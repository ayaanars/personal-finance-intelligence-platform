"""Exact canonical transaction rules independent of HTTP and persistence."""

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ledgerx.modules.imports.parser import Candidate

CURRENCIES = frozenset({"AED", "USD", "EUR", "GBP"})
ERROR_MESSAGES = {
    "COLUMN_COUNT_INVALID": "Row must contain the same number of columns as the header",
    "FIELD_TOO_LONG": "Fields must not exceed 4096 UTF-8 bytes",
    "DATE_INVALID": "Invalid date for the selected date format",
    "DEBIT_CREDIT_BOTH": "Both debit and credit are populated; leave the unused column blank",
    "DEBIT_CREDIT_INVALID": "Use an unsigned debit or credit amount; signed values need review",
    "DESCRIPTION_INVALID": "Use a nonblank description of at most 500 characters",
    "AMOUNT_INVALID": "Use a nonzero signed decimal with up to 16 integer and 4 fractional digits",
    "CURRENCY_UNSUPPORTED": "Use AED, USD, EUR or GBP in uppercase",
}


@dataclass(frozen=True)
class NormalizedRow:
    source_row_number: int
    transaction_date: date | None
    description: str | None
    amount: Decimal | None
    currency: str | None
    fingerprint: bytes | None
    errors: tuple[str, ...]


def normalize(candidate: Candidate) -> NormalizedRow:
    errors: list[str] = []
    parsed_date = None
    amount = None
    if candidate.values is None:
        return NormalizedRow(
            candidate.source_row_number,
            None,
            None,
            None,
            None,
            None,
            (candidate.error_code or "COLUMN_COUNT_INVALID",),
        )
    date_text, description, amount_text, currency = candidate.values
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", date_text):
        try:
            parsed_date = date.fromisoformat(date_text)
        except ValueError:
            pass
    if parsed_date is None:
        errors.append("DATE_INVALID")
    if not description.strip() or len(description) > 500:
        errors.append("DESCRIPTION_INVALID")
    if re.fullmatch(r"[+-]?[0-9]{1,16}(?:\.[0-9]{1,4})?", amount_text):
        amount = Decimal(amount_text)
    if amount is None or amount == 0:
        errors.append("AMOUNT_INVALID")
    if currency not in CURRENCIES:
        errors.append("CURRENCY_UNSUPPORTED")
    if errors:
        # Invalid values are not needed to explain how to correct the source record.
        return NormalizedRow(
            candidate.source_row_number, None, None, None, None, None, tuple(errors)
        )
    assert amount is not None and parsed_date is not None
    fingerprint = hashlib.sha256(
        json.dumps(
            [candidate.source_row_number, date_text, description, format(amount, ".4f"), currency],
            ensure_ascii=True,
            separators=(",", ":"),
        ).encode("ascii")
    ).digest()
    return NormalizedRow(
        candidate.source_row_number, parsed_date, description, amount, currency, fingerprint, ()
    )
