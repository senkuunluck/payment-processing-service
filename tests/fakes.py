from typing import Any


class FakeMessagePublisher:
    """Fake message broker for testing."""

    def __init__(self) -> None:
        self.published_messages: list[dict[str, Any]] = []
        self.fail_event_types: set[str] = set()

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Simulate message publishing."""

        if event_type in self.fail_event_types:
            raise RuntimeError("Simulated broker connection error")

        self.published_messages.append(
            {
                "event_type": event_type,
                "payload": payload,
            }
        )
