"""Inspect supplied vendor/expense data and reconcile payroll to the ledger."""
import argparse
import json
import sys
from pathlib import Path

from app.config import settings
from scripts.phase3_input_validation import validate_phase3_inputs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=settings.data_dir, help="Directory containing Phase 3 CSV files")
    parser.add_argument("--json", dest="json_path", help="Also write the report to this JSON file")
    args = parser.parse_args()
    report = validate_phase3_inputs(Path(args.data))
    encoded = json.dumps(report, indent=2, sort_keys=True)
    print(encoded)
    if args.json_path:
        path = Path(args.json_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded + "\n", encoding="utf-8")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
