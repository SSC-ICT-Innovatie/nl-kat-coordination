from bytes.events.events import Event


class EventManager:
    async def publish(self, event: Event) -> None:
        raise NotImplementedError()
