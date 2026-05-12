import asyncio
from events import Event, ResponseEvent


class EventBus:
    """Central async event bus for input and output."""

    def __init__(self):
        self.input_queue: asyncio.Queue[Event] = asyncio.Queue()
        self.output_queue: asyncio.Queue[ResponseEvent] = asyncio.Queue()

    async def put_input(self, event: Event) -> None:
        """Producer: put event on input bus (user messages, reminders, etc.)."""
        await self.input_queue.put(event)

    async def get_input(self) -> Event:
        """Agent: consume from input bus."""
        return await self.input_queue.get()

    async def put_output(self, event: ResponseEvent) -> None:
        """Agent: put response on output bus."""
        await self.output_queue.put(event)

    async def get_output(self) -> ResponseEvent:
        """Consumers: get response from output bus."""
        return await self.output_queue.get()
