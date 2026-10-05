"""Hashed one-time recovery tokens and bounded global abuse budgets."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from ledgerx.db.base import Base


class PasswordReset(Base):
    __tablename__ = "password_resets"
    __table_args__ = (CheckConstraint("octet_length(token_hash) = 32", name="token_hash_length"),)
    token_hash: Mapped[bytes] = mapped_column(LargeBinary, primary_key=True)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthRateLimit(Base):
    __tablename__ = "auth_rate_limits"
    __table_args__ = (CheckConstraint("attempts > 0", name="positive_attempts"),)
    scope: Mapped[str] = mapped_column(String(32), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False)
