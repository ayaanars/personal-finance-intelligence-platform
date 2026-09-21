"""Mapped uploads reuse real PostgreSQL staging and owner isolation."""

import json
from uuid import uuid4

import pytest
from sqlalchemy import text
from test_auth import Harness
from test_auth import auth as shared_auth
from test_imports import BASE, finalize_headers, setup

pytestmark = pytest.mark.integration
auth_fixture = shared_auth
CSV = b"Details,Date,Debit,Credit,Private unused\nSynthetic shop,03/04/2026,12.1234,,discard-me\n"
MAPPING = {
    "transaction_date": "Date",
    "description": "Details",
    "amount_mode": "debit_credit",
    "debit": "Debit",
    "credit": "Credit",
    "date_format": "DD/MM/YYYY",
    "fixed_currency": "AED",
}


@pytest.fixture
def auth(auth_fixture: Harness) -> Harness:
    return auth_fixture


def test_inspect_stage_profile_reuse_finalize_and_privacy(auth: Harness) -> None:
    headers = setup(auth)
    inspect = auth.client.post(BASE + "/inspect", content=CSV, headers=headers)
    assert inspect.status_code == 200, inspect.text
    assert inspect.json()["date_formats"] == ["DD/MM/YYYY", "MM/DD/YYYY"]
    assert inspect.json()["samples"][0]["normalized"] is None
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM statement_imports")) == 0
    headers["X-Column-Mapping"] = json.dumps(MAPPING)
    inspect = auth.client.post(BASE + "/inspect", content=CSV, headers=headers)
    assert inspect.json()["invalid_rows"] == 0
    normalized = inspect.json()["samples"][0]["normalized"]
    assert normalized["amount"] == "-12.1234" and normalized["transaction_date"] == "2026-04-03"
    staged = auth.client.post(BASE, content=CSV, headers=headers)
    assert staged.status_code == 201, staged.text
    batch = staged.json()["id"]
    assert auth.client.post(BASE, content=CSV, headers=headers).json()["id"] == batch
    changed = {**headers, "X-Column-Mapping": json.dumps({**MAPPING, "date_format": "MM/DD/YYYY"})}
    assert auth.client.post(BASE, content=CSV, headers=changed).status_code == 409
    save_headers = finalize_headers(headers)
    body = {"import_id": batch, "name": "Synthetic account CSV"}
    saved = auth.client.post(BASE + "/profiles", json=body, headers=save_headers)
    assert saved.status_code == 201, saved.text
    assert (
        auth.client.post(BASE + "/profiles", json=body, headers=save_headers).json() == saved.json()
    )
    reused = auth.client.post(BASE + "/inspect", content=CSV, headers=headers).json()
    assert reused["profiles"][0]["name"] == "Synthetic account CSV"
    assert reused["profiles"][0]["mapping"]["date_format"] == "DD/MM/YYYY"
    final = auth.client.post(f"{BASE}/{batch}/finalize", json={}, headers=save_headers)
    assert final.status_code == 200, final.text
    assert (
        auth.client.post(f"{BASE}/{batch}/finalize", json={}, headers=save_headers).json()
        == final.json()
    )
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 1
        assert db.scalar(text("SELECT count(*) FROM import_rows")) == 0
        assert "discard-me" not in str(db.execute(text("SELECT * FROM statement_imports")).all())
        assert "discard-me" not in str(
            db.execute(text("SELECT * FROM import_mapping_profiles")).all()
        )
        assert "03/04/2026" not in str(db.execute(text("SELECT * FROM statement_imports")).all())


def test_mapping_profile_ownership_and_incompatible_structure(auth: Harness) -> None:
    headers = setup(auth)
    headers["X-Column-Mapping"] = json.dumps(MAPPING)
    batch = auth.client.post(BASE, content=CSV, headers=headers).json()["id"]
    body = {"import_id": batch, "name": "Private mapping"}
    assert (
        auth.client.post(
            BASE + "/profiles", json=body, headers=finalize_headers(headers)
        ).status_code
        == 201
    )
    changed_structure = CSV.replace(b"Private unused", b"Other unused")
    assert (
        auth.client.post(BASE + "/inspect", content=changed_structure, headers=headers).json()[
            "profiles"
        ]
        == []
    )
    auth.register("other@example.com")
    auth.login("other@example.com")
    headers["X-CSRF-Token"] = auth.csrf()
    assert (
        auth.client.post(BASE + "/inspect", content=CSV, headers=headers).json()["profiles"] == []
    )
    assert (
        auth.client.post(
            BASE + "/profiles", json=body, headers=finalize_headers(headers)
        ).status_code
        == 404
    )
    assert auth.client.get(f"{BASE}/{batch}").status_code == 404
    assert auth.client.get(f"{BASE}/{batch}/rows").status_code == 404
    assert (
        auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 404
    )


def test_invalid_mapping_and_rows_fail_closed(auth: Harness) -> None:
    headers = setup(auth)
    headers["X-Column-Mapping"] = json.dumps({**MAPPING, "debit": "Credit"})
    assert auth.client.post(BASE, content=CSV, headers=headers).status_code == 422
    headers["X-Column-Mapping"] = json.dumps(MAPPING)
    bad = CSV + b"Invalid,03/04/2026,1,2,unused\n"
    staged = auth.client.post(BASE, content=bad, headers=headers)
    assert staged.status_code == 201, staged.text
    assert staged.json()["invalid_rows"] == 1
    batch = staged.json()["id"]
    assert (
        auth.client.post(
            f"{BASE}/{batch}/finalize", json={}, headers=finalize_headers(headers)
        ).status_code
        == 409
    )
    assert (
        auth.client.post(
            BASE + "/profiles",
            json={"import_id": batch, "name": "Invalid"},
            headers=finalize_headers(headers),
        ).status_code
        == 409
    )
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0
        assert db.scalar(text("SELECT count(*) FROM import_mapping_profiles")) == 0
    headers["Idempotency-Key"] = str(uuid4())
    headers["X-CSRF-Token"] = "invalid"
    assert auth.client.post(BASE + "/inspect", content=CSV, headers=headers).status_code == 403


def test_automatic_preview_and_saved_profile_application(auth: Harness) -> None:
    headers = setup(auth)
    content = b"CCY,Date,Details,Debit,Credit\nAED,2026-01-07,Synthetic,12.1234,\n"
    inspected = auth.client.post(BASE + "/inspect", content=content, headers=headers)
    assert inspected.status_code == 200, inspected.text
    result = inspected.json()
    assert result["recognition"]["state"] == "recognized"
    assert result["invalid_rows"] == 0
    assert result["samples"][0]["normalized"]["amount"] == "-12.1234"
    with auth.engine.connect() as db:
        assert db.scalar(text("SELECT count(*) FROM statement_imports")) == 0
        assert db.scalar(text("SELECT count(*) FROM imported_transactions")) == 0
    headers["X-Column-Mapping"] = json.dumps(MAPPING)
    batch = auth.client.post(BASE, content=CSV, headers=headers).json()["id"]
    assert (
        auth.client.post(
            BASE + "/profiles",
            json={"import_id": batch, "name": "Reviewed dates"},
            headers=finalize_headers(headers),
        ).status_code
        == 201
    )
    del headers["X-Column-Mapping"]
    saved = auth.client.post(BASE + "/inspect", content=CSV, headers=headers).json()
    assert saved["recognition"]["profile_name"] == "Reviewed dates"
    assert saved["recognition"]["state"] == "recognized" and saved["invalid_rows"] == 0
    assert saved["samples"][0]["normalized"]["transaction_date"] == "2026-04-03"
