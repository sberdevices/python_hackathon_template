# Dialog policy simplified

Simple version of smart assistants dialog policy system.

# Algorithm
1. The message is sent to the system via *rest* into *Dialog Policy (DP)*
2. *DP* send request `CLASSIFY_TEXT` to *Intent Recognizer (IR)* to classify message
3. IR send back to the *DP* result of classification `CLASSIFICATION_RESULT` - intent, projects
4. *DP* send a request `MESSAGE_TO_SKILL` to each *Smart App(SA)* classified
5. Each *SA* response `ANSWER_TO_USER` to *DP*
6. When *DP* got all responces from *SA*s, *DP* sends to *IR* `BLENDER_REQUEST` with all `ANSWER_TO_USER`s included
7. *IR* respond `BLENDER_RESPONSE` to *DP*
8. *DP* respond `ANSWER_TO_USER` via *rest*

# Requirements
- Python 3.7.8

# Usage
1. docker-compose -f docker-compose-kafka.yml up --build
2. docker-compose -f docker-compose.yml up --build 
3. Send a *message* http://0.0.0.0:8888/your_message
