"""Read-only validation for Phase 3 vendor, expense, payroll, and ledger CSVs."""
import csv
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

ZERO = Decimal("0.00")
CENT = Decimal("0.01")


def _read(data_dir: Path, filename: str):
    path = data_dir / filename
    if not path.is_file():
        raise FileNotFoundError(f"Required Phase 3 input is missing: {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _duplicates(rows, key):
    counts = Counter(key(row) for row in rows if key(row) not in (None, ""))
    return {str(value): count for value, count in counts.items() if count > 1}


def _money(value):
    return Decimal(str(value or "0")).quantize(CENT, rounding=ROUND_HALF_UP)


def validate_phase3_inputs(data_dir: str | Path):
    root = Path(data_dir)
    vendors = _read(root, "vendors.csv")
    expenses = _read(root, "expenses.csv")
    runs = _read(root, "payroll_runs.csv")
    journals = _read(root, "journal_entries.csv")
    lines = _read(root, "journal_lines.csv")
    accounts = _read(root, "chart_of_accounts.csv")
    employees = _read(root, "employees.csv")
    departments = _read(root, "departments.csv")

    errors = defaultdict(list)
    warnings = defaultdict(list)
    vendor_map = {row["vendor_id"]: row for row in vendors}
    account_map = {row["account_code"].split(".")[0]: row for row in accounts}
    journal_map = {row["entry_id"]: row for row in journals}
    source_counts = Counter((row["source_type"], row.get("source_id", "")) for row in journals)
    lines_by_entry = defaultdict(list)
    for line in lines:
        lines_by_entry[line["entry_id"]].append(line)
    departments_set = {row["department_id"] for row in departments}
    employee_set = {row["employee_id"] for row in employees}

    duplicate_vendor_ids = _duplicates(vendors, lambda row: row.get("vendor_id"))
    duplicate_expense_ids = _duplicates(expenses, lambda row: row.get("expense_id"))
    duplicate_run_ids = _duplicates(runs, lambda row: row.get("run_id"))
    duplicate_idempotency = _duplicates(runs, lambda row: row.get("idempotency_key"))
    duplicate_journal_ids = _duplicates(journals, lambda row: row.get("entry_id"))
    if duplicate_vendor_ids: errors["duplicate_vendor_ids"].append(duplicate_vendor_ids)
    if duplicate_expense_ids: errors["duplicate_expense_ids"].append(duplicate_expense_ids)
    if duplicate_run_ids: errors["duplicate_payroll_run_ids"].append(duplicate_run_ids)
    if duplicate_idempotency: errors["duplicate_payroll_idempotency_keys"].append(duplicate_idempotency)
    if duplicate_journal_ids: errors["duplicate_journal_entry_ids"].append(duplicate_journal_ids)

    for vendor in vendors:
        code = vendor["primary_expense_account"].split(".")[0]
        account = account_map.get(code)
        if not account or account["account_type"] != "EXPENSE" or account["is_group"].upper() != "N" or account["is_active"].upper() != "Y":
            errors["invalid_vendor_expense_account"].append([vendor["vendor_id"], code])

    expense_totals = defaultdict(lambda: {"amount_excl_gst": ZERO, "gst_amount": ZERO, "total_amount": ZERO})
    expense_ledger_totals = defaultdict(lambda: {"amount_excl_gst": ZERO, "gst_amount": ZERO, "total_amount": ZERO})
    status_counts = Counter()
    exact_dupes, likely_dupes = [], []
    refs = defaultdict(list)
    for expense in expenses:
        expense_id = expense["expense_id"]
        vendor = vendor_map.get(expense["vendor_id"])
        if not vendor: errors["unknown_vendor"].append(expense_id)
        if not expense.get("submitted_by") or expense["submitted_by"] not in employee_set:
            errors["unknown_expense_submitter"].append([expense_id, expense.get("submitted_by")])
        if expense.get("approved_by") and expense["approved_by"] not in employee_set:
            errors["unknown_expense_approver"].append([expense_id, expense["approved_by"]])
        code = expense["category_account"].split(".")[0]
        account = account_map.get(code)
        if not account or account["account_type"] != "EXPENSE" or account["is_group"].upper() != "N" or account["is_active"].upper() != "Y":
            errors["invalid_expense_account"].append([expense_id, code])
        if vendor and code != vendor["primary_expense_account"].split(".")[0]:
            warnings["vendor_category_account_conflict"].append([expense_id, expense["vendor_id"], vendor["primary_expense_account"], code])
        if expense.get("department_id") and expense["department_id"] not in departments_set:
            errors["unknown_department"].append([expense_id, expense["department_id"]])
        for column in ("expense_date", "due_date"):
            try: date.fromisoformat(expense[column])
            except (ValueError, TypeError): errors["invalid_" + column].append([expense_id, expense.get(column)])
        if expense.get("paid_date"):
            try: date.fromisoformat(expense["paid_date"])
            except (ValueError, TypeError): errors["invalid_paid_date"].append([expense_id, expense.get("paid_date")])
        try:
            excl = _money(expense["amount_excl_gst"])
            gst = _money(expense["gst_amount"])
            total = _money(expense["total_amount"])
            rate = Decimal(expense["gst_rate_percent"])
            expected_gst = (excl * rate / Decimal("100")).quantize(CENT, rounding=ROUND_HALF_UP)
            if min(excl, gst, total, rate) < ZERO: errors["negative_expense_amount"].append(expense_id)
            if gst != expected_gst: errors["gst_calculation_mismatch"].append([expense_id, str(gst), str(expected_gst)])
            if total != excl + gst: errors["expense_total_mismatch"].append([expense_id, str(total), str(excl + gst)])
            month = expense["expense_date"][:7]
            for key, value in (("amount_excl_gst", excl), ("gst_amount", gst), ("total_amount", total)):
                expense_totals[month][key] += value
        except (InvalidOperation, KeyError):
            errors["invalid_expense_amount"].append(expense_id)
            continue
        status = expense["status"].upper()
        status_counts[status] += 1
        if status not in {"PAID", "UNPAID"}:
            errors["unknown_expense_status"].append([expense_id, status])
        if status == "PAID" and (not expense.get("paid_date") or not expense.get("payment_ledger_entry_id")):
            errors["paid_without_payment_evidence"].append(expense_id)
        if status == "UNPAID" and (expense.get("paid_date") or expense.get("payment_ledger_entry_id")):
            errors["unpaid_with_payment_evidence"].append(expense_id)
        if expense.get("approved_by") and expense.get("submitted_by") == expense.get("approved_by"):
            warnings["legacy_separation_of_duties_violations"].append(expense_id)
        for column, source_type in (("ledger_entry_id", "EXPENSE"), ("payment_ledger_entry_id", "EXPENSE_PAYMENT")):
            entry_id = expense.get(column)
            if not entry_id:
                if column == "ledger_entry_id": errors["missing_expense_journal"].append(expense_id)
                continue
            entry = journal_map.get(entry_id)
            if not entry:
                errors["missing_" + column].append([expense_id, entry_id])
                continue
            if entry["source_type"] != source_type or entry.get("source_id") != expense_id:
                errors["expense_journal_source_mismatch"].append([expense_id, column, entry["source_type"], entry.get("source_id")])
            line_totals = defaultdict(lambda: [ZERO, ZERO])
            for line in lines_by_entry[entry_id]:
                line_totals[line["account_code"].split(".")[0]][0] += _money(line["debit"])
                line_totals[line["account_code"].split(".")[0]][1] += _money(line["credit"])
            actual = {key: tuple(value) for key, value in line_totals.items() if value != [ZERO, ZERO]}
            if column == "ledger_entry_id":
                expected = {code: (excl, ZERO), "1200": (gst, ZERO), "2001": (ZERO, total)}
            else:
                cash_codes = [code for code, (debit, credit) in actual.items() if code != "2001" and credit == total and debit == ZERO]
                if len(cash_codes) != 1 or any(code not in {"1001", "1002", "2001"} for code in actual):
                    errors["invalid_expense_payment_cash_account"].append([expense_id, cash_codes])
                    cash_codes = cash_codes[:1]
                expected = {"2001": (total, ZERO)}
                if cash_codes: expected[cash_codes[0]] = (ZERO, total)
            expected = {key: value for key, value in expected.items() if value != (ZERO, ZERO)}
            if actual != expected:
                errors["expense_journal_line_mismatch"].append([expense_id, column, actual, expected])
            if column == "ledger_entry_id":
                month_ledger = expense_ledger_totals[expense["expense_date"][:7]]
                month_ledger["amount_excl_gst"] += actual.get(code, (ZERO, ZERO))[0]
                month_ledger["gst_amount"] += actual.get("1200", (ZERO, ZERO))[0]
                month_ledger["total_amount"] += actual.get("2001", (ZERO, ZERO))[1]
            debit = sum((value[0] for value in actual.values()), ZERO)
            credit = sum((value[1] for value in actual.values()), ZERO)
            if debit != credit or debit != _money(entry["total_debit"]) or credit != _money(entry["total_credit"]):
                errors["expense_journal_unbalanced"].append([expense_id, entry_id])
        if expense.get("bill_reference"):
            refs[(expense["vendor_id"], expense["bill_reference"].strip().casefold())].append(expense)

    for (vendor_id, ref), group in refs.items():
        if len(group) > 1:
            exact_groups = defaultdict(list)
            for row in group:
                exact_groups[(row["expense_date"], row["total_amount"])].append(row["expense_id"])
            for (expense_date, amount), ids in exact_groups.items():
                if len(ids) > 1: exact_dupes.append([vendor_id, ref, expense_date, amount, ids])
            if not any(vendor_id == x[0] and ref == x[1] for x in exact_dupes):
                likely_dupes.append([vendor_id, ref, [row["expense_id"] for row in group]])

    # Detect likely duplicates with matching vendor, date, and gross amount even if the reference differs.
    by_vendor_date_amount = defaultdict(list)
    for row in expenses:
        by_vendor_date_amount[(row["vendor_id"], row["expense_date"], row["total_amount"])].append(row)
    for key, group in by_vendor_date_amount.items():
        refs_seen = {row["bill_reference"].strip().casefold() for row in group}
        if len(group) > 1 and len(refs_seen) > 1:
            likely_dupes.append([key[0], key[1], key[2], [row["expense_id"] for row in group]])

    # Validate every journal entry and its lines. Reversal references use source IDs in this source snapshot.
    for entry in journals:
        entry_lines = lines_by_entry.get(entry["entry_id"], [])
        debit = sum((_money(line["debit"]) for line in entry_lines), ZERO)
        credit = sum((_money(line["credit"]) for line in entry_lines), ZERO)
        if len(entry_lines) < 2 or debit != credit or debit != _money(entry["total_debit"]) or credit != _money(entry["total_credit"]):
            errors["journal_unbalanced_or_header_mismatch"].append(entry["entry_id"])
        reversal_ref = entry.get("reversal_of_source_id")
        if reversal_ref and not any(row.get("source_id") == reversal_ref for row in journals):
            errors["invalid_reversal_source_reference"].append([entry["entry_id"], reversal_ref])

    for source_type in ("EXPENSE", "EXPENSE_PAYMENT", "PAYROLL_RUN", "SALARY_PAYMENT"):
        repeated = {source_id: count for (kind, source_id), count in source_counts.items()
                    if kind == source_type and source_id and count > 1}
        if repeated: errors[f"duplicate_{source_type.lower()}_journal_source"].append(repeated)

    payroll_lines_by_run = defaultdict(list)
    for entry in journals:
        if entry["source_type"] == "PAYROLL_RUN":
            payroll_lines_by_run[entry.get("source_id")].append(entry)
    run_months = defaultdict(lambda: {"run_employer_cost": ZERO, "ledger_payroll_debit": ZERO})
    salary_payment_entries = defaultdict(list)
    for entry in journals:
        if entry["source_type"] == "SALARY_PAYMENT":
            salary_payment_entries[entry.get("source_id")].append(entry)
    for run in runs:
        run_id = run["run_id"]
        if not run.get("idempotency_key"): errors["missing_payroll_idempotency_key"].append(run_id)
        entry_id = run.get("journal_entry_id")
        entry = journal_map.get(entry_id or "")
        if not entry: errors["missing_payroll_journal_entry"].append([run_id, entry_id])
        elif entry["source_type"] != "PAYROLL_RUN" or entry.get("source_id") != run_id or entry["status"] != "POSTED":
            errors["payroll_journal_source_or_status_mismatch"].append([run_id, entry_id])
        associated = payroll_lines_by_run.get(run_id, [])
        if len(associated) != 1: errors["payroll_journal_duplicate_or_missing_source"].append([run_id, len(associated)])
        if run["status"] in {"PAID", "POSTED - PAYMENT PENDING"} and (not entry or entry["status"] != "POSTED"):
            errors["payroll_run_status_mismatch"].append([run_id, run["status"]])
        if _money(run["total_gross"]) - _money(run["total_deductions"]) != _money(run["total_net"]):
            errors["payroll_net_total_mismatch"].append(run_id)
        if _money(run["total_gross"]) + _money(run["total_employer_contributions"]) != _money(run["total_employer_cost"]):
            errors["payroll_employer_cost_mismatch"].append(run_id)
        payments = salary_payment_entries.get(run_id, [])
        if run["status"] == "PAID":
            if len(payments) != 1 or not run.get("pay_date"):
                errors["paid_payroll_missing_salary_payment"].append([run_id, len(payments)])
            elif payments[0]["status"] != "POSTED" or payments[0]["entry_date"] != run["pay_date"]:
                errors["salary_payment_date_or_status_mismatch"].append([run_id, payments[0]["entry_id"]])
            else:
                payment_lines = lines_by_entry[payments[0]["entry_id"]]
                pay_debits = sum((_money(line["debit"]) for line in payment_lines
                                  if line["account_code"].split(".")[0] == "2100"), ZERO)
                pay_bank_credits = sum((_money(line["credit"]) for line in payment_lines
                                        if line["account_code"].split(".")[0] in {"1001", "1002"}), ZERO)
                if pay_debits != _money(run["total_net"]) or pay_bank_credits != _money(run["total_net"]):
                    errors["salary_payment_amount_mismatch"].append([run_id, str(pay_debits), str(pay_bank_credits)])
        elif run["status"] == "POSTED - PAYMENT PENDING" and payments:
            errors["pending_payroll_has_salary_payment"] .append([run_id, [item["entry_id"] for item in payments]])
        month = run["period_start"][:7]
        run_months[month]["run_employer_cost"] += _money(run["total_employer_cost"])
        if entry:
            for line in lines_by_entry[entry_id]:
                account = account_map.get(line["account_code"].split(".")[0])
                if account and account["account_type"] == "EXPENSE":
                    run_months[month]["ledger_payroll_debit"] += _money(line["debit"])
    for month, totals in run_months.items():
        if totals["run_employer_cost"] != totals["ledger_payroll_debit"]:
            errors["payroll_month_reconciliation_mismatch"].append([month, str(totals["run_employer_cost"]), str(totals["ledger_payroll_debit"])])
    for month, source_values in expense_totals.items():
        ledger_values = expense_ledger_totals.get(month, {key: ZERO for key in source_values})
        if source_values != ledger_values:
            errors["monthly_expense_ledger_reconciliation_mismatch"].append([month,
                {key: str(value) for key, value in source_values.items()},
                {key: str(value) for key, value in ledger_values.items()}])
    for entry in journals:
        if entry["source_type"] == "PAYROLL_RUN" and entry.get("source_id") not in {run["run_id"] for run in runs}:
            errors["orphan_payroll_journal_entry"].append(entry["entry_id"])

    report = {
        "counts": {"vendors": len(vendors), "expenses": len(expenses), "payroll_runs": len(runs),
                   "journal_entries": len(journals), "journal_lines": len(lines)},
        "duplicate_ids": {"vendor_ids": duplicate_vendor_ids, "expense_ids": duplicate_expense_ids,
                          "payroll_run_ids": duplicate_run_ids, "payroll_idempotency_keys": duplicate_idempotency,
                          "journal_entry_ids": duplicate_journal_ids},
        "expense_status_counts": dict(status_counts),
        "expense_totals_by_month": {month: {key: str(value) for key, value in values.items()}
                                    for month, values in sorted(expense_totals.items())},
        "expense_ledger_totals_by_month": {month: {key: str(value) for key, value in values.items()}
                                           for month, values in sorted(expense_ledger_totals.items())},
        "duplicate_bill_candidates": {"exact": exact_dupes, "likely": likely_dupes},
        "legacy_warnings": {key: value for key, value in warnings.items()},
        "payroll_month_reconciliation": {month: {key: str(value) for key, value in values.items()}
                                         for month, values in sorted(run_months.items())},
        "errors": {key: value[:50] for key, value in errors.items()},
        "error_counts": {key: len(value) for key, value in errors.items()},
        "legacy_warning_counts": {key: len(value) for key, value in warnings.items()},
    }
    return report
