"""Mapping inspection is transient; profiles retain configuration only."""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ledgerx.modules.identity.service import Principal
from ledgerx.modules.imports.errors import ImportFailure
from ledgerx.modules.imports.mapping import ColumnMapping, MappedCSV, read_table, suggest
from ledgerx.modules.imports.models import MappingProfile
from ledgerx.modules.imports.normalization import ERROR_MESSAGES, normalize
from ledgerx.modules.imports.recognition import Recognition, recognize
from ledgerx.modules.imports.schemas import RowIssue, RowView
from ledgerx.modules.imports.service import effective_status, owned_import


class ProfileView(BaseModel):
    id: UUID
    name: str
    mapping: ColumnMapping


class SampleView(BaseModel):
    source_row_number: int
    source: list[str]
    normalized: RowView | None


class InspectionView(BaseModel):
    recognition: Recognition
    headers: list[str]
    suggestions: dict[str, str]
    date_formats: list[str]
    profiles: list[ProfileView]
    samples: list[SampleView]
    total_rows: int
    invalid_rows: int | None


class SaveProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    import_id: UUID
    name: str = Field(min_length=1, max_length=80, pattern=r"^[^\x00-\x1f\x7f]+$")


def inspect(
    db: Session,
    principal: Principal,
    content: bytes,
    mapping: ColumnMapping | None,
) -> InspectionView:
    table = read_table(content)
    suggestions, formats = suggest(table)
    profiles = db.scalars(
        select(MappingProfile)
        .where(
            MappingProfile.user_id == principal.user.id,
            MappingProfile.workspace_id == principal.workspace.id,
        )
        .order_by(MappingProfile.name)
        .limit(50)
    ).all()
    compatible = [
        ProfileView(id=p.id, name=p.name, mapping=ColumnMapping.model_validate(p.mapping_spec))
        for p in profiles
        if set(p.source_headers) == set(table.headers)
    ]
    recognition = recognize(table, [(p.name, p.mapping) for p in compatible])
    if mapping is not None:
        recognition = Recognition(
            source="reviewed",
            state="recognized", mapping=mapping, evidence=["Mapping choices explicitly reviewed."]
        )
    elif recognition.state == "recognized":
        mapping = recognition.mapping
    normalized = (
        [normalize(candidate) for candidate in MappedCSV(mapping).table_candidates(table)]
        if mapping
        else []
    )
    samples = []
    sample_indices = list(range(min(5, len(table.rows))))
    sample_indices.extend(
        [index for index, row in enumerate(normalized) if index >= 5 and row.errors][:5]
    )
    for index in sample_indices:
        source = table.rows[index]
        row = normalized[index] if normalized else None
        samples.append(
            SampleView(
                source_row_number=index + 2,
                # Bounded display only; neither samples nor source values reach persistence.
                source=[value[:500] for value in source[:64]],
                normalized=RowView(
                    source_row_number=row.source_row_number,
                    transaction_date=row.transaction_date,
                    description=row.description,
                    amount=format(row.amount, ".4f") if row.amount is not None else None,
                    currency=row.currency,
                    errors=[
                        RowIssue(code=code, message=ERROR_MESSAGES[code]) for code in row.errors
                    ],
                )
                if row
                else None,
            )
        )
    return InspectionView(
        recognition=recognition,
        headers=table.headers,
        suggestions=suggestions,
        date_formats=formats,
        profiles=compatible,
        samples=samples,
        total_rows=len(table.rows),
        invalid_rows=sum(bool(row.errors) for row in normalized) if mapping else None,
    )


def save_profile(db: Session, principal: Principal, body: SaveProfile) -> ProfileView:
    batch = owned_import(db, principal, body.import_id)
    if effective_status(batch) not in {"ready", "completed"} or not batch.mapping_spec:
        raise ImportFailure(409, "PROFILE_NOT_READY", "Review a valid mapped import before saving")
    assert batch.source_headers is not None
    query = select(MappingProfile).where(
        MappingProfile.user_id == principal.user.id,
        MappingProfile.workspace_id == principal.workspace.id,
    )
    existing = db.scalar(query.where(MappingProfile.name == body.name))
    if existing is not None:
        if existing.mapping_spec != batch.mapping_spec or set(existing.source_headers) != set(
            batch.source_headers
        ):
            raise ImportFailure(409, "PROFILE_NAME_USED", "Choose a different profile name")
        return ProfileView(
            id=existing.id,
            name=existing.name,
            mapping=ColumnMapping.model_validate(existing.mapping_spec),
        )
    if (db.scalar(select(func.count()).select_from(query.subquery())) or 0) >= 50:
        raise ImportFailure(409, "PROFILE_LIMIT", "This workspace has reached its 50-profile limit")
    profile = MappingProfile(
        user_id=principal.user.id,
        workspace_id=principal.workspace.id,
        name=body.name,
        source_headers=batch.source_headers,
        mapping_spec=batch.mapping_spec,
    )
    db.add(profile)
    db.flush()
    return ProfileView(
        id=profile.id, name=profile.name, mapping=ColumnMapping.model_validate(profile.mapping_spec)
    )
