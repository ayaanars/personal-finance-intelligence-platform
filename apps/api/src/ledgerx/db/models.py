"""Explicit model registry for Alembic metadata discovery."""

from ledgerx.modules.goals.models import MonthlyGoal
from ledgerx.modules.identity.models import AuthAudit, Credential, User, UserSession, Workspace
from ledgerx.modules.identity.recovery_models import AuthRateLimit, PasswordReset
from ledgerx.modules.imports.models import ImportAudit, ImportRow, MappingProfile, StatementImport
from ledgerx.modules.transactions.enrichment_models import TransactionAudit, TransactionEnrichment
from ledgerx.modules.transactions.models import ImportedTransaction

__all__ = [
    "AuthRateLimit",
    "PasswordReset",
    "MappingProfile",
    "MonthlyGoal",
    "TransactionAudit",
    "TransactionEnrichment",
    "AuthAudit",
    "Credential",
    "User",
    "UserSession",
    "Workspace",
    "ImportAudit",
    "ImportRow",
    "StatementImport",
    "ImportedTransaction",
]
