"""Raw CSV transport: bounded memory only, no filename-derived filesystem access."""

import asyncio
import re

from fastapi import Request

from ledgerx.modules.imports.errors import ImportFailure

MAX_BYTES = 5 * 1024 * 1024
UPLOAD_SECONDS = 15


async def read_csv_upload(request: Request) -> bytes:
    # The filename is checked and discarded. It is never used as a path or retained.
    filename = request.headers.get("x-filename", "")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.-]{0,119}\.csv", filename, re.ASCII):
        raise ImportFailure(422, "FILENAME_INVALID", "Use a simple .csv filename in X-Filename")
    size = request.headers.get("content-length")
    if size is not None:
        if not size.isascii() or not size.isdecimal():
            raise ImportFailure(400, "CONTENT_LENGTH_INVALID", "Invalid content length")
        if len(size) > 10 or int(size) > MAX_BYTES:
            raise ImportFailure(413, "FILE_TOO_LARGE", "CSV exceeds the 5 MiB limit")
    content = bytearray()
    try:
        async with asyncio.timeout(UPLOAD_SECONDS):
            async for chunk in request.stream():
                if len(content) + len(chunk) > MAX_BYTES:
                    raise ImportFailure(413, "FILE_TOO_LARGE", "CSV exceeds the 5 MiB limit")
                content.extend(chunk)
        return bytes(content)
    except TimeoutError:
        raise ImportFailure(408, "UPLOAD_TIMEOUT", "CSV upload took too long") from None
    finally:
        content.clear()
