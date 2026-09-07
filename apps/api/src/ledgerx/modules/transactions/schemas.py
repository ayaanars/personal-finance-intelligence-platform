from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from ledgerx.modules.transactions.understanding import Category


class CategoryOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category: Category | None


class TransactionView(BaseModel):
    id: UUID
    transaction_date: date
    amount: str
    currency: str
    raw_description: str
    normalized_description: str
    merchant: str | None
    category: Category
    categorization_source: str
    categorization_reason: str
    automatic_category: Category
    automatic_source: str
    automatic_reason: str
    rule_id: str
    rule_version: str
    normalization_version: str
    version: int
    enrichment_persisted: bool


class Page(BaseModel):
    next_cursor: str | None
    has_more: bool


class TransactionPage(BaseModel):
    items: list[TransactionView]
    page: Page
