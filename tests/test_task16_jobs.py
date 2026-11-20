from datetime import date

import pytest
from unittest.mock import Mock

from app import jobs
from app.jobs import month_sequence
from scripts.run_payroll_validation import mismatch_cause


def test_month_sequence_spans_18_months_and_year_boundary():
    periods = month_sequence("2025-07")
    assert len(periods) == 18
    assert periods[0] == ("2025-07", date(2025, 7, 31))
    assert periods[5] == ("2025-12", date(2025, 12, 31))
    assert periods[6] == ("2026-01", date(2026, 1, 31))
    assert periods[-1] == ("2026-12", date(2026, 12, 31))


@pytest.mark.parametrize("month", ["2025-00", "2025-13", "invalid"])
def test_month_sequence_rejects_invalid_month(month):
    with pytest.raises((ValueError, TypeError)):
        month_sequence(month)


def test_background_task_runs_each_month_and_records_progress(monkeypatch):
    session = Mock()
    session_factory = Mock()
    session_factory.return_value.__enter__ = Mock(return_value=session)
    session_factory.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(jobs, "SessionLocal", session_factory)
    run_month = Mock(side_effect=lambda _db, month, _pay_date, **_kwargs:
                     (Mock(run_id=f"RUN-{month}"), []))
    monkeypatch.setattr(jobs, "run_payroll_month", run_month)
    progress = []
    monkeypatch.setattr(jobs.run_18_month_payroll, "update_state",
                        lambda **kwargs: progress.append(kwargs))

    result = jobs.run_18_month_payroll.run("2025-01")

    assert len(result["run_ids"]) == 18
    assert result["run_ids"][0] == "RUN-2025-01"
    assert result["run_ids"][-1] == "RUN-2026-06"
    assert run_month.call_count == 18
    assert progress[-1]["meta"]["current"] == progress[-1]["meta"]["total"] == 18


def test_all_api_routes_are_documented_under_v1():
    from app.main import app

    documented = app.openapi()["paths"]
    assert "/api/v1/auth/login" in documented
    assert "/api/v1/payroll/jobs/18-month" in documented
    assert "/api/v1/payroll/jobs/{job_id}" in documented
    assert "/api/v1/health" in documented
    assert "/auth/login" not in documented


@pytest.mark.parametrize(("field", "expected"), [
    ("calendar_days", "employment_period_or_calendar"),
    ("lop_days", "attendance_or_loss_of_pay_policy"),
    ("variable_pay", "variable_pay_source_missing_or_unapproved"),
    ("monthly_fixed_gross", "salary_structure_or_lop_proration"),
    ("overtime_pay", "overtime_input_or_policy"),
    ("pf_employee", "pf_rate_wage_base_or_eligibility"),
    ("esi_employer", "esi_rate_wage_base_or_eligibility"),
    ("professional_tax", "professional_tax_rule_or_state"),
    ("tds", "tax_regime_declarations_or_authoritative_rules"),
    ("other_deductions", "employee_loan_or_advance_schedule_missing"),
    ("net_pay", "derived_from_component_mismatches"),
    ("unrecognized", "unresolved"),
])
def test_payroll_comparison_classifies_mismatch_fields(field, expected):
    assert mismatch_cause(field) == expected
