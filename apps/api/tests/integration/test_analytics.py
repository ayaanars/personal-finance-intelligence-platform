"""Real imports, corrections, isolation and aggregation on migrated PostgreSQL."""

from uuid import uuid4

import pytest
from sqlalchemy import text
from test_auth import Harness
from test_auth import auth as shared_auth
from test_imports import BASE, HEADER, finalize_headers, setup, upload

pytestmark = pytest.mark.integration
auth_fixture = shared_auth
ENDPOINT = "/api/v1/analytics/overview"


@pytest.fixture
def auth(auth_fixture: Harness) -> Harness:
    return auth_fixture


def test_finalized_summary_legacy_override_window_and_isolation(auth: Harness) -> None:
    headers = setup(auth)
    csv = HEADER + (
        b"2026-01-01,Carrefour,-900,AED\n"
        b"2026-08-01,Salary,1000,AED\n2026-08-02,Carrefour,-100,AED\n"
        b"2026-09-01,Salary,2000,AED\n2026-09-02,Carrefour,-250,AED\n"
        b"2026-09-03,Carrefour refund,25,AED\n2026-09-04,Internal transfer,-200,AED\n"
        b"2026-09-05,ATM withdrawal,-50,AED\n2026-09-06,Unrecognized,-12.3456,USD\n"
    )
    batch = upload(auth, headers, csv)
    assert auth.client.get(ENDPOINT).json()["currencies"] == []
    assert (
        auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    response = auth.client.get(ENDPOINT)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["month"] == "2026-09" and data["window_start"] == "2026-04"
    assert data["available_months"] == ["2026-09", "2026-08", "2026-01"]
    aed, usd = data["currencies"]
    assert aed["totals"]["income"] == "2000.0000"
    assert aed["totals"]["outflow"] == "500.0000"
    assert aed["totals"]["net_cash_flow"] == "1525.0000"
    assert aed["totals"]["spending"] == "250.0000"
    assert aed["totals"]["other_inflows"] == "25.0000"
    assert aed["comparison"]["state"] == "available"
    assert usd["totals"]["spending"] == "12.3456"
    assert usd["comparison"]["state"] == "insufficient_history"
    assert len(aed["trend"]) == 2
    # Legacy fallback produces precisely the same analytics, without writes.
    with auth.engine.begin() as db:
        db.execute(text("DELETE FROM transaction_enrichments"))
    assert auth.client.get(ENDPOINT).json() == data
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM transaction_enrichments")) == 0
    items = auth.client.get("/api/v1/transactions").json()["items"]
    fact = next(item for item in items if item["amount"] == "-250.0000")
    changed = auth.client.patch(
        f"/api/v1/transactions/{fact['id']}/category",
        json={"category": "Transfers"},
        headers={"X-CSRF-Token": headers["X-CSRF-Token"], "If-Match": '"0"'},
    )
    assert changed.status_code == 200
    updated = auth.client.get(ENDPOINT).json()["currencies"][0]
    assert updated["totals"]["spending"] == "0.0000"
    assert updated["totals"]["outflow"] == "500.0000"
    assert updated["totals"]["transfers_out"] == "450.0000"
    assert (
        auth.client.get(ENDPOINT, params={"month": "2026-01"}).json()["currencies"][0]["totals"][
            "outflow"
        ]
        == "900.0000"
    )
    auth.register("other-analytics@example.com")
    auth.login("other-analytics@example.com")
    assert auth.client.get(ENDPOINT).json()["available_months"] == []
    assert auth.client.get(ENDPOINT, params={"month": "2026-09"}).json()["currencies"] == []


def test_auth_validation_empty_and_boundary_months(auth: Harness) -> None:
    assert auth.client.get(ENDPOINT).status_code == 401
    setup(auth)
    assert auth.client.get(ENDPOINT).json()["month"] is None
    for month in ("0000-01", "2026-13", "2026-00", "2026-9", "bad", "2026-09-01"):
        response = auth.client.get(ENDPOINT, params={"month": month})
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"
    for month in ("0001-01", "9999-12", "2026-09"):
        assert auth.client.get(ENDPOINT, params={"month": month}).status_code == 200
    assert auth.client.get(ENDPOINT, params={"user_id": str(uuid4())}).status_code == 422
    assert (
        auth.client.get(ENDPOINT, headers={"Origin": "https://foreign.invalid"}).status_code == 403
    )


def test_intelligence_date_details_legacy_and_owner_isolation(auth: Harness) -> None:
    endpoint = "/api/v1/analytics/intelligence"
    assert auth.client.get(endpoint).status_code == 401
    headers = setup(auth)
    batch = upload(
        auth,
        headers,
        HEADER
        + (
            b"2026-03-01,Salary,1000,AED\n2026-08-01,Carrefour,-100,AED\n"
            b"2026-09-05,Carrefour,-250,AED\n2026-09-06,Carrefour refund,25,AED\n"
            b"2026-09-07,Internal transfer,-20,AED\n2026-09-08,ATM withdrawal,-30,AED\n"
            b"2026-09-09,Amazon,-10,USD\n"
        ),
    )
    assert auth.client.get(endpoint).json()["currencies"] == []

    assert (
        auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    response = auth.client.get(endpoint)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    data = response.json()
    assert data["window_start"] == "2026-03"
    aed, usd = data["currencies"]
    assert aed["behaviour"]["average_purchase"] == "250.0000"
    assert aed["behaviour"]["return_inflows"] == "25.0000"
    assert usd["behaviour"]["average_purchase"] == "10.0000"
    with auth.engine.begin() as db:
        db.execute(text("DELETE FROM transaction_enrichments"))
    assert auth.client.get(endpoint).json() == data
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM transaction_enrichments")) == 0
    identifier = aed["behaviour"]["largest_purchases"][0]["identifier"]
    corrected = auth.client.patch(
        f"/api/v1/transactions/{identifier}/category",
        json={"category": "Transfers"},
        headers={"X-CSRF-Token": headers["X-CSRF-Token"], "If-Match": '"0"'},
    )
    assert corrected.status_code == 200
    revised = auth.client.get(endpoint).json()["currencies"][0]
    assert revised["behaviour"]["average_purchase"] is None
    assert revised["behaviour"]["largest_purchases"] == []
    assert revised["totals"]["outflow"] == aed["totals"]["outflow"]
    for month in ("0001-01", "9999-12"):
        assert auth.client.get(endpoint, params={"month": month}).status_code == 200
    assert auth.client.get(endpoint, params={"month": "0000-01"}).status_code == 422
    assert auth.client.get(endpoint, params={"owner": "foreign"}).status_code == 422
    assert (
        auth.client.get(endpoint, headers={"Origin": "https://foreign.invalid"}).status_code == 403
    )
    auth.register("other-intelligence@example.com")
    auth.login("other-intelligence@example.com")
    assert auth.client.get(endpoint).json()["currencies"] == []


def test_baselines_and_recurring_are_currency_specific_and_respect_corrections(
    auth: Harness,
) -> None:
    endpoint = "/api/v1/analytics/intelligence"
    headers = setup(auth)
    lines = [
        f"2026-{month:02d}-05,Netflix,-{value},{currency}\n"
        for month in range(3, 10)
        for currency, value in [("AED", 49), ("USD", 12)]
    ]
    batch = upload(auth, headers, HEADER + "".join(lines).encode())
    assert (
        auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    aed, usd = auth.client.get(endpoint).json()["currencies"]
    assert aed["baselines"]["metrics"][0]["mean"] == "49.0000"
    assert usd["baselines"]["metrics"][0]["mean"] == "12.0000"
    assert aed["recurring"]["annual_estimate"] == "588.0000"
    assert usd["recurring"]["annual_estimate"] == "144.0000"
    assert aed["recurring"]["payments"][0]["newly_qualified"] is False
    identifier = aed["recurring"]["payments"][0]["evidence"][-1]["identifier"]
    assert (
        auth.client.patch(
            f"/api/v1/transactions/{identifier}/category",
            json={"category": "Transfers"},
            headers={"X-CSRF-Token": headers["X-CSRF-Token"], "If-Match": '"1"'},
        ).status_code
        == 200
    )
    revised = auth.client.get(endpoint).json()["currencies"]
    assert revised[0]["recurring"]["payments"] == []
    assert revised[0]["baselines"]["metrics"][0]["position"] == "below"
    assert revised[1] == usd


def test_unusual_ml_owner_currency_and_corrected_fact_isolation(auth: Harness) -> None:
    endpoint = "/api/v1/analytics/unusual"
    assert auth.client.get(endpoint).status_code == 401
    headers = setup(auth)
    lines = [
        f"2026-{m:02d}-{i % 28 + 1:02d},Carrefour,-{10 + i},AED\n"
        for m in (6, 7, 8)
        for i in range(40)
    ]
    lines += ["2026-09-05,Amazon,-1000,AED\n", "2026-09-05,Amazon,-1000,USD\n"]
    batch = upload(auth, headers, HEADER + "".join(lines).encode())
    assert auth.client.get(endpoint).json()["currencies"] == []
    assert (
        auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    response = auth.client.get(endpoint)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    original = response.json()
    aed, usd = original["currencies"]
    assert aed["ml_state"] == "active" and aed["historical_purchases"] == 120
    assert usd["ml_state"] == "insufficient_history" and usd["items"] == []
    identifier = next(
        i["transaction_ids"][0]
        for i in aed["items"]
        if any(e["code"] == "large_purchase" for e in i["evidence"])
    )
    assert auth.client.get(endpoint, params={"user_id": str(uuid4())}).status_code == 422
    assert auth.client.get(endpoint, params={"month": "0000-01"}).status_code == 422
    for month in ("0001-01", "9999-12"):
        assert auth.client.get(endpoint, params={"month": month}).status_code == 200
    # A different owner's model/history cannot affect this owner's fitted result.
    first_session = str(auth.client.cookies["ledgerx_session"])
    auth.register("unusual-other@example.com")
    auth.login("unusual-other@example.com")
    assert auth.client.get(endpoint).json()["currencies"] == []
    assert auth.client.get(f"/api/v1/transactions/{identifier}").status_code == 404
    other_headers = {**headers, "X-CSRF-Token": auth.csrf(), "Idempotency-Key": str(uuid4())}
    other_batch = upload(
        auth, other_headers, HEADER + "".join(lines).replace("-1000", "-2").encode()
    )
    assert (
        auth.client.post(
            f"{BASE}/{other_batch}/finalize", json={}, headers=finalize_headers(other_headers)
        ).status_code
        == 200
    )
    assert auth.client.get(endpoint).json()["currencies"][0]["ml_state"] == "active"
    auth.use(first_session)
    assert auth.client.get(endpoint).json() == original
    detail = auth.client.get(f"/api/v1/transactions/{identifier}")
    assert (
        auth.client.patch(
            f"/api/v1/transactions/{identifier}/category",
            json={"category": "Transfers"},
            headers={"X-CSRF-Token": auth.csrf(), "If-Match": f'"{detail.json()["version"]}"'},
        ).status_code
        == 200
    )
    assert not auth.client.get(endpoint).json()["currencies"][0]["items"]
