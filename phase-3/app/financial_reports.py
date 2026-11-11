"""Read-only financial statements derived from posted journal lines."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from .models import ChartOfAccount, JournalEntry, JournalLine

ZERO = Decimal("0.00")


def _period(start_date: date | None, end_date: date | None) -> tuple[date, date]:
    end = end_date or date.today()
    start = start_date or date(end.year if end.month >= 4 else end.year - 1, 4, 1)
    if start > end:
        raise HTTPException(422, "start_date must be on or before end_date")
    return start, end


def _decimal(value) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value or 0))


def _ledger_data(db: Session, end_date: date):
    accounts = db.query(ChartOfAccount).order_by(ChartOfAccount.account_code).all()
    by_code = {account.account_code: account for account in accounts}
    entries = db.query(JournalEntry).filter(
        JournalEntry.status == "POSTED", JournalEntry.entry_date <= end_date
    ).order_by(JournalEntry.entry_date, JournalEntry.entry_id).all()
    lines = db.query(JournalLine).join(JournalEntry, JournalEntry.entry_id == JournalLine.entry_id).filter(
        JournalEntry.status == "POSTED", JournalEntry.entry_date <= end_date
    ).order_by(JournalEntry.entry_id, JournalLine.line_no).all()
    by_entry: dict[str, list[JournalLine]] = {}
    for line in lines:
        by_entry.setdefault(line.entry_id, []).append(line)

    invalid = []
    for entry in entries:
        entry_lines = by_entry.get(entry.entry_id, [])
        debit = sum((_decimal(line.debit) for line in entry_lines), ZERO)
        credit = sum((_decimal(line.credit) for line in entry_lines), ZERO)
        if len(entry_lines) < 2 or debit != credit or debit == ZERO:
            invalid.append(entry.entry_id)
            continue
        for line in entry_lines:
            account = by_code.get(line.account_code)
            dr, cr = _decimal(line.debit), _decimal(line.credit)
            if (dr < ZERO or cr < ZERO or (dr > ZERO) == (cr > ZERO)
                    or account is None or account.is_group):
                invalid.append(entry.entry_id)
                break
    if invalid:
        raise HTTPException(409, {
            "message": "Financial report cannot include unbalanced or invalid posted journal entries",
            "entry_ids": sorted(set(invalid))[:20],
        })
    return accounts, by_code, entries, lines


def _build_maps(db: Session, accounts, by_code, lines, start: date, end: date):
    entry_dates = {entry_id: entry_date for entry_id, entry_date in db.query(
        JournalEntry.entry_id, JournalEntry.entry_date
    ).filter(JournalEntry.status == "POSTED", JournalEntry.entry_date <= end).all()}
    rows = {a.account_code: {"opening_debit": ZERO, "opening_credit": ZERO,
                            "period_debit": ZERO, "period_credit": ZERO}
            for a in accounts if not a.is_group}
    for line in lines:
        account = by_code.get(line.account_code)
        if account is None or account.is_group:
            continue
        key = "opening" if entry_dates[line.entry_id] < start else "period"
        rows[account.account_code][f"{key}_debit"] += _decimal(line.debit)
        rows[account.account_code][f"{key}_credit"] += _decimal(line.credit)
    return rows


def _signed_side(net: Decimal) -> tuple[Decimal, Decimal]:
    return (net, ZERO) if net >= ZERO else (ZERO, -net)


def _rollup(rows: dict[str, dict], by_code: dict[str, ChartOfAccount]):
    result = {code: dict(values) for code, values in rows.items()}
    for code, values in rows.items():
        account = by_code[code]
        parent_code = account.parent_code
        seen = {code}
        while parent_code:
            if parent_code in seen or parent_code not in by_code:
                raise HTTPException(409, f"Invalid chart-of-accounts hierarchy at {code}")
            seen.add(parent_code)
            parent = by_code[parent_code]
            target = result.setdefault(parent_code, {key: ZERO for key in values})
            for key, value in values.items():
                target[key] += value
            parent_code = parent.parent_code
    return result


def _read(db: Session, start: date | None, end: date | None):
    start, end = _period(start, end)
    accounts, by_code, entries, lines = _ledger_data(db, end)
    rows = _build_maps(db, accounts, by_code, lines, start, end)
    return start, end, accounts, by_code, rows, _rollup(rows, by_code)


def trial_balance(db: Session, start_date: date | None = None, end_date: date | None = None):
    start, end, accounts, by_code, leaf_rows, all_rows = _read(db, start_date, end_date)
    result = []
    totals = {key: ZERO for key in (
        "opening_debit", "opening_credit", "period_debit", "period_credit", "closing_debit", "closing_credit")}
    for account in accounts:
        values = all_rows.get(account.account_code, {key: ZERO for key in totals})
        opening_net = values["opening_debit"] - values["opening_credit"]
        closing_net = opening_net + values["period_debit"] - values["period_credit"]
        opening_dr, opening_cr = _signed_side(opening_net)
        closing_dr, closing_cr = _signed_side(closing_net)
        row = {"account_code": account.account_code, "account_name": account.account_name,
               "account_type": account.account_type, "parent_code": account.parent_code,
               "is_group": bool(account.is_group), "opening_debit": opening_dr,
               "opening_credit": opening_cr, "period_debit": values["period_debit"],
               "period_credit": values["period_credit"], "closing_debit": closing_dr,
               "closing_credit": closing_cr}
        result.append(row)
    # Recalculate opening columns as signed balances (they must balance independently).
    totals["opening_debit"] = sum((_signed_side(v["opening_debit"] - v["opening_credit"])[0]
                                    for v in leaf_rows.values()), ZERO)
    totals["opening_credit"] = sum((_signed_side(v["opening_debit"] - v["opening_credit"])[1]
                                     for v in leaf_rows.values()), ZERO)
    totals["period_debit"] = sum((v["period_debit"] for v in leaf_rows.values()), ZERO)
    totals["period_credit"] = sum((v["period_credit"] for v in leaf_rows.values()), ZERO)
    totals["closing_debit"] = sum((_signed_side(v["opening_debit"] - v["opening_credit"] + v["period_debit"] - v["period_credit"])[0]
                                    for v in leaf_rows.values()), ZERO)
    totals["closing_credit"] = sum((_signed_side(v["opening_debit"] - v["opening_credit"] + v["period_debit"] - v["period_credit"])[1]
                                     for v in leaf_rows.values()), ZERO)
    return {"start_date": start, "end_date": end, "rows": result,
            "totals": totals, "balanced": totals["closing_debit"] == totals["closing_credit"]}


def _statement_groups(accounts, amounts, account_types):
    groups = [a for a in accounts if a.is_group and a.parent_code is None and a.account_type in account_types]
    result = []
    for group in groups:
        children = []
        for account in accounts:
            if account.is_group or account.account_type != group.account_type:
                continue
            parent = account.parent_code
            while parent and parent != group.account_code:
                parent = next((a.parent_code for a in accounts if a.account_code == parent), None)
            if parent == group.account_code:
                children.append({"account_code": account.account_code, "account_name": account.account_name,
                                 "amount": amounts.get(account.account_code, ZERO)})
        result.append({"account_code": group.account_code, "account_name": group.account_name,
                       "amount": sum((child["amount"] for child in children), ZERO), "accounts": children})
    return result


def profit_and_loss(db: Session, start_date: date | None = None, end_date: date | None = None):
    start, end, accounts, by_code, rows, _ = _read(db, start_date, end_date)
    income_amounts, expense_amounts = {}, {}
    for code, account in by_code.items():
        if account.is_group:
            continue
        values = rows.get(code, {})
        activity = values.get("period_credit", ZERO) - values.get("period_debit", ZERO)
        if account.account_type == "INCOME":
            income_amounts[code] = activity
        elif account.account_type == "EXPENSE":
            expense_amounts[code] = -activity
    revenue = sum(income_amounts.values(), ZERO)
    expenses = sum(expense_amounts.values(), ZERO)
    return {"start_date": start, "end_date": end,
            "revenue": _statement_groups(accounts, income_amounts, {"INCOME"}),
            "expenses": _statement_groups(accounts, expense_amounts, {"EXPENSE"}),
            "total_revenue": revenue, "total_expenses": expenses,
            "net_profit": revenue - expenses}


def balance_sheet(db: Session, start_date: date | None = None, end_date: date | None = None):
    start, end, accounts, by_code, rows, all_rows = _read(db, start_date, end_date)
    assets_amounts, liabilities_amounts, equity_amounts = {}, {}, {}
    prior_income = prior_expense = ZERO
    for code, account in by_code.items():
        if account.is_group:
            continue
        values = rows.get(code, {})
        closing = values["opening_debit"] - values["opening_credit"] + values["period_debit"] - values["period_credit"]
        if account.account_type == "ASSET":
            assets_amounts[code] = closing
        elif account.account_type == "LIABILITY":
            liabilities_amounts[code] = -closing
        elif account.account_type == "EQUITY":
            equity_amounts[code] = -closing
        elif account.account_type == "INCOME":
            prior_income += values["opening_credit"] - values["opening_debit"]
        elif account.account_type == "EXPENSE":
            prior_expense += values["opening_debit"] - values["opening_credit"]
    current_profit = profit_and_loss(db, start, end)["net_profit"]
    prior_profit = prior_income - prior_expense
    assets_total = sum(assets_amounts.values(), ZERO)
    liabilities_total = sum(liabilities_amounts.values(), ZERO)
    recorded_equity = sum(equity_amounts.values(), ZERO)
    equity_total = recorded_equity + prior_profit
    right_side = liabilities_total + equity_total + current_profit
    return {"start_date": start, "end_date": end,
            "assets": _statement_groups(accounts, assets_amounts, {"ASSET"}),
            "liabilities": _statement_groups(accounts, liabilities_amounts, {"LIABILITY"}),
            "equity": _statement_groups(accounts, equity_amounts, {"EQUITY"}),
            "assets_total": assets_total, "liabilities_total": liabilities_total,
            "recorded_equity_total": recorded_equity, "prior_period_profit": prior_profit,
            "equity_total_including_prior_profit": equity_total,
            "current_period_profit": current_profit, "liabilities_equity_and_profit": right_side,
            "difference": assets_total - right_side, "balanced": assets_total == right_side}
