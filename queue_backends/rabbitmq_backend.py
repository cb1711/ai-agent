import json
import logging

import pika

from config import settings
from queue_backends import VideoChunkQueue

logger = logging.getLogger(__name__)

_EXCHANGE = ""
_DURABLE = True


class RabbitMQQueue(VideoChunkQueue):
    def __init__(self) -> None:
        params = pika.URLParameters(settings.rabbitmq_url)
        self._connection = pika.BlockingConnection(params)
        self._channel = self._connection.channel()
        self._queue_name = settings.screen_record_queue_name
        self._channel.queue_declare(queue=self._queue_name, durable=_DURABLE)
        logger.info("RabbitMQQueue connected url=%s queue=%s", settings.rabbitmq_url, self._queue_name)

    def publish(self, chunk: dict) -> None:
        self._channel.basic_publish(
            exchange=_EXCHANGE,
            routing_key=self._queue_name,
            body=json.dumps(chunk),
            properties=pika.BasicProperties(delivery_mode=2),  # persistent
        )

    def consume(self):
        logger.info("RabbitMQQueue starting consume on %s", self._queue_name)
        self._channel.basic_qos(prefetch_count=1)
        for method, _props, body in self._channel.consume(
            self._queue_name, auto_ack=False, inactivity_timeout=1
        ):
            if method is None:
                # inactivity_timeout fired — check if we should stop
                continue
            yield json.loads(body)
            self._channel.basic_ack(method.delivery_tag)

    def stop(self) -> None:
        self._channel.stop_consuming()

    def close(self) -> None:
        try:
            self._channel.cancel()
            self._connection.close()
        except Exception:
            pass
        logger.info("RabbitMQQueue closed")
