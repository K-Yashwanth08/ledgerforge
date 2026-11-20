"""Check a deployed LedgerForge URL without printing credentials or payroll amounts."""
import os
import re
import sys
from decimal import Decimal, InvalidOperation
from urllib.parse import urljoin

import httpx


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable is missing: {name}")
    return value


def main() -> int:
    try:
        base_url = required("LEDGERFORGE_BASE_URL").rstrip("/") + "/"
        username = required("LEDGERFORGE_SMOKE_USERNAME")
        password = required("LEDGERFORGE_SMOKE_PASSWORD")
        employee_id = required("LEDGERFORGE_SMOKE_EMPLOYEE_ID")
        month = required("LEDGERFORGE_SMOKE_MONTH")
        if not re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", month):
            raise ValueError("LEDGERFORGE_SMOKE_MONTH must be a valid YYYY-MM month")

        with httpx.Client(timeout=30, follow_redirects=True) as client:
            health = client.get(urljoin(base_url, "api/v1/health"))
            if health.status_code != 200 or health.json().get("status") != "ok":
                raise RuntimeError("Health check failed")
            print("PASS health")

            login = client.post(urljoin(base_url, "api/v1/auth/login"),
                                json={"username": username, "password": password})
            if login.status_code != 200 or not login.json().get("access_token"):
                raise RuntimeError("Login failed; check the configured test account")
            token = login.json()["access_token"]
            print("PASS login")

            calculation = client.get(
                urljoin(base_url, f"api/v1/payroll/calculate/{employee_id}"),
                params={"month": month}, headers={"Authorization": f"Bearer {token}"})
            if calculation.status_code != 200:
                raise RuntimeError(f"Payroll calculation failed (HTTP {calculation.status_code})")
            result = calculation.json()
            if result.get("employee_id") != employee_id or result.get("month") != month:
                raise RuntimeError("Payroll response did not match the requested employee and period")
            for field in ("gross_pay", "total_deductions", "net_pay"):
                try:
                    amount = Decimal(str(result[field]))
                except (KeyError, InvalidOperation, TypeError) as exc:
                    raise RuntimeError("Payroll response is missing valid totals") from exc
                if not amount.is_finite():
                    raise RuntimeError("Payroll response contains a non-finite total")
            print(f"PASS payroll calculation ({month}; values hidden)")
        return 0
    except (ValueError, RuntimeError, httpx.HTTPError) as exc:
        print(f"FAIL {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
