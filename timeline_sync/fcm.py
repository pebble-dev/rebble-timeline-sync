import firebase_admin

from firebase_admin import messaging

from .models import FcmInstance

import beeline

def send_fcm_message(user_id, data):
    if user_id is None:
        beeline.add_context_field('timeline.failure.details', 'fcm_user_missing')
        raise ValueError

    fcm_instances = FcmInstance.query.filter_by(user_id=user_id)
    fids = [fcm_instance.fid for fcm_instance in fcm_instances]

    if len(fids) == 0:
        return

    message = messaging.MulticastMessage(
        data=data,
        fids=fids,
    )

    response = messaging.send_each_for_multicast(message)

    if response.failure_count > 0:
        responses = response.responses
        for idx, resp in enumerate(responses):
            if not resp.success:
                FcmInstance.query.filter_by(user_id=user_id, fid=fids[idx]).delete()


def send_fcm_message_to_topics(topics, data):
    condition = ' || '.join([f"'{str(topic.id)}' in topics" for topic in topics])

    message = messaging.Message(
        data=data,
        condition=condition,
    )

    response = messaging.send(message)


def subscribe_to_fcm_topic(user_id, topic):
    if user_id is None:
        beeline.add_context_field('timeline.failure.details', 'fcm_user_missing')
        raise ValueError

    fcm_instances = FcmInstance.query.filter_by(user_id=user_id)
    fids = [fcm_instance.fid for fcm_instance in fcm_instances]

    if len(fids) == 0:
        return

    response = messaging.subscribe_to_topic(fids, str(topic.id))

    if response.failure_count > 0:
        responses = response.responses
        for idx, resp in enumerate(responses):
            if not resp.success:
                FcmInstance.query.filter_by(user_id=user_id, fid=fids[idx]).delete()

def unsubscribe_from_fcm_topic(user_id, topic):
    if user_id is None:
        beeline.add_context_field('timeline.failure.details', 'fcm_user_missing')
        raise ValueError

    fcm_instances = FcmInstance.query.filter_by(user_id=user_id)
    fids = [fcm_instance.fid for fcm_instance in fcm_instances]

    if len(fids) == 0:
        return

    response = messaging.unsubscribe_from_topic(fids, str(topic.id))

    if response.failure_count > 0:
        responses = response.responses
        for idx, resp in enumerate(responses):
            if not resp.success:
                FcmInstance.query.filter_by(user_id=user_id, fid=fids[idx]).delete()
