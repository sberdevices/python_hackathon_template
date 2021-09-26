import json
import logging
import uuid

import aiohttp
from aiohttp import web

from config import settings
from kafka.consumer_kafka_wrapper import ConsumerKafkaWrapper
from kafka.producer_kafka_wrapper import ProducerKafkaWrapper
from utils.support_functions import IsOurKafkaResponceChecker, kafka_message_to_dict, ResponseException

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger('webapp')


class WebAsyncWrapper:
    def __init__(self):
        self.app = web.Application()
        self._configure_server()
        self._register_producer_kafka()
        self.consumer = ConsumerKafkaWrapper()

    def _configure_server(self):
        self._message_id = 0
        self.app.add_routes([
            web.get('/', self._handle),
            web.get('/message/{message}', self._handle)
        ])

    async def _handle(self, request):
        message = request.match_info.get('message', 'Anonymous')

        try:
            session = uuid.uuid4().hex
            classified_message = self.classify_text_IR(session, message)

            classified_message_dict = kafka_message_to_dict(classified_message)
            intents = classified_message_dict.get('payload', {}).get('intents', {})

            apps_responses = self.apps_responses_on_message_to_skill(session, intents, message)

            blender_response_IR = self.blender_response_IR(session, apps_responses)

            blender_response_IR_dict = kafka_message_to_dict(blender_response_IR)

            response_dict = blender_response_IR_dict
            response_dict['messageName'] = 'ANSWER_TO_USER'
            response = str(response_dict)

            classificator_responses = classified_message_dict.get('payload', {})
            blender_apps_responses = response_dict.get('payload', {}).get('appResponses', [])

            tokens = []
            for app_response in [classificator_responses, blender_response_IR_dict] + blender_apps_responses:
                app_headers = app_response.get('headers', {})
                tokens.append(app_headers)

            return web.Response(text=response, headers={"tokens": json.dumps(tokens)})

        except ResponseException as e:
            logger.error(e)
            return aiohttp.web.HTTPInternalServerError()

    def run_app(self):
        web.run_app(self.app)

    def _register_producer_kafka(self):
        self.producer = ProducerKafkaWrapper()

    def get_new_message_id(self):
        self._message_id += 1
        return self._message_id

    def classify_text_IR(self, session, message):
        this_message_id = self.get_new_message_id()
        classify_text_request = json.dumps(
            {
                'messageId': this_message_id,
                'messageName': 'CLASSIFY_TEXT',
                'uuid': {
                    'session': session,
                    'userId': settings.USER_ID
                },
                'payload': {
                    'message': message
                }
            }
        )

        logger.info('Request to classify to IR sent')
        self.producer.produce(settings.IR_TO, 'CLASSIFY_TEXT', classify_text_request)

        is_our_IR_response_checker = IsOurKafkaResponceChecker(message_ids=[this_message_id],
                                                               message_names=['CLASSIFICATION_RESULT'])
        message_from_topic = self.consumer.get_message(topics=[settings.IR_FROM],
                                                       return_expression=is_our_IR_response_checker.check,
                                                       timeout=100)

        if message_from_topic is None:
            raise ResponseException('CLASSIFICATION_RESULT', settings.IR_FROM)

        logger.info('Response to classify from IR received')
        return message_from_topic

    def apps_responses_on_message_to_skill(self, session, intents, message):
        sent_messages_ids = []
        logger.info('Sending requests to smart apps')
        smart_app_from_topics = []
        for intent_name, intent in intents.items():
            project = intent.get('project', {})
            project_name = project.get('name')

            if project_name not in settings.SMART_APPS:
                continue

            smart_app_to_topic = f'{project_name}_in_{settings.USER_ID}'
            smart_app_from_topics.append(f'{project_name}_out_{settings.USER_ID}')

            project_id = project.get('id')
            this_message_id = self.get_new_message_id()
            app_request = json.dumps(
                {
                    'messageName': 'MESSAGE_TO_SKILL',
                    'messageId': this_message_id,
                    'uuid': {
                        'session': session,
                        'userId': settings.USER_ID
                    },
                    'payload': {
                        'app_info': {
                            'projectId': project_id
                        },
                        'intent': intent_name,
                        'projectName': project_name,
                        'message': {
                            'original_text': message
                        }
                    }
                }
            )
            logger.info('Sending requests to smart app %s, topic: %s', project_name, smart_app_to_topic)
            self.producer.produce(smart_app_to_topic, 'MESSAGE_TO_SKILL', app_request)
            sent_messages_ids.append(this_message_id)

        apps_responses = []
        messages_number = len(sent_messages_ids)
        for response_num in range(messages_number):
            is_our_response_checker = IsOurKafkaResponceChecker(message_ids=sent_messages_ids,
                                                                message_names=['ANSWER_TO_USER'])
            app_response = self.consumer.get_message(topics=smart_app_from_topics,
                                                     return_expression=is_our_response_checker.check,
                                                     timeout=10)
            if app_response is None:
                raise ResponseException('ANSWER_TO_USER', smart_app_from_topics)

            app_response_message_dict = kafka_message_to_dict(app_response)

            message_id = app_response_message_dict.get('messageId')
            apps_responses.append(app_response_message_dict)
            sent_messages_ids.remove(message_id)
            logger.info('Response from smart app received: %s', app_response.value())

        logger.info('Response from all smart apps received')

        return apps_responses

    def blender_response_IR(self, session, apps_responses):
        this_message_id = self.get_new_message_id()
        IR_blender_request = json.dumps(
            {
                'messageName': 'BLENDER_REQUEST',
                'messageId': this_message_id,
                'uuid': {
                    'session': session,
                    "userId": settings.USER_ID
                },
                'payload': {
                    'appResponses': apps_responses
                }
            }
        )

        logger.info('Request to blend to IR sent')

        self.producer.produce(settings.IR_TO, 'BLENDER_REQUEST', IR_blender_request)

        is_our_IR_response_checker = IsOurKafkaResponceChecker(message_ids=[this_message_id],
                                                               message_names=['BLENDER_RESPONSE'])
        IR_blender_response = self.consumer.get_message(topics=[settings.IR_FROM],
                                                        return_expression=is_our_IR_response_checker.check,
                                                        timeout=10)

        if IR_blender_response is None:
            raise ResponseException('BLENDER_RESPONSE', settings.IR_FROM)

        logger.info('Response to blend from IR received')

        return IR_blender_response
