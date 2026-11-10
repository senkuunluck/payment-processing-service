from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.core.config import get_settings


@pytest.fixture
def api_key() -> str:
    """Return the configured API key."""

    return get_settings().api_key


@pytest.fixture
def payment_payload() -> dict:
    """Return a valid payment request payload."""

    return {
        "amount": "1250.50",
        "currency": "RUB",
        "description": "Test payment",
        "metadata": {"order_id": "order-123"},
        "webhook_url": "https://example.com/webhook",
    }


@pytest.mark.asyncio
async def test_create_payment(
    client: AsyncClient,
    api_key: str,
    payment_payload: dict,
) -> None:
    response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers={
            "X-API-Key": api_key,
            "Idempotency-Key": "test-key-001",
        },
    )

    assert response.status_code == 202

    data = response.json()

    assert data["payment_id"] is not None
    assert data["status"] == "pending"
    assert data["created_at"] is not None
    assert "id" not in data
    assert "amount" not in data


@pytest.mark.asyncio
async def test_get_payment(
    client: AsyncClient,
    api_key: str,
    payment_payload: dict,
) -> None:
    create_response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers={
            "X-API-Key": api_key,
            "Idempotency-Key": "test-key-002",
        },
    )

    assert create_response.status_code == 202

    payment_id = create_response.json()["payment_id"]

    response = await client.get(
        f"/api/v1/payments/{payment_id}",
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 200
    assert response.json()["id"] == payment_id
    assert response.json()["amount"] == "1250.50"
    assert response.json()["currency"] == "RUB"


@pytest.mark.asyncio
async def test_idempotency_with_same_data(
    client: AsyncClient,
    api_key: str,
    payment_payload: dict,
) -> None:
    headers = {
        "X-API-Key": api_key,
        "Idempotency-Key": "test-key-003",
    }

    first_response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers=headers,
    )

    second_response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers=headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202

    assert first_response.json()["payment_id"] == second_response.json()["payment_id"]


@pytest.mark.asyncio
async def test_idempotency_with_different_data(
    client: AsyncClient,
    api_key: str,
    payment_payload: dict,
) -> None:
    headers = {
        "X-API-Key": api_key,
        "Idempotency-Key": "test-key-004",
    }

    first_response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers=headers,
    )

    different_payload = {
        **payment_payload,
        "amount": "2000.00",
    }

    second_response = await client.post(
        "/api/v1/payments",
        json=different_payload,
        headers=headers,
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 409


@pytest.mark.asyncio
async def test_missing_api_key(
    client: AsyncClient,
    payment_payload: dict,
) -> None:
    response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers={"Idempotency-Key": "test-key-005"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_invalid_api_key(
    client: AsyncClient,
    payment_payload: dict,
) -> None:
    response = await client.post(
        "/api/v1/payments",
        json=payment_payload,
        headers={
            "X-API-Key": "invalid-api-key",
            "Idempotency-Key": "test-key-006",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_nonexistent_payment(
    client: AsyncClient,
    api_key: str,
) -> None:
    nonexistent_id = uuid4()

    response = await client.get(
        f"/api/v1/payments/{nonexistent_id}",
        headers={"X-API-Key": api_key},
    )

    assert response.status_code == 404
