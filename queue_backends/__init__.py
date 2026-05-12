import json
from abc import ABC, abstractmethod


class VideoChunkQueue(ABC):
    """Abstract interface for transporting screen recording chunks between processes."""

    @abstractmethod
    def publish(self, chunk: dict) -> None:
        """Serialize and enqueue a chunk dict."""
        ...

    @abstractmethod
    def consume(self):
        """Blocking generator that yields deserialized chunk dicts indefinitely."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Signal consume() to exit on the next iteration."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release underlying connection / channel."""
        ...

    @staticmethod
    def from_settings() -> "VideoChunkQueue":
        """Factory: return the backend configured in settings."""
        from config import settings
        if settings.queue_backend == "rabbitmq":
            from queue_backends.rabbitmq_backend import RabbitMQQueue
            return RabbitMQQueue()
        from queue_backends.redis_backend import RedisQueue
        return RedisQueue()
