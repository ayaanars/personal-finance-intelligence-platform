"""Phase 8 behavior on real migrated PostgreSQL; all source data is synthetic."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session
from test_auth import Harness
from test_auth import auth as shared_auth

from ledgerx.modules.imports import service

pytestmark = pytest.mark.integration
HEADER = b"transaction_date,description,amount,currency\n"
CSV = HEADER + b"2026-09-01,Synthetic salary,+1234.5678,AED\n2026-09-02,Synthetic shop,-12.50,USD\n"
BASE = "/api/v1/imports"
auth_fixture = shared_auth


@pytest.fixture
def auth(auth_fixture: Harness) -> Harness:
    return auth_fixture


def setup(auth: Harness) -> dict[str, str]:
    auth.register()
    auth.login()
    return {
        "Content-Type": "text/csv",
        "X-Filename": "synthetic.csv",
        "X-CSRF-Token": auth.csrf(),
        "Idempotency-Key": str(uuid4()),
    }


def upload(auth: Harness, headers: dict[str, str], content: bytes = CSV) -> str:
    response = auth.client.post(BASE, content=content, headers=headers)
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def finalize_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-CSRF-Token": headers["X-CSRF-Token"],
        "Idempotency-Key": str(uuid4()),
    }


def test_preview_finalize_exact_facts_and_retry(auth: Harness) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers)
    preview = auth.client.get(f"{BASE}/{batch_id}").json()
    assert preview["status"] == "ready" and preview["can_finalize"]
    assert (preview["total_rows"], preview["valid_rows"], preview["invalid_rows"]) == (2, 2, 0)
    assert preview["currencies"] == ["AED", "USD"]
    assert preview["period_start"] == "2026-09-01" and preview["period_end"] == "2026-09-02"
    assert [row["amount"] for row in preview["rows"]["items"]] == ["1234.5678", "-12.5000"]
    assert datetime.fromisoformat(
        preview["expires_at"].replace("Z", "+00:00")
    ) - datetime.fromisoformat(preview["created_at"].replace("Z", "+00:00")) == timedelta(hours=24)
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0
        assert db.scalar(text("SELECT count(*) FROM import_rows")) == 2
    assert upload(auth, headers) == batch_id
    final_headers = finalize_headers(headers)
    response = auth.client.post(f"{BASE}/{batch_id}/finalize", json={}, headers=final_headers)
    assert response.status_code == 200, response.text
    assert response.json()["accepted_rows"] == 2
    retry = auth.client.post(f"{BASE}/{batch_id}/finalize", json={}, headers=final_headers)
    assert retry.json() == response.json()
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 2
        assert db.scalar(text("SELECT count(*) FROM import_rows")) == 0
        assert db.scalar(text("SELECT count(*) FROM import_audit_events")) == 2
        amounts = (
            db.execute(text("SELECT amount FROM imported_transactions ORDER BY source_row_number"))
            .scalars()
            .all()
        )
        assert amounts == [Decimal("1234.5678"), Decimal("-12.5000")]
    complete = auth.client.get(f"{BASE}/{batch_id}").json()
    assert not complete["can_finalize"] and complete["accepted_rows"] == 2
    assert complete["rows"] == preview["rows"]


@pytest.mark.parametrize(
    "bad_row,code",
    [
        (b"bad,Synthetic,1,AED\n", "DATE_INVALID"),
        (b"2026-09-01,Synthetic,1.00001,AED\n", "AMOUNT_INVALID"),
        (b"2026-09-01,Synthetic,1,JPY\n", "CURRENCY_UNSUPPORTED"),
        (b"2026-09-01,,1,AED\n", "DESCRIPTION_INVALID"),
        (b"missing,columns\n", "COLUMN_COUNT_INVALID"),
    ],
)
def test_any_invalid_row_blocks_every_transaction(auth: Harness, bad_row: bytes, code: str) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers, CSV + bad_row)
    view = auth.client.get(f"{BASE}/{batch_id}").json()
    assert (view["total_rows"], view["valid_rows"], view["invalid_rows"]) == (3, 2, 1)
    assert view["status"] == "invalid" and not view["can_finalize"]
    row = view["rows"]["items"][2]
    assert row["source_row_number"] == 4 and row["errors"][0]["code"] == code
    assert row["description"] is None and row["amount"] is None
    assert (
        auth.client.post(
            f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 409
    )
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0


def test_ownership_and_csrf_for_all_routes(auth: Harness) -> None:
    headers = setup(auth)
    token = str(auth.client.cookies["ledgerx_session"])
    batch_id = upload(auth, headers)
    auth.register("other@example.com")
    auth.login("other@example.com")
    other_csrf = auth.csrf()
    for suffix in ("", "/rows"):
        other = auth.client.get(f"{BASE}/{batch_id}{suffix}")
        missing = auth.client.get(f"{BASE}/{uuid4()}{suffix}")
        assert other.status_code == missing.status_code == 404
        assert other.json()["error"]["code"] == missing.json()["error"]["code"]
    other_headers = {"X-CSRF-Token": other_csrf, "Idempotency-Key": str(uuid4())}
    assert (
        auth.client.post(f"{BASE}/{batch_id}/finalize", json={}, headers=other_headers).status_code
        == 404
    )
    assert auth.client.post(BASE, content=CSV, headers=headers).status_code == 403
    auth.client.cookies.clear()
    assert auth.client.post(BASE, content=CSV, headers=headers).status_code == 401
    assert auth.client.get(f"{BASE}/{batch_id}").status_code == 401
    assert (
        auth.client.post(f"{BASE}/{batch_id}/finalize", json={}, headers=other_headers).status_code
        == 401
    )
    auth.use(token)
    for csrf in ("", "bad", other_csrf):
        bad = {**headers, "X-CSRF-Token": csrf}
        assert auth.client.post(BASE, content=CSV, headers=bad).status_code == 403
        assert (
            auth.client.post(
                f"{BASE}/{batch_id}/finalize", json={}, headers={**finalize_headers(bad)}
            ).status_code
            == 403
        )


@pytest.mark.parametrize(
    "content,status",
    [
        (b"", 422),
        (HEADER, 422),
        (b"date,amount\n", 422),
        (CSV + b'"unclosed', 422),
        (HEADER + b"\xff", 422),
        (HEADER + b"\x00", 422),
        (b"x" * (5 * 1024 * 1024 + 1), 413),
        (HEADER + b"2026-09-01,Synthetic,1,AED\n" * 25001, 413),
    ],
    ids=["empty", "header-only", "columns", "quoting", "encoding", "nul", "bytes", "rows"],
)
def test_file_failure_leaves_no_staging(auth: Harness, content: bytes, status: int) -> None:
    headers = setup(auth)
    response = auth.client.post(BASE, content=content, headers=headers)
    assert response.status_code == status, response.text
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM statement_imports")) == 0
        assert db.scalar(text("SELECT count(*) FROM import_rows")) == 0


def test_idempotency_keys_are_owner_and_operation_scoped(auth: Harness) -> None:
    headers = setup(auth)
    first = upload(auth, headers)
    assert auth.client.post(BASE, content=CSV + b"\n", headers=headers).status_code == 409
    second = upload(auth, {**headers, "Idempotency-Key": str(uuid4())})
    finals = finalize_headers(headers)
    assert auth.client.post(f"{BASE}/{first}/finalize", json={}, headers=finals).status_code == 200
    assert auth.client.post(f"{BASE}/{second}/finalize", json={}, headers=finals).status_code == 409
    assert (
        auth.client.post(
            f"{BASE}/{first}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 409
    )
    auth.register("other@example.com")
    auth.login("other@example.com")
    assert upload(auth, {**headers, "X-CSRF-Token": auth.csrf()}) != first


def test_repeated_transactions_and_bounded_pagination(auth: Harness) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers, HEADER + b"2026-09-01,Synthetic,1,AED\n" * 103)
    first = auth.client.get(f"{BASE}/{batch_id}").json()["rows"]
    assert len(first["items"]) == 50 and first["next_after_row"] == 51
    second = auth.client.get(f"{BASE}/{batch_id}/rows?after_row=51&limit=100").json()
    assert len(second["items"]) == 53 and second["next_after_row"] is None
    assert second["items"][0]["source_row_number"] == 52
    assert auth.client.get(f"{BASE}/{batch_id}/rows?limit=101").status_code == 422
    assert (
        auth.client.post(
            f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 103
        assert (
            db.scalar(text("SELECT count(DISTINCT fingerprint) FROM imported_transactions")) == 103
        )


def test_expiry_hides_staging_blocks_finalize_and_cleanup_is_repeatable(auth: Harness) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers)
    with auth.engine.connect() as db:
        expiry = db.scalar(text("SELECT expires_at FROM statement_imports"))
    with patch.object(service, "utcnow", return_value=expiry):
        response = auth.client.get(f"{BASE}/{batch_id}")
        assert response.json()["status"] == "expired" and not response.json()["can_finalize"]
        assert response.json()["rows"]["items"] == []
        assert auth.client.get(f"{BASE}/{batch_id}/rows").json()["items"] == []
        assert (
            auth.client.post(
                f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
            ).status_code
            == 409
        )
        with Session(auth.engine) as session, session.begin():
            assert service.purge_expired(session, limit=100, correlation_id=uuid4()) == 1
        with Session(auth.engine) as session, session.begin():
            assert service.purge_expired(session, limit=100, correlation_id=uuid4()) == 0
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM import_rows")) == 0
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0
        assert db.scalar(text("SELECT status FROM statement_imports")) == "expired"


def test_concurrent_finalize_requests_create_one_result(auth: Harness) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers)
    token = str(auth.client.cookies["ledgerx_session"])
    finals = finalize_headers(headers)
    barrier = Barrier(2)

    def run() -> tuple[int, object]:
        with TestClient(auth.app) as client:
            client.cookies.set("ledgerx_session", token, domain="testserver.local", path="/")
            barrier.wait(timeout=10)
            response = client.post(f"{BASE}/{batch_id}/finalize", json={}, headers=finals)
            return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert results[0] == results[1] and results[0][0] == 200, results
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 2


@pytest.mark.parametrize("table", ["import_rows", "imported_transactions", "import_audit_events"])
def test_injected_failures_roll_back_the_whole_operation(auth: Harness, table: str) -> None:
    headers = setup(auth)
    if table == "import_rows":
        with auth.engine.begin() as db:
            db.execute(text("ALTER TABLE import_rows ADD CONSTRAINT forced_failure CHECK(false)"))
        assert auth.client.post(BASE, content=CSV, headers=headers).status_code == 500
        with auth.engine.connect() as db:
            assert db.scalar(text("SELECT count(*) FROM statement_imports")) == 0
    else:
        batch_id = upload(auth, headers)
        with auth.engine.begin() as db:
            clause = "false" if table == "imported_transactions" else "event_code <> 'finalized'"
            db.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT forced_failure CHECK({clause})"))
        response = auth.client.post(
            f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
        )
        assert response.status_code == 500 and "forced_failure" not in response.text
        with auth.engine.connect() as db:
            assert db.scalar(text("SELECT status FROM statement_imports")) == "ready"
            assert db.scalar(text("SELECT count(*) FROM import_rows")) == 2
            assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0


@pytest.mark.parametrize(
    "assignment",
    [
        "currency='JPY'",
        "amount=0",
        "amount='NaN'::numeric",
        "fingerprint=decode('00','hex')",
        "source_row_number=1",
        "user_id=gen_random_uuid()",
        "description=''",
        "errors=ARRAY['DATE_INVALID']::varchar[]",
    ],
)
def test_staging_constraints(auth: Harness, assignment: str) -> None:
    upload(auth, setup(auth))
    with auth.engine.begin() as db, pytest.raises(IntegrityError):
        db.execute(text(f"UPDATE import_rows SET {assignment}"))


def test_workspace_owner_fk_and_staging_source_uniqueness(auth: Harness) -> None:
    headers = setup(auth)
    upload(auth, headers)
    profile = auth.register("other@example.com")
    with auth.engine.begin() as db, pytest.raises(IntegrityError):
        db.execute(text("UPDATE statement_imports SET user_id=:other"), {"other": profile["id"]})
    with auth.engine.begin() as db, pytest.raises(IntegrityError):
        db.execute(text("UPDATE import_rows SET source_row_number=2"))


def test_fact_and_audit_immutability_and_completion_constraints(auth: Harness) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers)
    with pytest.raises(DBAPIError), auth.engine.begin() as db:
        db.execute(
            text(
                "UPDATE statement_imports SET status='completed', "
                "finalized_at=clock_timestamp(), finalize_key=gen_random_uuid()"
            )
        )
    assert (
        auth.client.post(
            f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    for table in ("imported_transactions", "import_audit_events"):
        for command in (f"UPDATE {table} SET id=id", f"DELETE FROM {table}", f"TRUNCATE {table}"):
            with auth.engine.begin() as db, pytest.raises(DBAPIError):
                db.execute(text(command))
    with auth.engine.begin() as db, pytest.raises(DBAPIError):
        db.execute(
            text(
                "UPDATE statement_imports SET status='ready', finalized_at=NULL, finalize_key=NULL"
            )
        )


def test_no_raw_storage_or_sensitive_logs(auth: Harness, caplog: pytest.LogCaptureFixture) -> None:
    headers = setup(auth)
    # Any attempt by our upload pipeline to open a file would fail.
    with patch("builtins.open", side_effect=AssertionError("No raw file writes")):
        batch_id = upload(auth, headers)
    with auth.engine.connect() as db:
        batch = db.execute(text("SELECT * FROM statement_imports")).mappings().one()
        assert not any("filename" in key or "raw" in key or "content" in key for key in batch)
        assert len(batch["file_sha256"]) == 32
    assert "Synthetic salary" not in caplog.text and "synthetic.csv" not in caplog.text
    assert "1234.5678" not in caplog.text
    assert auth.client.get(f"{BASE}/{batch_id}").headers["cache-control"] == "no-store"


def test_upload_origin_media_unknown_body_and_openapi(auth: Harness) -> None:
    headers = setup(auth)
    for changes, status in [
        ({"Origin": "https://evil.example"}, 403),
        ({"Content-Type": "application/json"}, 415),
        ({"X-Filename": "../bad.csv"}, 422),
        ({"Idempotency-Key": "not-a-uuid"}, 422),
    ]:
        assert (
            auth.client.post(BASE, content=CSV, headers={**headers, **changes}).status_code
            == status
        )
    batch_id = upload(auth, headers)
    assert (
        auth.client.post(
            f"{BASE}/{batch_id}/finalize",
            json={"skip_invalid": True},
            headers=finalize_headers(headers),
        ).status_code
        == 422
    )
    schema = auth.app.openapi()
    assert "text/csv" in schema["paths"][BASE]["post"]["requestBody"]["content"]


def test_maximum_row_count_can_be_staged_and_finalized(auth: Harness) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers, HEADER + b"2026-09-01,Synthetic,0.0001,GBP\n" * 25000)
    response = auth.client.post(
        f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
    )
    assert response.status_code == 200, response.text
    assert response.json()["accepted_rows"] == 25000


def test_precision_extremes_and_all_currencies_roundtrip(auth: Harness) -> None:
    headers = setup(auth)
    content = HEADER + b"".join(
        f"2026-09-01,Synthetic,{amount},{currency}\n".encode()
        for amount, currency in [
            ("9999999999999999.9999", "AED"),
            ("-9999999999999999.9999", "USD"),
            ("0.0001", "EUR"),
            ("-0.0001", "GBP"),
        ]
    )
    batch_id = upload(auth, headers, content)
    before = auth.client.get(f"{BASE}/{batch_id}").json()
    assert (
        auth.client.post(
            f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    after = auth.client.get(f"{BASE}/{batch_id}").json()
    assert before["rows"] == after["rows"]
    assert [row["amount"] for row in after["rows"]["items"]] == [
        "9999999999999999.9999",
        "-9999999999999999.9999",
        "0.0001",
        "-0.0001",
    ]
    assert after["currencies"] == ["AED", "EUR", "GBP", "USD"]


def test_expiry_during_finalize_rolls_back_copied_facts(auth: Harness) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers)
    with auth.engine.connect() as db:
        expiry = db.scalar(text("SELECT expires_at FROM statement_imports"))
    with patch.object(service, "utcnow", side_effect=[expiry - timedelta(seconds=1), expiry]):
        response = auth.client.post(
            f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
        )
    assert response.status_code == 409
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0
        assert db.scalar(text("SELECT count(*) FROM import_rows")) == 2
        assert db.scalar(text("SELECT status FROM statement_imports")) == "ready"


def test_missing_staging_is_never_partially_finalized(auth: Harness) -> None:
    headers = setup(auth)
    batch_id = upload(auth, headers)
    with auth.engine.begin() as db:
        db.execute(text("DELETE FROM import_rows WHERE source_row_number=2"))
    response = auth.client.post(
        f"{BASE}/{batch_id}/finalize", json={}, headers=finalize_headers(headers)
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "IMPORT_INTEGRITY_ERROR"
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0


def test_concurrent_upload_with_same_key_creates_one_batch(auth: Harness) -> None:
    headers = setup(auth)
    token = str(auth.client.cookies["ledgerx_session"])
    barrier = Barrier(2)

    def run() -> str:
        with TestClient(auth.app) as client:
            client.cookies.set("ledgerx_session", token, domain="testserver.local", path="/")
            barrier.wait(timeout=10)
            response = client.post(BASE, content=CSV, headers=headers)
            assert response.status_code == 201, response.text
            return str(response.json()["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run) for _ in range(2)]
        assert futures[0].result(timeout=20) == futures[1].result(timeout=20)
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM statement_imports")) == 1
        assert db.scalar(text("SELECT count(*) FROM import_rows")) == 2


def test_cleanup_skips_locked_batches_and_preserves_other_states(auth: Harness) -> None:
    headers = setup(auth)
    pending_id = upload(auth, headers)
    completed_id = upload(auth, {**headers, "Idempotency-Key": str(uuid4())})
    assert (
        auth.client.post(
            f"{BASE}/{completed_id}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 200
    )
    with auth.engine.connect() as db:
        expiry = db.scalar(text("SELECT max(expires_at) FROM statement_imports"))
    with auth.engine.begin() as locked:
        locked.execute(
            text("SELECT id FROM statement_imports WHERE id=:id FOR UPDATE"), {"id": pending_id}
        )
        with patch.object(service, "utcnow", return_value=expiry):
            with Session(auth.engine) as session, session.begin():
                assert service.purge_expired(session, limit=100, correlation_id=uuid4()) == 0
    with patch.object(service, "utcnow", return_value=expiry):
        with Session(auth.engine) as session, session.begin():
            assert service.purge_expired(session, limit=100, correlation_id=uuid4()) == 1
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 2


def test_database_rejects_unfinalized_fact_inserts(auth: Harness) -> None:
    upload(auth, setup(auth))
    with pytest.raises(DBAPIError), auth.engine.begin() as db:
        db.execute(
            text(
                "INSERT INTO imported_transactions "
                "(user_id, import_id, source_row_number, transaction_date, description, "
                "amount, currency, fingerprint) SELECT user_id, import_id, source_row_number, "
                "transaction_date, description, amount, currency, fingerprint FROM import_rows"
            )
        )


def test_missing_keys_unsupported_adapter_rotated_csrf_and_cors(auth: Harness) -> None:
    headers = setup(auth)
    assert (
        auth.client.post(
            BASE, content=CSV, headers={k: v for k, v in headers.items() if k != "Idempotency-Key"}
        ).status_code
        == 422
    )
    assert (
        auth.client.post(
            BASE + "?parser_code=unverified-bank", content=CSV, headers=headers
        ).status_code
        == 422
    )
    batch_id = upload(auth, headers)
    assert (
        auth.client.post(
            f"{BASE}/{batch_id}/finalize",
            json={},
            headers={"X-CSRF-Token": headers["X-CSRF-Token"]},
        ).status_code
        == 422
    )
    auth.csrf()
    assert auth.client.post(BASE, content=CSV, headers=headers).status_code == 403
    response = auth.client.options(
        BASE,
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": (
                "content-type,x-filename,x-csrf-token,idempotency-key"
            ),
        },
    )
    assert response.status_code == 200
