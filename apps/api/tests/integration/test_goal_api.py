from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from test_auth import Harness
from test_auth import auth as shared_auth
from test_imports import BASE, HEADER, finalize_headers, setup, upload

pytestmark = pytest.mark.integration
auth_fixture = shared_auth


@pytest.fixture
def auth(auth_fixture: Harness) -> Harness:
    return auth_fixture


def test_goal_create_update_replay_currency_month_and_owner(auth: Harness) -> None:
    assert auth.client.get("/api/v1/goals").status_code == 401
    headers = {"X-CSRF-Token": setup(auth)["X-CSRF-Token"]}
    body = dict(month="2026-09", currency="AED", kind="spending", target="7000", active=True)
    for _ in range(2):
        assert auth.client.put("/api/v1/goals", json=body, headers=headers).status_code == 204

    def read() -> list[dict[str, object]]:
        return list(auth.client.get("/api/v1/goals?month=2026-09").json()["goals"])

    assert len(read()) == 1
    assert read()[0]["target"] == "7000.0000"
    assert (
        auth.client.put(
            "/api/v1/goals", json={**body, "target": "6500", "active": False}, headers=headers
        ).status_code
        == 204
    )
    original_session = str(auth.client.cookies["ledgerx_session"])
    assert read()[0]["status"] == "Inactive"
    for changes in ({"kind": "net_cash_flow", "target": "2000"}, {"currency": "USD"}):
        assert (
            auth.client.put("/api/v1/goals", json={**body, **changes}, headers=headers).status_code
            == 204
        )
    assert len(read()) == 3
    assert auth.client.get("/api/v1/goals?month=2026-08").json()["goals"] == []
    assert auth.client.put("/api/v1/goals", json=body).status_code == 403
    assert (
        auth.client.put(
            "/api/v1/goals", json={**body, "user_id": "foreign"}, headers=headers
        ).status_code
        == 422
    )
    auth.register("goals-other@example.com")
    auth.login("goals-other@example.com")
    assert read() == []
    key = {k: body[k] for k in ("month", "currency", "kind")}
    assert (
        auth.client.request(
            "DELETE", "/api/v1/goals", json=key, headers={"X-CSRF-Token": auth.csrf()}
        ).status_code
        == 204
    )
    assert (
        auth.client.put(
            "/api/v1/goals", json=body, headers={"X-CSRF-Token": auth.csrf()}
        ).status_code
        == 204
    )
    assert len(read()) == 1
    for _ in range(2):
        assert (
            auth.client.request(
                "DELETE", "/api/v1/goals", json=key, headers={"X-CSRF-Token": auth.csrf()}
            ).status_code
            == 204
        )
    assert read() == []
    auth.use(original_session)
    assert len(read()) == 3
    assert (
        next(g for g in read() if g["kind"] == "spending" and g["currency"] == "AED")["target"]
        == "6500.0000"
    )


def test_forecast_uses_finalized_owned_imports_and_selected_month(auth: Harness) -> None:
    headers = setup(auth)
    batch = upload(
        auth,
        headers,
        HEADER
        + (
            b"2026-06-20,Netflix,-100,AED\n2026-07-20,Netflix,-100,AED\n"
            b"2026-08-20,Netflix,-100,AED\n2026-09-02,Carrefour,-150,AED\n"
            b"2026-09-02,Carrefour,-50,USD\n2026-09-25,Carrefour,-900,AED\n"
        ),
    )
    with patch("ledgerx.modules.goals.service.datetime") as clock:
        clock.now.return_value = datetime(2026, 9, 15, tzinfo=UTC)
        assert auth.client.get("/api/v1/goals").json()["currencies"] == []
        assert (
            auth.client.post(
                f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
            ).status_code
            == 200
        )
        data = auth.client.get("/api/v1/goals").json()
        aed, usd = data["currencies"]
        assert data["month"] == "2026-09"
        assert aed["projected_spending"] == "400.0000"
        assert usd["projected_spending"] == "100.0000"
        assert aed["remaining_recurring"] == "100.0000"
        assert usd["remaining_recurring"] == "0.0000"
        past = auth.client.get("/api/v1/goals?month=2026-08").json()["currencies"][0]
        assert past["state"] == "historical" and past["projected_spending"] == "100.0000"
