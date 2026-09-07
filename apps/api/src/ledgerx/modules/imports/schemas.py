"""Bounded application results shared by use cases and HTTP responses."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel


class RowIssue(BaseModel):
    code: str
    message: str


class RowView(BaseModel):
    source_row_number: int
    transaction_date: date | None
    description: str | None
    amount: str | None
    currency: str | None
    errors: list[RowIssue]


class RowPage(BaseModel):
    items: list[RowView]
    next_after_row: int | None


class ImportView(BaseModel):
    id: UUID
    status: str
    parser_name: str
    parser_version: str
    total_rows: int
    valid_rows: int
    invalid_rows: int
    accepted_rows: int
    period_start: date | None
    period_end: date | None
    currencies: list[str]
    created_at: datetime
    expires_at: datetime
    finalized_at: datetime | None
    can_finalize: bool
    rows: RowPage


class FinalizeView(BaseModel):
    id: UUID
    status: str
    accepted_rows: int
    finalized_at: datetime
