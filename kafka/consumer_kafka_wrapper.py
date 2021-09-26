import logging
import logging
import time

from confluent_kafka import Consumer
from confluent_kafka import KafkaError, KafkaException

from config import settings

logger = logging.getLogger('kafka')


class ConsumerKafkaWrapper:
    def __init__(self):
        self._consumer = Consumer(
            {
                'bootstrap.servers': settings.KAFKA_SERVER,
                'group.id': 'default_consumer',
                'auto.offset.reset': 'smallest'
            }
        )
        self._running = False

    def start_loop(self, topics, process_message_func):
        self._running = True
        self._basic_consume_loop(topics=topics, process_message_func=process_message_func)

    def shutdown(self):
        self._running = False

    def _basic_consume_loop(self, topics, process_message_func):
        try:
            self._consumer.subscribe(topics)

            while self._running:
                msg = self._consumer.poll(timeout=1.0)
                #logger.debug('....Polling topics %s', str(topics))
                if msg is None:
                    continue

                logger.debug('Discovered message')

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition event
                        logger.error('%s [%d] reached end at offset %d', msg.topic(), msg.partition(), msg.offset())
                    elif msg.error():
                        raise KafkaException(msg.error())
                else:
                    logger.debug('Received message: %s %s %s', msg.topic(), msg.key(), msg.value())
                    process_message_func(msg)
        finally:
            # Close down consumer to commit final offsets.
            self._consumer.close()

    def get_message(self, topics, return_expression, timeout=1):
        self._running = True
        return self._get_message_consume_loop(topics=topics, return_expression=return_expression, timeout=timeout)

    def _get_message_consume_loop(self, topics, return_expression, timeout):
        start = time.time()
        return_message = None

        try:
            self._consumer.subscribe(topics)

            while self._running:
                if time.time() - start >= timeout:
                    logger.debug('Shutting down')
                    self.shutdown()

                msg = self._consumer.poll(timeout=1)
                #logger.debug('....Polling topics %s', str(topics))
                if msg is None:
                    continue
                logger.debug('Message discovered')

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        # End of partition event
                        logger.error('%s [%d] reached end at offset %d', msg.topic(), msg.partition(), msg.offset())
                    elif msg.error():
                        raise KafkaException(msg.error())
                else:
                    expr = return_expression(msg)
                    logger.debug('Message evaluated = %s', expr)
                    logger.debug('Accepted message: %s %s %s', msg.topic(), msg.key(), msg.value())
                    if expr:
                        return_message = msg
                        self.shutdown()
        except:
            # Close down consumer to commit final offsets.
            logger.error('Closing consumer')
            self._consumer.close()
        finally:
            return return_message
