"""Untrusted upload transport bounds without a database or filesystem writes."""

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from starlette.requests import Request
from starlette.types import Message

from ledgerx.api import import_upload
from ledgerx.modules.imports.errors import ImportFailure


def request(chunks: list[bytes], headers: dict[str, str]) -> Request:
    async def messages() -> AsyncIterator[Message]:
        for chunk in chunks:
            yield {"type": "http.request", "body": chunk, "more_body": True}
        yield {"type": "http.request", "body": b"", "more_body": False}

    stream = messages()
    return Request(
        {"type": "http", "headers": [(k.encode(), v.encode()) for k, v in headers.items()]},
        stream.__anext__,
    )


@pytest.mark.parametrize("size_header", [None, "1", "5242881", "-1", "invalid", "9" * 100])
def test_upload_size_including_dishonest_content_length(size_header: str | None) -> None:
    headers = {"x-filename": "synthetic.csv"}
    if size_header is not None:
        headers["content-length"] = size_header
    req = request([b"a" * import_upload.MAX_BYTES, b"x"], headers)
    with pytest.raises(ImportFailure) as error:
        asyncio.run(import_upload.read_csv_upload(req))
    assert error.value.status in {400, 413}


@pytest.mark.parametrize("name", ["", "../a.csv", "C:\\a.csv", "a.pdf", "a.csv.exe", "x" * 130])
def test_filename_is_restricted(name: str) -> None:
    with pytest.raises(ImportFailure, match="FILENAME_INVALID"):
        asyncio.run(import_upload.read_csv_upload(request([b"data"], {"x-filename": name})))


def test_chunked_upload_and_timeout() -> None:
    headers = {"x-filename": "synthetic.csv"}
    assert asyncio.run(import_upload.read_csv_upload(request([b"a,", b"b"], headers))) == b"a,b"

    async def slow() -> Message:
        await asyncio.sleep(1)
        return {"type": "http.request", "body": b"", "more_body": False}

    req = Request({"type": "http", "headers": [(b"x-filename", b"synthetic.csv")]}, slow)
    with patch.object(import_upload, "UPLOAD_SECONDS", 0.001):
        with pytest.raises(ImportFailure, match="UPLOAD_TIMEOUT"):
            asyncio.run(import_upload.read_csv_upload(req))
