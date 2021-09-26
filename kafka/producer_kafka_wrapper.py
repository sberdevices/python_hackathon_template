import logging

from confluent_kafka import Producer

from config import settings

logger = logging.getLogger('kafka')


class ProducerKafkaWrapper:

    def __init__(self):
        self.producer = Producer(
            {
                'bootstrap.servers': settings.KAFKA_SERVER,
                'client.id': settings.USER_ID
            }
        )

    def produce(self, topic, key, value):
        self.producer.produce(topic=topic, key=key, value=value, callback=self._acked)

        # Wait up to 1 second for events. Callbacks will be invoked during
        # this method call if the message is acknowledged.
        self.producer.poll(3)

    @staticmethod
    def _acked(err, msg):
        if err is not None:
            logger.error('Failed to deliver message: %s %s %s', msg.topic, msg.key, msg.value)
        else:
            logger.debug('Delivered message: %s %s %s', msg.topic(), msg.key(), msg.value())
