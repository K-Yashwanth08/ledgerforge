import csv
from pathlib import Path

from scripts.preview_tax_configuration import preview_bundle


def _write(path, columns, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def test_sample_bundle_is_never_production_ready_and_does_not_write_db():
    result = preview_bundle(Path("data"))
    assert result["database_changed"] is False
    assert result["sample_rows"] > 0
    assert result["production_ready"] is False
    assert any("missing required columns" in error for error in result["errors"])


def test_preview_accepts_complete_approved_provenance_bundle(tmp_path):
    common = {"approval_status": "APPROVED", "source_reference": "Policy circular REF-2026-01",
              "note": "Approved by policy owner"}
    _write(tmp_path / "tax_slabs.csv",
        ["slab_id", "financial_year", "regime", "income_from", "income_to", "rate_percent",
         "effective_from", "effective_to", "approval_status", "source_reference", "note"],
        [dict(common, slab_id="A", financial_year="FY2026-27", regime="REGIME_A", income_from="0",
             income_to="100000", rate_percent="0", effective_from="2026-04-01", effective_to=""),
         dict(common, slab_id="B", financial_year="FY2026-27", regime="REGIME_A", income_from="100000",
             income_to="", rate_percent="10", effective_from="2026-04-01", effective_to="")])
    parameter_rows = [dict(common, parameter=name, financial_year="FY2026-27", regime="REGIME_A",
        value=value, effective_from="2026-04-01", effective_to="") for name, value in [
        ("standard_deduction", "0"), ("rebate_threshold_taxable", "0"),
        ("rebate_amount", "0"),
        ("health_education_cess_percent", "0")]]
    _write(tmp_path / "tax_parameters.csv",
        ["parameter", "financial_year", "regime", "value", "effective_from", "effective_to",
         "approval_status", "source_reference", "note"], parameter_rows)
    rates = ["PF_EMPLOYEE_RATE", "PF_EMPLOYER_RATE", "PF_WAGE_CEILING", "ESI_EMPLOYEE_RATE",
        "ESI_EMPLOYER_RATE", "ESI_WAGE_LIMIT", "PT_MONTHLY", "PT_GROSS_THRESHOLD", "OT_MULTIPLIER",
        "OT_MONTHLY_CAP_HOURS", "WORKING_HOURS_PER_MONTH"]
    _write(tmp_path / "statutory_rates.csv",
        ["parameter", "value", "unit", "effective_from", "effective_to", "approval_status",
         "source_reference", "note"],
        [dict(common, parameter=name, value="1", unit="INR", effective_from="2026-04-01", effective_to="")
         for name in rates])
    result = preview_bundle(tmp_path)
    assert result["production_ready"] is True
    assert result["errors"] == []
    assert result["sample_rows"] == 0


def test_preview_rejects_overlapping_versions_and_unapproved_policy(tmp_path):
    common = {"approval_status": "PENDING", "source_reference": "REF-1", "note": "Pending"}
    _write(tmp_path / "tax_slabs.csv",
        ["slab_id", "financial_year", "regime", "income_from", "income_to", "rate_percent",
         "effective_from", "effective_to", "approval_status", "source_reference", "note"], [])
    _write(tmp_path / "tax_parameters.csv",
        ["parameter", "financial_year", "regime", "value", "effective_from", "effective_to",
         "approval_status", "source_reference", "note"],
        [dict(common, parameter="standard_deduction", financial_year="FY2026-27", regime="A",
              value="0", effective_from="2026-04-01", effective_to="2026-12-31"),
         dict(common, parameter="standard_deduction", financial_year="FY2026-27", regime="A",
              value="0", effective_from="2026-11-01", effective_to="")])
    _write(tmp_path / "statutory_rates.csv",
        ["parameter", "value", "unit", "effective_from", "effective_to", "approval_status",
         "source_reference", "note"], [])
    result = preview_bundle(tmp_path)
    assert result["production_ready"] is False
    assert any("overlaps" in error for error in result["errors"])
    assert any("approval_status must be APPROVED" in error for error in result["errors"])
