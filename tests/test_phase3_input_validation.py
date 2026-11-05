from scripts.phase3_input_validation import validate_phase3_inputs


def test_phase3_source_validation_reconciles_ledgers_and_preserves_legacy_warnings():
    report = validate_phase3_inputs("data")
    assert report["counts"] == {"vendors": 30, "expenses": 501, "payroll_runs": 18,
        "journal_entries": 2524, "journal_lines": 6784}
    assert report["errors"] == {}
    assert report["expense_status_counts"] == {"PAID": 478, "UNPAID": 23}
    assert report["duplicate_bill_candidates"] == {"exact": [], "likely": []}
    assert report["legacy_warning_counts"]["legacy_separation_of_duties_violations"] == 14
    assert all(row["run_employer_cost"] == row["ledger_payroll_debit"]
               for row in report["payroll_month_reconciliation"].values())
    assert report["expense_totals_by_month"]["2025-04"] == {
        "amount_excl_gst": "11042940.00", "gst_amount": "1892144.10", "total_amount": "12935084.10"}
