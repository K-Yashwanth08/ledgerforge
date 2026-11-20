import smoke_test


class FakeResponse:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


def test_smoke_test_checks_health_login_and_calculation_without_printing_secrets(monkeypatch, capsys):
    for name, value in {
        "LEDGERFORGE_BASE_URL": "https://example.test",
        "LEDGERFORGE_SMOKE_USERNAME": "hr@example.test",
        "LEDGERFORGE_SMOKE_PASSWORD": "Sensitive-pass-123!",
        "LEDGERFORGE_SMOKE_EMPLOYEE_ID": "EMP-SECRET-ID",
        "LEDGERFORGE_SMOKE_MONTH": "2025-04",
    }.items():
        monkeypatch.setenv(name, value)

    class FakeClient:
        def __init__(self, **_kwargs):
            self.calls = []

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url, **kwargs):
            self.calls.append(("GET", url, kwargs))
            return FakeResponse(200, {"status": "ok"})

        def post(self, url, **kwargs):
            self.calls.append(("POST", url, kwargs))
            return FakeResponse(200, {"access_token": "secret-token"})

    monkeypatch.setattr(smoke_test.httpx, "Client", FakeClient)
    original_get = FakeClient.get

    def get_with_calculation(self, url, **kwargs):
        if "/payroll/calculate/" in url:
            return FakeResponse(200, {"employee_id": "EMP-SECRET-ID", "month": "2025-04",
                                     "gross_pay": "100", "total_deductions": "20", "net_pay": "80"})
        return original_get(self, url, **kwargs)

    monkeypatch.setattr(FakeClient, "get", get_with_calculation)
    assert smoke_test.main() == 0
    output = capsys.readouterr().out
    assert "PASS health" in output
    assert "PASS login" in output
    assert "PASS payroll calculation" in output
    assert all(secret not in output for secret in ("Sensitive-pass", "secret-token", "EMP-SECRET-ID", "100"))


def test_smoke_test_rejects_missing_environment(monkeypatch, capsys):
    for name in ("LEDGERFORGE_BASE_URL", "LEDGERFORGE_SMOKE_USERNAME", "LEDGERFORGE_SMOKE_PASSWORD",
                 "LEDGERFORGE_SMOKE_EMPLOYEE_ID", "LEDGERFORGE_SMOKE_MONTH"):
        monkeypatch.delenv(name, raising=False)
    assert smoke_test.main() == 1
    assert "LEDGERFORGE_BASE_URL" in capsys.readouterr().err
