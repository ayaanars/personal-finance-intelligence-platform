"""Phase 9 API, integrity and ownership checks on disposable PostgreSQL schemas."""

from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from test_auth import Harness
from test_auth import auth as shared_auth
from test_imports import BASE, HEADER, finalize_headers, setup, upload

pytestmark = pytest.mark.integration
auth_fixture = shared_auth
TX = "/api/v1/transactions"


@pytest.fixture
def auth(auth_fixture: Harness) -> Harness:
    return auth_fixture


def finalized(auth: Harness, count: int = 2) -> tuple[dict[str, str], list[dict[str, object]]]:
    headers = setup(auth)
    batch = upload(auth, headers, HEADER + b"2026-09-01,  Carrefour MOE  ,-12.3456,AED\n" * count)
    response = auth.client.post(
        f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
    )
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": headers["X-CSRF-Token"]}, auth.client.get(TX).json()["items"]


def test_facts_enrichment_and_pagination(auth: Harness) -> None:
    _, items = finalized(auth, 3)
    assert len(items) == 3 and len({str(item["id"]) for item in items}) == 3
    for item in items:
        assert item["raw_description"] == "  Carrefour MOE  "
        assert item["normalized_description"] == "CARREFOUR MOE"
        assert item["merchant"] == "Carrefour"
        assert item["category"] == "Groceries"
        assert item["amount"] == "-12.3456" and item["currency"] == "AED"
        assert item["transaction_date"] == "2026-09-01"
        assert item["categorization_source"] == "merchant_rule"
        assert item["categorization_reason"] == "Merchant matched Carrefour rule."
        assert item["version"] == 1 and item["enrichment_persisted"] is True
        response = auth.client.get(f"{TX}/{item['id']}")
        assert response.json() == item and response.headers["cache-control"] == "no-store"
    seen: list[str] = []
    cursor = None
    while True:
        response = auth.client.get(
            TX, params={"limit": 1, **({"cursor": cursor} if cursor else {})}
        )
        assert response.status_code == 200
        page = response.json()
        seen.extend(item["id"] for item in page["items"])
        cursor = page["page"]["next_cursor"]
        if cursor is None:
            assert not page["page"]["has_more"]
            break
    assert seen == [item["id"] for item in items]
    for params in ({"limit": 0}, {"limit": 101}, {"cursor": "garbage"}):
        assert auth.client.get(TX, params=params).status_code == 422


def test_override_reprocess_clear_and_conflict(auth: Harness) -> None:
    headers, items = finalized(auth)
    identifier = items[0]["id"]
    endpoint = f"{TX}/{identifier}"
    response = auth.client.patch(
        endpoint + "/category",
        json={"category": "Education"},
        headers={**headers, "If-Match": '"1"'},
    )
    assert response.status_code == 200, response.text
    manual = response.json()
    assert manual["category"] == "Education" and manual["categorization_source"] == "manual"
    assert manual["automatic_category"] == "Groceries" and manual["version"] == 2
    assert (
        auth.client.patch(
            endpoint + "/category",
            json={"category": "Travel"},
            headers={**headers, "If-Match": '"1"'},
        ).status_code
        == 409
    )
    with patch("ledgerx.modules.transactions.service.RULE_VERSION", "understanding-v2"):
        response = auth.client.post(endpoint + "/reprocess", json={}, headers=headers)
        assert response.status_code == 200
        refreshed = response.json()
        assert refreshed["category"] == "Education" and refreshed["version"] == 3
        assert refreshed["rule_version"] == "understanding-v2"
        assert (
            auth.client.post(endpoint + "/reprocess", json={}, headers=headers).json() == refreshed
        )
    cleared = auth.client.patch(
        endpoint + "/category", json={"category": None}, headers={**headers, "If-Match": '"3"'}
    )
    assert cleared.status_code == 200
    assert cleared.json()["category"] == "Groceries"
    for key in ("amount", "currency", "transaction_date", "raw_description", "id"):
        assert cleared.json()[key] == items[0][key]
    assert auth.client.get(f"{TX}/{items[1]['id']}").json() == items[1]
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM transaction_audit_events")) == 3
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 2


def test_security_all_routes(auth: Harness) -> None:
    headers, items = finalized(auth)
    owner = str(auth.client.cookies["ledgerx_session"])
    endpoint = f"{TX}/{items[0]['id']}"
    for csrf in ("", "bad"):
        bad_headers = {"X-CSRF-Token": csrf, "If-Match": '"1"'}
        assert (
            auth.client.patch(
                endpoint + "/category", json={"category": "Travel"}, headers=bad_headers
            ).status_code
            == 403
        )
        assert (
            auth.client.post(endpoint + "/reprocess", json={}, headers=bad_headers).status_code
            == 403
        )
    for body in ({"category": "INVALID"}, {"category": "Income", "user_id": str(uuid4())}, {}):
        assert (
            auth.client.patch(
                endpoint + "/category", json=body, headers={**headers, "If-Match": '"1"'}
            ).status_code
            == 422
        )
    assert (
        auth.client.patch(
            endpoint + "/category", json={"category": "Income"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        auth.client.post(
            endpoint + "/reprocess",
            json={},
            headers={**headers, "Origin": "https://foreign.invalid"},
        ).status_code
        == 403
    )
    owner_cursor = auth.client.get(TX, params={"limit": 1}).json()["page"]["next_cursor"]
    auth.register("other@example.com")
    auth.login("other@example.com")
    foreign = {"X-CSRF-Token": auth.csrf(), "If-Match": '"1"'}
    assert auth.client.get(TX).json()["items"] == []
    assert auth.client.get(TX, params={"cursor": owner_cursor}).status_code == 422
    for candidate in (endpoint, f"{TX}/{uuid4()}"):
        assert auth.client.get(candidate).status_code == 404
        assert (
            auth.client.patch(
                candidate + "/category", json={"category": "Travel"}, headers=foreign
            ).status_code
            == 404
        )
        assert (
            auth.client.post(candidate + "/reprocess", json={}, headers=foreign).status_code == 404
        )
    auth.client.cookies.clear()
    assert auth.client.get(TX).status_code == 401
    assert auth.client.get(endpoint).status_code == 401
    assert (
        auth.client.patch(
            endpoint + "/category", json={"category": "Travel"}, headers=foreign
        ).status_code
        == 401
    )
    assert auth.client.post(endpoint + "/reprocess", json={}, headers=foreign).status_code == 401
    auth.use(owner)
    assert auth.client.get(endpoint).json() == items[0]


def test_enrichment_failure_rolls_back_finalization(auth: Harness) -> None:
    headers = setup(auth)
    batch = upload(auth, headers)
    with patch(
        "ledgerx.modules.transactions.service.understand", side_effect=RuntimeError("private")
    ):
        response = auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        )
    assert response.status_code == 500 and "private" not in response.text
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0
        assert db.scalar(text("SELECT count(*) FROM transaction_enrichments")) == 0
        assert db.scalar(text("SELECT count(*) FROM import_rows")) == 2
        assert db.scalar(text("SELECT status FROM statement_imports")) == "ready"
    assert (
        auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )


def test_legacy_fact_read_and_reprocess(auth: Harness) -> None:
    headers = setup(auth)
    batch = upload(auth, headers)
    # Simulate a Phase 8 writer: facts have no enrichment before deployment/backfill.
    with patch("ledgerx.modules.imports.service.enrich_import"):
        assert (
            auth.client.post(
                f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
            ).status_code
            == 200
        )
    items = auth.client.get(TX).json()["items"]
    assert all(not item["enrichment_persisted"] and item["version"] == 0 for item in items)
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM transaction_enrichments")) == 0
    response = auth.client.post(
        f"{TX}/{items[0]['id']}/reprocess",
        json={},
        headers={"X-CSRF-Token": headers["X-CSRF-Token"]},
    )
    assert response.status_code == 200 and response.json()["enrichment_persisted"]
    assert response.json()["version"] == 1


def test_concurrent_overrides_cannot_silently_replace(auth: Harness) -> None:
    headers, items = finalized(auth)
    token = str(auth.client.cookies["ledgerx_session"])

    def request(category: str) -> int:
        with TestClient(auth.app) as client:
            client.cookies.set("ledgerx_session", token)
            return client.patch(
                f"{TX}/{items[0]['id']}/category",
                json={"category": category},
                headers={**headers, "If-Match": '"1"'},
            ).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(request, ["Travel", "Education"])) == [200, 409]


def test_constraints_and_append_only_audit(auth: Harness) -> None:
    headers, items = finalized(auth)
    auth.register("other@example.com")
    with auth.engine.connect() as db:
        other = db.scalar(text("SELECT id FROM users WHERE email_normalized = 'other@example.com'"))
        with pytest.raises(IntegrityError):
            db.execute(
                text("UPDATE transaction_enrichments SET user_id = :other"), {"other": other}
            )
        db.rollback()
        with pytest.raises(IntegrityError):
            db.execute(text("UPDATE transaction_enrichments SET automatic_category = 'Invalid'"))
        db.rollback()
        with pytest.raises(DBAPIError):
            db.execute(text("UPDATE imported_transactions SET description = 'changed'"))
        db.rollback()
    assert (
        auth.client.patch(
            f"{TX}/{items[0]['id']}/category",
            json={"category": "Travel"},
            headers={**headers, "If-Match": '"1"'},
        ).status_code
        == 200
    )
    for sql in (
        "UPDATE transaction_audit_events SET event_code = 'reprocess'",
        "DELETE FROM transaction_audit_events",
        "TRUNCATE transaction_audit_events",
    ):
        with auth.engine.begin() as db, pytest.raises(DBAPIError):
            db.execute(text(sql))


def test_populated_migration_preserves_facts(auth: Harness) -> None:
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    finalized(auth)
    with auth.engine.begin() as db:
        facts = db.execute(text("SELECT * FROM imported_transactions ORDER BY id")).all()
        config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
        config.attributes["connection"] = db
        command.downgrade(config, "0004_csv_import")
        assert db.execute(text("SELECT * FROM imported_transactions ORDER BY id")).all() == facts
        command.upgrade(config, "head")
        command.check(config)
        assert db.execute(text("SELECT * FROM imported_transactions ORDER BY id")).all() == facts
        assert db.scalar(text("SELECT count(*) FROM transaction_enrichments")) == 0
    assert all(not item["enrichment_persisted"] for item in auth.client.get(TX).json()["items"])


def test_override_audit_failure_rolls_back(auth: Harness) -> None:
    headers, items = finalized(auth)
    endpoint = f"{TX}/{items[0]['id']}"
    with patch("ledgerx.modules.transactions.service.TransactionAudit", side_effect=RuntimeError):
        response = auth.client.patch(
            endpoint + "/category",
            json={"category": "Education"},
            headers={**headers, "If-Match": '"1"'},
        )
    assert response.status_code == 500
    assert auth.client.get(endpoint).json() == items[0]
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM transaction_audit_events")) == 0


def test_concurrent_reprocess_preserves_override(auth: Harness) -> None:
    headers, items = finalized(auth)
    endpoint = f"{TX}/{items[0]['id']}"
    token = str(auth.client.cookies["ledgerx_session"])

    def request(manual: bool) -> int:
        with TestClient(auth.app) as client:
            client.cookies.set("ledgerx_session", token)
            if manual:
                return client.patch(
                    endpoint + "/category",
                    json={"category": "Education"},
                    headers={**headers, "If-Match": '"1"'},
                ).status_code
            return client.post(endpoint + "/reprocess", json={}, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(request, [True, False])) == [200, 200]
    assert auth.client.get(endpoint).json()["category"] == "Education"
