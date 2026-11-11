"""Validate a proposed tax/statutory CSV bundle without writing to the database."""
import argparse
import csv
import json
import re
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


REQUIRED = {
    "tax_slabs.csv": {"slab_id", "financial_year", "regime", "income_from", "income_to",
                      "rate_percent", "effective_from", "effective_to", "approval_status",
                      "source_reference", "note"},
    "tax_parameters.csv": {"parameter", "financial_year", "regime", "value", "effective_from",
                           "effective_to", "approval_status", "source_reference", "note"},
    "statutory_rates.csv": {"parameter", "value", "unit", "effective_from", "effective_to",
                            "approval_status", "source_reference", "note"},
}
REQUIRED_TAX_PARAMETERS = {"standard_deduction", "rebate_threshold_taxable", "rebate_amount",
                           "health_education_cess_percent"}
REQUIRED_STATUTORY_PARAMETERS = {"PF_EMPLOYEE_RATE", "PF_EMPLOYER_RATE", "PF_WAGE_CEILING",
    "ESI_EMPLOYEE_RATE", "ESI_EMPLOYER_RATE", "ESI_WAGE_LIMIT", "PT_MONTHLY",
    "PT_GROSS_THRESHOLD", "OT_MULTIPLIER", "OT_MONTHLY_CAP_HOURS", "WORKING_HOURS_PER_MONTH"}


def _decimal(value: str, label: str, errors: list[str]) -> Decimal | None:
    try:
        parsed = Decimal(value)
        if not parsed.is_finite():
            raise InvalidOperation
        return parsed
    except (InvalidOperation, TypeError):
        errors.append(f"{label}: expected a finite decimal")
        return None


def _date(value: str, label: str, errors: list[str], *, optional: bool = False) -> date | None:
    if optional and not value:
        return None
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        errors.append(f"{label}: expected YYYY-MM-DD")
        return None


def _read(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            missing = REQUIRED[path.name] - set(reader.fieldnames or ())
            if missing:
                errors.append(f"{path.name}: missing required columns: {', '.join(sorted(missing))}")
            return list(reader)
    except OSError as exc:
        errors.append(f"{path.name}: cannot read file ({exc})")
        return []


def _validate_timeline(rows: list[dict[str, str]], key_fields: tuple[str, ...], filename: str,
                      errors: list[str]) -> None:
    intervals: dict[tuple[str, ...], list[tuple[date, date | None, str]]] = defaultdict(list)
    for index, row in enumerate(rows, start=2):
        label = f"{filename}:{index}"
        start = _date(row.get("effective_from", ""), f"{label} effective_from", errors)
        end = _date(row.get("effective_to", ""), f"{label} effective_to", errors, optional=True)
        if start and end and end < start:
            errors.append(f"{label}: effective_to precedes effective_from")
        if start:
            intervals[tuple(row.get(field, "") for field in key_fields)].append((start, end, label))
    for key, ranges in intervals.items():
        ranges.sort(key=lambda item: item[0])
        for previous, current in zip(ranges, ranges[1:]):
            if previous[1] is None or current[0] <= previous[1]:
                errors.append(f"{current[2]}: effective range overlaps another version for {key}")


def preview_bundle(directory: Path) -> dict:
    errors: list[str] = []
    files = {name: _read(directory / name, errors) for name in REQUIRED}
    for name, rows in files.items():
        if not rows:
            errors.append(f"{name}: at least one data row is required")
    _validate_timeline(files["tax_parameters.csv"], ("parameter", "financial_year", "regime"),
                       "tax_parameters.csv", errors)
    _validate_timeline(files["statutory_rates.csv"], ("parameter",), "statutory_rates.csv", errors)
    sample_rows = 0
    unapproved_rows = 0
    for name, rows in files.items():
        for index, row in enumerate(rows, start=2):
            label = f"{name}:{index}"
            if any(term in (row.get("note", "") + " " + row.get("source_reference", "")).casefold()
                   for term in ("sample", "training", "demo")):
                sample_rows += 1
            if row.get("approval_status", "").strip().upper() != "APPROVED":
                unapproved_rows += 1
                errors.append(f"{label}: approval_status must be APPROVED")
            if not row.get("source_reference", "").strip():
                errors.append(f"{label}: source_reference is required")

    groups: dict[tuple[str, str, str], list[tuple[Decimal, Decimal | None, str]]] = defaultdict(list)
    slab_versions: dict[tuple[str, str], dict[date, list[date | None]]] = defaultdict(lambda: defaultdict(list))
    slab_ids: set[str] = set()
    for index, row in enumerate(files["tax_slabs.csv"], start=2):
        label = f"tax_slabs.csv:{index}"
        if row.get("slab_id") in slab_ids:
            errors.append(f"{label}: duplicate slab_id")
        slab_ids.add(row.get("slab_id", ""))
        low = _decimal(row.get("income_from", ""), f"{label} income_from", errors)
        high = _decimal(row["income_to"], f"{label} income_to", errors) if row.get("income_to", "").strip() else None
        rate = _decimal(row.get("rate_percent", ""), f"{label} rate_percent", errors)
        effective_from = _date(row.get("effective_from", ""), f"{label} effective_from", errors)
        effective_to = _date(row.get("effective_to", ""), f"{label} effective_to", errors, optional=True)
        fy, regime = row.get("financial_year", ""), row.get("regime", "")
        if not re.fullmatch(r"FY\d{4}-\d{2}", fy) or not regime.strip():
            errors.append(f"{label}: financial_year and regime are required")
        if effective_from:
            slab_versions[(fy, regime)][effective_from].append(effective_to)
        if low is not None and low < 0:
            errors.append(f"{label}: income_from cannot be negative")
        if high is not None and low is not None and high <= low:
            errors.append(f"{label}: income_to must exceed income_from")
        if rate is not None and not Decimal("0") <= rate <= Decimal("100"):
            errors.append(f"{label}: rate_percent must be between 0 and 100")
        if low is not None:
            groups[(fy, regime, row.get("effective_from", ""))].append((low, high, label))
    for key, slabs in groups.items():
        slabs.sort(key=lambda item: item[0])
        if slabs and slabs[0][0] != 0:
            errors.append(f"tax slabs {key}: first lower limit must be zero")
        for index, (low, high, label) in enumerate(slabs):
            if index and slabs[index - 1][1] != low:
                errors.append(f"{label}: slab boundaries must be contiguous and non-overlapping")
            if index < len(slabs) - 1 and high is None:
                errors.append(f"{label}: only the final slab may have an open upper limit")
            if index == len(slabs) - 1 and high is not None:
                errors.append(f"{label}: final slab must have an open upper limit")
    for key, versions in slab_versions.items():
        ranges = []
        for effective_from, ends in versions.items():
            if len(set(ends)) != 1:
                errors.append(f"tax slab version {key} effective {effective_from}: inconsistent effective_to values")
            ranges.append((effective_from, ends[0]))
        ranges.sort(key=lambda item: item[0])
        for previous, current in zip(ranges, ranges[1:]):
            if previous[1] is None or current[0] <= previous[1]:
                errors.append(f"tax slab version {key} effective {current[0]}: date range overlaps another version")

    parameter_keys: set[tuple[str, str, str, str]] = set()
    parameter_groups: dict[tuple[str, str, str], set[str]] = defaultdict(set)
    for index, row in enumerate(files["tax_parameters.csv"], start=2):
        label = f"tax_parameters.csv:{index}"
        key = (row.get("parameter", ""), row.get("financial_year", ""), row.get("regime", ""),
               row.get("effective_from", ""))
        if not re.fullmatch(r"FY\d{4}-\d{2}", key[1]) or not key[2].strip():
            errors.append(f"{label}: valid financial_year and regime are required")
        if key in parameter_keys:
            errors.append(f"{label}: duplicate parameter configuration version")
        parameter_keys.add(key)
        parameter_groups[key[1:]].add(key[0])
        value = _decimal(row.get("value", ""), f"{label} value", errors)
        _date(key[3], f"{label} effective_from", errors)
        _date(row.get("effective_to", ""), f"{label} effective_to", errors, optional=True)
        if value is not None and value < 0:
            errors.append(f"{label}: value cannot be negative")
        if key[0] == "health_education_cess_percent" and value is not None and value > 100:
            errors.append(f"{label}: cess cannot exceed 100 percent")
    for key, names in parameter_groups.items():
        missing = REQUIRED_TAX_PARAMETERS - names
        if missing:
            errors.append(f"tax parameters {key}: missing {', '.join(sorted(missing))}")

    rate_keys: set[tuple[str, str]] = set()
    rate_names: set[str] = set()
    for index, row in enumerate(files["statutory_rates.csv"], start=2):
        label = f"statutory_rates.csv:{index}"
        key = (row.get("parameter", ""), row.get("effective_from", ""))
        if key in rate_keys:
            errors.append(f"{label}: duplicate statutory rate version")
        rate_keys.add(key)
        rate_names.add(key[0])
        value = _decimal(row.get("value", ""), f"{label} value", errors)
        _date(key[1], f"{label} effective_from", errors)
        _date(row.get("effective_to", ""), f"{label} effective_to", errors, optional=True)
        if value is not None and value < 0:
            errors.append(f"{label}: value cannot be negative")
        if row.get("unit", "").casefold().startswith("percent") and value is not None and value > 100:
            errors.append(f"{label}: percentage cannot exceed 100")
    missing_rates = REQUIRED_STATUTORY_PARAMETERS - rate_names
    if files["statutory_rates.csv"] and missing_rates:
        errors.append("statutory_rates.csv: missing required payroll parameters: " +
                      ", ".join(sorted(missing_rates)))

    return {"directory": str(directory.resolve()), "row_counts": {name: len(rows) for name, rows in files.items()},
            "sample_rows": sample_rows, "unapproved_rows": unapproved_rows,
            "production_ready": not errors and sample_rows == 0,
            "database_changed": False, "errors": errors,
            "message": "Preview only; this command never writes or activates configuration."}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("data"))
    args = parser.parse_args()
    result = preview_bundle(args.directory)
    print(json.dumps(result, indent=2))
    return 0 if not result["errors"] and result["production_ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
