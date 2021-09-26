import json
import logging
from confluent_kafka.admin import AdminClient, NewTopic

from config import settings
from kafka.consumer_kafka_wrapper import ConsumerKafkaWrapper
from kafka.producer_kafka_wrapper import ProducerKafkaWrapper

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('mocks')


def create_topics(topics):
    admin_client = AdminClient({
        'bootstrap.servers': settings.KAFKA_SERVER
    })

    logger.debug('Creating topics %s', str(topics))
    topic_list = []
    for topic in topics:
        topic_list.append(NewTopic(topic, 1, 1))

    fs = admin_client.create_topics(topic_list)
    for topic, f in fs.items():
        try:
            f.result()  # The result itself is None
            logger.debug('Topic %s', topic)
        except Exception as e:
            logger.error('Failed to create topic %s: %s', topic, e)


class SmartApp:
    def __init__(self, name):
        self.name = name
        self.producer = ProducerKafkaWrapper()
        self.consumer = ConsumerKafkaWrapper()
        self.in_topic = f'{name}_in_{settings.USER_ID}'
        self.out_topic = f'{name}_out_{settings.USER_ID}'

        create_topics([self.in_topic, self.out_topic])

        self.consumer.start_loop([self.in_topic], self.process_message)

    def process_message(self, message):
        message_string = message.value().decode('UTF-8')
        decoded_message = json.loads(message_string)
        this_message_id = decoded_message.get('messageId')

        # no message_id - no to whom to answer
        if this_message_id is None:
            return

        message_name = decoded_message.get('messageName')
        session = decoded_message.get('uuid', {}).get('session')
        project_name = decoded_message.get('payload', {}).get('projectName')
        project_id = decoded_message.get('payload', {}).get('app_info', {}).get('projectId')

        if message_name == 'MESSAGE_TO_SKILL':
            app_response = json.dumps(
                {
                    'messageId': this_message_id,
                    'messageName': 'ANSWER_TO_USER',
                    'uuid': {
                        'session': session,
                        'userId': settings.USER_ID
                    },
                    'payload': {
                        'projectName': project_name,
                        'app_info': {
                            'projectId': project_id,
                        }
                    }
                }
            )
            self.producer.produce(self.out_topic, 'SERVER_ACTION', app_response)

class IntentRecognizer:
    def __init__(self):
        self.producer = ProducerKafkaWrapper()
        self.consumer = ConsumerKafkaWrapper()

        create_topics([settings.IR_TO, settings.IR_FROM])

        self.consumer.start_loop([settings.IR_TO], self.process_message)

    def process_message(self, message):
        message_string = message.value().decode('UTF-8')
        decoded_message = json.loads(message_string)
        this_message_id = decoded_message.get('messageId')

        # no message_id - no to whom to answer
        if this_message_id is None:
            return

        message_name = decoded_message.get('messageName')
        message_text = decoded_message.get('payload', {}).get('message')
        session = decoded_message.get('uuid', {}).get('session')
        uuid_user_id = decoded_message.get('uuid', {}).get('userId')
        app_responses = decoded_message.get('payload', {}).get('appResponses')

        if message_name == 'CLASSIFY_TEXT':
            classification_result_response = json.dumps(
                {
                    'messageId': this_message_id,
                    'messageName': 'CLASSIFICATION_RESULT',
                    'uuid': {
                        'session': session,
                        'userId': uuid_user_id
                    },
                    'payload': {
                        'intents': {
                            'weather': {
                                'score': 1.0,
                                'project': {'name': 'weather'}
                            }
                        },
                        'original_text': message_text
                    }
                }
            )
            self.producer.produce(settings.IR_FROM, 'CLASSIFICATION_RESULT', classification_result_response)

        if message_name == 'BLENDER_REQUEST':
            blender_result_response = json.dumps(
                {
                    'messageId': this_message_id,
                    'messageName': 'BLENDER_RESPONSE',
                    'uuid': {
                        'session': session,
                        'userId': uuid_user_id
                    },
                    'payload': {
                        'appResponses': app_responses
                    }
                }
            )
            self.producer.produce(settings.IR_FROM, 'BLENDER_RESPONSE', blender_result_response)


if __name__ == "__main__":
    import sys

    app = sys.argv[1]
    if app == 'ir':
        IntentRecognizer()
    else:
        SmartApp(app)