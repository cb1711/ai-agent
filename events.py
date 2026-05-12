from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Event:
    """Base event on the bus."""
    type: str  # "user_message", "reminder_fired", "response"
    user_id: str  # "cli", "telegram:123456", etc.
    source: str  # "cli", "telegram", "scheduler"
    content: str  # message text
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponseEvent(Event):
    """Output from agent."""
    type: str = field(default="response", init=False)
    dest: str = None  # where to send response: "cli", "telegram:123456", etc.
