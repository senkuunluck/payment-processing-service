
import uuid
from enum import StrEnum
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy import (
    Enum as SQLAlchemyEnum,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PaymentStatus(StrEnum):
    """Available payment statuses."""

    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PaymentCurrency(StrEnum):
    """Supported payment currencies."""

    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"


class Payment(Base):
    """Payment database model."""

    __tablename__ = "payments"

    __table_args__ = (
        UniqueConstraint(
            "idempotency_key",
            name="uq_payments_idempotency_key",
        ),
        CheckConstraint(
            "amount > 0",
            name="positive_amount",
        ),
        Index("ix_payments_status", "status"),
        Index("ix_payments_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=12, scale=2),
        nullable=False,
    )

    currency: Mapped[PaymentCurrency] = mapped_column(
        SQLAlchemyEnum(
            PaymentCurrency,
            name="payment_currency",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )

    description: Mapped[str] = mapped_column(
        String(length=500),
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
    )

    status: Mapped[PaymentStatus] = mapped_column(
        SQLAlchemyEnum(
            PaymentStatus,
            name="payment_status",
            native_enum=False,
            create_constraint=True,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=PaymentStatus.PENDING,
        server_default=PaymentStatus.PENDING.value,
    )

    idempotency_key: Mapped[str] = mapped_column(
        String(length=255),
        nullable=False,
    )

    webhook_url: Mapped[str] = mapped_column(
        String(length=2048),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    def __repr__(self) -> str:
        return (
            f"Payment(id={self.id!r}, "
            f"amount={self.amount!r}, "
            f"currency={self.currency.value!r}, "
            f"status={self.status.value!r})"
        )
