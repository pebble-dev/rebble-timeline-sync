from firebase_admin import messaging
from .models import db, FcmToken
from .utils import api_error

def send_fcm_message(user_id, data):
    if user_id is None:
        raise ValueError

    fcm_tokens = db.session.query(FcmToken).filter_by(user_id=user_id)
    tokens = [fcm_token.token for fcm_token in fcm_tokens]

    message = messaging.MulticastMessage(
        data=data,
        tokens=tokens,
    )

    response = messaging.send_each_for_multicast(message)

    if response.failure_count > 0:
        responses = response.responses
        for idx, resp in enumerate(responses):
            if not resp.success:
                FcmToken.query.filter_by(user_id=user_id, token=tokens[idx]).delete()


def send_fcm_message_to_topics(topics, data):
    condition = ' || '.join([f"'{str(topic.id)}' in topics" for topic in topics])

    message = messaging.Message(
        data=data,
        condition=condition,
    )

    try:
        response = messaging.send(message)
    except Exception as e:
        return api_error(400)


def subscribe_to_fcm_topic(user_id, topic):
    if user_id is None:
        raise ValueError

    fcm_tokens = db.session.query(FcmToken).filter_by(user_id=user_id)
    tokens = [fcm_token.token for fcm_token in fcm_tokens]

    response = messaging.subscribe_to_topic(tokens, str(topic.id))

    if response.failure_count > 0:
        responses = response.responses
        for idx, resp in enumerate(responses):
            if not resp.success:
                FcmToken.query.filter_by(user_id=user_id, token=tokens[idx]).delete()

def unsubscribe_from_fcm_topic(user_id, topic):
    if user_id is None:
        raise ValueError

    fcm_tokens = db.session.query(FcmToken).filter_by(user_id=user_id)
    tokens = [fcm_token.token for fcm_token in fcm_tokens]

    response = messaging.unsubscribe_from_topic(tokens, str(topic.id))

    if response.failure_count > 0:
        responses = response.responses
        for idx, resp in enumerate(responses):
            if not resp.success:
                FcmToken.query.filter_by(user_id=user_id, token=tokens[idx]).delete()    

