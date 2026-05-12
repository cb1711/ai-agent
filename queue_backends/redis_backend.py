import json
import logging

import redis as redis_lib

from config import settings
from queue_backends import VideoChunkQueue

logger = logging.getLogger(__name__)


class RedisQueue(VideoChunkQueue):
    def __init__(self) -> None:
        self._client = redis_lib.Redis.from_url(settings.redis_url, decode_responses=True)
        self._queue_name = settings.screen_record_queue_name
        self._stopped = False
        logger.info("RedisQueue connected url=%s queue=%s", settings.redis_url, self._queue_name)

    def publish(self, chunk: dict) -> None:
        self._client.rpush(self._queue_name, json.dumps(chunk))

    def consume(self):
        logger.info("RedisQueue starting consume on %s", self._queue_name)
        while not self._stopped:
            result = self._client.blpop(self._queue_name, timeout=1)
            if result is None:
                continue
            _, raw = result
            yield json.loads(raw)

    def stop(self) -> None:
        self._stopped = True

    def close(self) -> None:
        self._client.close()
        logger.info("RedisQueue closed")
