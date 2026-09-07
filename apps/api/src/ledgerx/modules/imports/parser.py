"""Adapter-neutral CSV candidates and strict bounded canonical CSV parsing."""

import csv
import io
import re
from collections.abc import Iterator
from dataclasses import dataclass
from time import monotonic
from typing import Protocol

from ledgerx.modules.imports.errors import ImportFailure

MAX_ROWS = 25_000
MAX_FIELD_BYTES = 4096
PARSE_SECONDS = 15
HEADERS = ("transaction_date", "description", "amount", "currency")


def validate_quoting(decoded: str) -> None:
    """csv.reader strict mode alone accepts quotes embedded in unquoted fields."""
    state = "start"
    for character in decoded:
        if state == "quoted":
            if character == '"':
                state = "closed"
        elif state == "closed":
            if character == '"':
                state = "quoted"
            elif character in ",\r\n":
                state = "start"
            else:
                raise ImportFailure(422, "CSV_MALFORMED", "CSV quoting is invalid")
        elif character == '"':
            if state != "start":
                raise ImportFailure(422, "CSV_MALFORMED", "CSV quoting is invalid")
            state = "quoted"
        elif character in ",\r\n":
            state = "start"
        else:
            state = "unquoted"
    if state == "quoted":
        raise ImportFailure(422, "CSV_MALFORMED", "CSV quoting is invalid")


@dataclass(frozen=True)
class Candidate:
    source_row_number: int
    values: tuple[str, str, str, str] | None
    error_code: str | None = None


class StatementAdapter(Protocol):
    name: str
    version: str

    def candidates(self, content: bytes) -> Iterator[Candidate]: ...


class CanonicalCSV:
    name = "ledgerx-canonical"
    version = "1"

    def candidates(self, content: bytes) -> Iterator[Candidate]:
        started = monotonic()
        try:
            decoded = content.decode("utf-8-sig", errors="strict")
        except UnicodeDecodeError:
            raise ImportFailure(422, "ENCODING_INVALID", "CSV must be UTF-8") from None
        if not decoded.strip():
            raise ImportFailure(422, "CSV_EMPTY", "CSV must contain a header and data rows")
        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", decoded):
            raise ImportFailure(422, "CSV_CONTROL_CHARACTER", "CSV contains unsupported characters")
        validate_quoting(decoded)
        reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
        try:
            headers = next(reader)
            if len(headers) != len(HEADERS) or set(headers) != set(HEADERS):
                raise ImportFailure(
                    422,
                    "CSV_HEADERS_INVALID",
                    "Required columns: transaction_date, description, amount, currency",
                )
            positions = [headers.index(column) for column in HEADERS]
            count = 0
            for row in reader:
                count += 1
                if count > MAX_ROWS:
                    raise ImportFailure(413, "ROW_LIMIT_EXCEEDED", "CSV exceeds 25000 data rows")
                if monotonic() - started >= PARSE_SECONDS:
                    raise ImportFailure(422, "PARSE_TIMEOUT", "CSV processing took too long")
                # Record numbers count CSV records, not physical lines inside quoted fields.
                number = count + 1
                if len(row) != len(HEADERS):
                    yield Candidate(number, None, "COLUMN_COUNT_INVALID")
                elif any(len(field.encode("utf-8")) > MAX_FIELD_BYTES for field in row):
                    yield Candidate(number, None, "FIELD_TOO_LONG")
                else:
                    values = [row[position] for position in positions]
                    yield Candidate(number, (values[0], values[1], values[2], values[3]))
            if count == 0:
                raise ImportFailure(422, "CSV_EMPTY", "CSV must contain data rows")
        except csv.Error:
            raise ImportFailure(
                422, "CSV_MALFORMED", "CSV structure or quoting is invalid"
            ) from None


def select_adapter(code: str) -> StatementAdapter:
    if code != CanonicalCSV.name:
        raise ImportFailure(422, "PARSER_UNSUPPORTED", "Select ledgerx-canonical")
    return CanonicalCSV()
