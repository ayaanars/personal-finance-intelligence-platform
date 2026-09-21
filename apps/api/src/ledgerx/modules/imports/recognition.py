"""Deterministic recognition: named evidence, explicit unresolved choices, no scores."""

import re
from typing import Literal

from pydantic import BaseModel, Field

from ledgerx.modules.imports.mapping import ColumnMapping, SourceTable, suggest, validate_mapping
from ledgerx.modules.imports.normalization import CURRENCIES


class Recognition(BaseModel):
    source: Literal["automatic", "profile", "reviewed"] = "automatic"
    state: Literal["recognized", "needs_confirmation", "needs_mapping"]
    mapping: ColumnMapping | None = None
    questions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    profile_name: str | None = None


def recognize(table: SourceTable, profiles: list[tuple[str, ColumnMapping]]) -> Recognition:
    # Profiles represent previously reviewed conventions, not merely guessed column names.
    distinct = {p.model_dump_json(): (name, p) for name, p in reversed(profiles)}
    if len(distinct) == 1:
        name, profile_mapping = next(iter(distinct.values()))
        validate_mapping(table.headers, profile_mapping)
        return Recognition(
            source="profile",
            state="recognized",
            mapping=profile_mapping,
            profile_name=name,
            evidence=["Saved mapping matches every source column name."],
        )
    suggestions, formats = suggest(table)
    required = [field for field in ("transaction_date", "description") if field not in suggestions]
    single = "amount" in suggestions
    split = "debit" in suggestions and "credit" in suggestions
    if single == split:
        required.append("amount_mode")
    if split and not single:
        positions = [table.headers.index(suggestions[field]) for field in ("debit", "credit")]
        if any(
            row[index].strip().startswith(("-", "+"))
            for row in table.rows
            if len(row) == len(table.headers)
            for index in positions
        ):
            required.append("amount_mode")
    questions = list(required)
    if len(distinct) > 1:
        questions.append("profile")
    if len(formats) != 1:
        questions.append("date_format")
    fixed = None
    if "currency" not in suggestions:
        explicit = {
            code
            for header in table.headers
            for code in CURRENCIES
            if re.search(rf"\b{code}\b", header.upper())
        }
        if len(explicit) == 1:
            fixed = next(iter(explicit))
        else:
            questions.append("currency")
    if single:
        values = [
            row[table.headers.index(suggestions["amount"])].strip()
            for row in table.rows
            if len(row) == len(table.headers)
        ]
        canonical = {"transaction_date", "description", "amount", "currency"} <= set(table.headers)
        if not canonical and not any(value.startswith("-") for value in values):
            questions.append("sign_convention")
    config = {
        "transaction_date": suggestions.get("transaction_date", ""),
        "description": suggestions.get("description", ""),
        "amount_mode": "debit_credit" if split and not single else "single",
        "amount": suggestions.get("amount") if not split or single else None,
        "debit": suggestions.get("debit") if split and not single else None,
        "credit": suggestions.get("credit") if split and not single else None,
        "currency": suggestions.get("currency"),
        "fixed_currency": fixed,
        "date_format": formats[0] if len(formats) == 1 else "YYYY-MM-DD",
    }
    # A partial mapping is not executable. Suggestions remain available separately.
    mapping = ColumnMapping.model_validate(config) if not required else None
    return Recognition(
        state="needs_mapping" if required else "needs_confirmation" if questions else "recognized",
        mapping=mapping,
        questions=questions,
        evidence=["Unique header aliases checked against source values."]
        + (["One date format fits every source row."] if len(formats) == 1 else [])
        + ([f"Currency {fixed} is explicitly named in the source headers."] if fixed else [])
        + (
            ["Debit and credit columns define unsigned outflows and inflows."]
            if split and not single
            else ["Signed amounts are preserved; no signs are reversed."]
        ),
    )
