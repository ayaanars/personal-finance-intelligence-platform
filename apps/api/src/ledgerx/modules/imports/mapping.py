"""Transient CSV inspection and explicit mappings into the existing canonical boundary."""

import csv
import io
import re
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime
from time import monotonic
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ledgerx.modules.imports.errors import ImportFailure
from ledgerx.modules.imports.normalization import CURRENCIES
from ledgerx.modules.imports.parser import (
    MAX_FIELD_BYTES,
    MAX_ROWS,
    PARSE_SECONDS,
    Candidate,
    validate_quoting,
)

DateFormat = Literal["YYYY-MM-DD", "DD/MM/YYYY", "MM/DD/YYYY", "DD-MM-YYYY"]
FORMATS: dict[str, tuple[str, str]] = {
    "YYYY-MM-DD": (r"[0-9]{4}-[0-9]{2}-[0-9]{2}", "%Y-%m-%d"),
    "DD/MM/YYYY": (r"[0-9]{2}/[0-9]{2}/[0-9]{4}", "%d/%m/%Y"),
    "MM/DD/YYYY": (r"[0-9]{2}/[0-9]{2}/[0-9]{4}", "%m/%d/%Y"),
    "DD-MM-YYYY": (r"[0-9]{2}-[0-9]{2}-[0-9]{4}", "%d-%m-%Y"),
}
ALIASES = {
    "transaction_date": {"date", "transaction date", "posting date", "value date", "txn date"},
    "description": {
        "description",
        "details",
        "narrative",
        "merchant",
        "transaction details",
        "payee",
        "particulars",
        "memo",
    },
    "amount": {"amount", "transaction amount", "net amount"},
    "debit": {"debit", "debit amount", "withdrawal", "withdrawals", "money out", "paid out"},
    "credit": {"credit", "credit amount", "deposit", "deposits", "money in", "paid in"},
    "currency": {"currency", "ccy"},
}


class ColumnMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    transaction_date: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=120)
    amount_mode: Literal["single", "debit_credit"] = "single"
    amount: str | None = Field(default=None, max_length=120)
    debit: str | None = Field(default=None, max_length=120)
    credit: str | None = Field(default=None, max_length=120)
    currency: str | None = Field(default=None, max_length=120)
    fixed_currency: Literal["AED", "USD", "EUR", "GBP"] | None = None
    date_format: DateFormat


def read_mapping(value: str) -> ColumnMapping:
    try:
        return ColumnMapping.model_validate_json(value)
    except ValidationError:
        raise ImportFailure(
            422, "MAPPING_INVALID", "Select required columns and an explicit date format"
        ) from None


def validate_mapping(headers: list[str], mapping: ColumnMapping) -> None:
    selected = [mapping.transaction_date, mapping.description]
    if mapping.amount_mode == "single":
        if not mapping.amount or mapping.debit is not None or mapping.credit is not None:
            raise ImportFailure(422, "MAPPING_INVALID", "Select one signed amount column")
        selected.append(mapping.amount)
    else:
        if not mapping.debit or not mapping.credit or mapping.amount is not None:
            raise ImportFailure(422, "MAPPING_INVALID", "Select separate debit and credit columns")
        selected.extend([mapping.debit, mapping.credit])
    if (mapping.currency is None) == (mapping.fixed_currency is None):
        raise ImportFailure(
            422, "MAPPING_INVALID", "Select a currency column or statement currency"
        )
    if mapping.currency is not None:
        selected.append(mapping.currency)
    if len(set(selected)) != len(selected) or any(column not in headers for column in selected):
        raise ImportFailure(
            422, "MAPPING_INVALID", "Use a different existing source column for each field"
        )


@dataclass(frozen=True)
class SourceTable:
    headers: list[str]
    rows: list[list[str]]


def read_table(content: bytes) -> SourceTable:
    started = monotonic()
    if len(content) > 5 * 1024 * 1024:
        raise ImportFailure(413, "FILE_TOO_LARGE", "CSV exceeds the 5 MiB limit")
    try:
        decoded = content.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise ImportFailure(422, "ENCODING_INVALID", "CSV must be UTF-8") from None
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", decoded):
        raise ImportFailure(422, "CSV_CONTROL_CHARACTER", "CSV contains unsupported characters")
    validate_quoting(decoded)
    reader = csv.reader(io.StringIO(decoded, newline=""), strict=True)
    try:
        headers = next(reader, [])
        normalized = [header.strip().casefold() for header in headers]
        if (
            not 1 <= len(headers) <= 64
            or any(not header.strip() or len(header) > 120 for header in headers)
            or len(set(normalized)) != len(headers)
        ):
            raise ImportFailure(
                422,
                "CSV_HEADERS_INVALID",
                "Use 1–64 unique, nonblank column names (120 characters max)",
            )
        rows: list[list[str]] = []
        for row in reader:
            if len(rows) >= MAX_ROWS:
                raise ImportFailure(413, "ROW_LIMIT_EXCEEDED", "CSV exceeds 25000 data rows")
            if monotonic() - started >= PARSE_SECONDS:
                raise ImportFailure(422, "PARSE_TIMEOUT", "CSV processing took too long")
            rows.append(row)
        if not rows:
            raise ImportFailure(422, "CSV_EMPTY", "CSV must contain data rows")
        return SourceTable(headers, rows)
    except csv.Error:
        raise ImportFailure(422, "CSV_MALFORMED", "CSV structure or quoting is invalid") from None


def date_value(value: str, date_format: str) -> str | None:
    pattern, formatter = FORMATS[date_format]
    if not re.fullmatch(pattern, value):
        return None
    try:
        return datetime.strptime(value, formatter).date().isoformat()
    except ValueError:
        return None


def suggest(table: SourceTable) -> tuple[dict[str, str], list[str]]:
    suggestions: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        candidates = [
            header
            for header in table.headers
            if re.sub(
                r"\s+",
                " ",
                re.sub(r"\b(AED|USD|EUR|GBP)\b|[()]", "", header, flags=re.IGNORECASE)
                .strip()
                .lower()
                .replace("_", " "),
            )
            in aliases
        ]
        # Multiple name matches remain a manual choice; values never choose a date's meaning.
        if len(candidates) == 1:
            column = candidates[0]
            values = [
                row[table.headers.index(column)].strip()
                for row in table.rows[:100]
                if len(row) == len(table.headers)
            ]
            populated = [value for value in values if value]
            plausible = bool(populated) or field in {"debit", "credit"}
            if field in {"amount", "debit", "credit"}:
                plausible = plausible and all(
                    re.fullmatch(r"[+-]?[0-9]+(?:\.[0-9]+)?", value) for value in populated
                )
            elif field == "currency":
                plausible = plausible and all(value in CURRENCIES for value in populated)
            elif field == "transaction_date":
                plausible = plausible and all(
                    any(date_value(value, fmt) for fmt in FORMATS) for value in populated
                )
            if plausible:
                suggestions[field] = column
    if "currency" not in suggestions:
        # A column containing only supported ISO codes is concrete currency evidence.
        candidates = []
        for index, header in enumerate(table.headers):
            if header in suggestions.values():
                continue
            values = [row[index].strip() for row in table.rows if len(row) == len(table.headers)]
            if values and all(value in CURRENCIES for value in values):
                candidates.append(header)
        if len(candidates) == 1:
            suggestions["currency"] = candidates[0]
    formats: list[str] = []
    if "transaction_date" in suggestions:
        index = table.headers.index(suggestions["transaction_date"])
        values = [row[index].strip() for row in table.rows if len(row) == len(table.headers)]
        formats = [fmt for fmt in FORMATS if values and all(date_value(v, fmt) for v in values)]
    return suggestions, formats


class MappedCSV:
    name = "ledgerx-mapped-csv"
    version = "1"

    def __init__(self, mapping: ColumnMapping) -> None:
        self.mapping = mapping

    def candidates(self, content: bytes) -> Iterator[Candidate]:
        table = read_table(content)
        yield from self.table_candidates(table)

    def table_candidates(self, table: SourceTable) -> Iterator[Candidate]:
        mapping = self.mapping
        validate_mapping(table.headers, mapping)
        for number, row in enumerate(table.rows, 2):
            if len(row) != len(table.headers):
                yield Candidate(number, None, "COLUMN_COUNT_INVALID")
                continue
            if any(len(value.encode("utf-8")) > MAX_FIELD_BYTES for value in row):
                yield Candidate(number, None, "FIELD_TOO_LONG")
                continue

            def value(column: str | None, source: list[str] = row) -> str:
                return source[table.headers.index(column)].strip() if column else ""

            normalized_date = date_value(value(mapping.transaction_date), mapping.date_format)
            amount = value(mapping.amount)
            if mapping.amount_mode == "debit_credit":
                debit, credit = value(mapping.debit), value(mapping.credit)
                if debit and credit:
                    yield Candidate(number, None, "DEBIT_CREDIT_BOTH")
                    continue
                unsigned = debit or credit
                if not re.fullmatch(r"[0-9]{1,16}(?:\.[0-9]{1,4})?", unsigned):
                    yield Candidate(number, None, "DEBIT_CREDIT_INVALID")
                    continue
                amount = f"-{debit}" if debit else credit
            yield Candidate(
                number,
                (
                    normalized_date or "",
                    value(mapping.description),
                    amount,
                    value(mapping.currency) if mapping.currency else mapping.fixed_currency or "",
                ),
            )
