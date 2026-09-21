import pytest
from test_auth import Harness
from test_auth import auth as shared_auth
from test_imports import BASE, finalize_headers, setup, upload

pytestmark = pytest.mark.integration
auth_fixture = shared_auth


@pytest.fixture
def auth(auth_fixture: Harness) -> Harness:
    return auth_fixture


def test_first_month_reports_and_ownership(auth: Harness) -> None:
    headers = setup(auth)
    data = (
        b"transaction_date,description,amount,currency\n"
        + b"".join(
            f"2026-09-{i:02},Carrefour,{-100 if i == 6 else -10},AED\n".encode()
            for i in range(1, 7)
        )
        + b"2026-09-01,Salary,2000,AED\n2026-09-02,Netflix,-20,USD\n"
    )
    batch = upload(auth, headers, data)
    assert (
        auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    endpoint = "/api/v1/analytics/"
    intel = auth.client.get(endpoint + "intelligence?month=2026-09").json()
    assert intel["available_months"] == ["2026-09"]
    aed, usd = intel["currencies"]
    assert aed["totals"]["spending"] == "150.0000" and usd["totals"]["spending"] == "20.0000"
    assert aed["comparison"]["metrics"] == [] and aed["insights"] == []
    assert aed["behaviour"]["spending_count"] == 6
    assert aed["recurring"]["candidates"][0]["observed_months"] == 1
    unusual = auth.client.get(endpoint + "unusual?month=2026-09").json()
    assert unusual["currencies"][0]["items"][0]["basis"] == "current_month"
    assert unusual["currencies"][1]["items"] == []
    relations = auth.client.get(endpoint + "relationships?month=2026-09").json()
    assert relations["currencies"][0]["state"] == "insufficient_history"
    auth.register("other-first-month@example.com")
    auth.login("other-first-month@example.com")
    for route in ("intelligence", "unusual", "relationships"):
        assert auth.client.get(endpoint + route + "?month=2026-09").json()["currencies"] == []
