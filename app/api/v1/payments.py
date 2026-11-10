from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_api_key
from app.db.session import get_session
from app.repositories.payment import PaymentRepository
from app.schemas.payment import (
    PaymentCreate,
    PaymentCreatedResponse,
    PaymentResponse,
)
from app.services.payment import IdempotencyConflictError, PaymentService

router = APIRouter(
    prefix="/payments",
    tags=["Payments"],
    dependencies=[Depends(require_api_key)],
)


@router.post(
    "",
    response_model=PaymentCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def create_payment(
    data: PaymentCreate,
    idempotency_key: Annotated[
        str,
        Header(alias="Idempotency-Key", min_length=1, max_length=255),
    ],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentCreatedResponse:
    """Accept a new payment for asynchronous processing."""

    service = PaymentService(session)

    try:
        payment = await service.create_payment(data, idempotency_key)
    except IdempotencyConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return PaymentCreatedResponse(
        payment_id=payment.id,
        status=payment.status,
        created_at=payment.created_at,
    )


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
)
async def get_payment(
    payment_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PaymentResponse:
    """Retrieve a payment by its ID."""

    repository = PaymentRepository(session)
    payment = await repository.get_by_id(payment_id)

    if payment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment not found",
        )

    return PaymentResponse.model_validate(payment)
