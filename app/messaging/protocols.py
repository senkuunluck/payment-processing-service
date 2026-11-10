from typing import Any, Protocol


class MessagePublisher(Protocol):
    """Interface for publishing messages to a message broker."""

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Publish an event to the message broker."""
        ...
