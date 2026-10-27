from verify_ledgerforge import within_one_paisa
from scripts.run_payroll_validation import mismatch_cause


def test_payroll_validator_accepts_exact_one_paisa_difference():
    assert within_one_paisa("123456.78", "123456.77")


def test_payroll_validator_rejects_difference_over_one_paisa():
    assert not within_one_paisa("123456.78", "123456.76")


def test_payroll_validator_uses_decimal_not_binary_float():
    # This decimal difference is exactly one paisa, although float subtraction
    # can represent it as slightly more than 0.01.
    assert abs(float("1.01") - float("1.00")) > 0.01
    assert within_one_paisa("1.01", "1.00")

def test_payroll_mismatch_classification_names_component_and_policy():
    assert mismatch_cause("variable_pay")=="variable_pay_source_missing_or_unapproved"
    assert mismatch_cause("professional_tax")=="professional_tax_rule_or_state"
    assert mismatch_cause("other_deductions")=="employee_loan_or_advance_schedule_missing"
