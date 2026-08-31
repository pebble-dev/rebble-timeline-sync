import requests
from flask import request, abort, jsonify
from .settings import config
import datetime
import firebase_admin

import beeline

ERROR_CODES = {
    400:	{"errorCode": "INVALID_JSON"},
    403:	{"errorCode": "INVALID_API_KEY"},
    404:	{"errorCode": "NOT_FOUND"},
    410:	{"errorCode": "INVALID_USER_TOKEN"},
    429:	{"errorCode": "RATE_LIMIT_EXCEEDED"},
    500:    {"errorCode": "INTERNAL_SERVER_ERROR"}
}

ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'
ISO_FORMAT_MSEC = '%Y-%m-%dT%H:%M:%S.%fZ'

# Copied from https://github.com/pebble-dev/rebble-appstore-api/blob/master/appstore/utils.py
# Really should be in common library


def get_access_token():
    access_token = request.args.get('access_token')
    if not access_token:
        header = request.headers.get('Authorization')
        if header:
            auth = header.split(' ')
            if len(auth) == 2 and auth[0] == 'Bearer':
                access_token = auth[1]
    if not access_token:
        abort(401)
    beeline.add_context_field("access_token", access_token)
    return access_token


def authed_request(method, url, **kwargs):
    headers = kwargs.setdefault('headers', {})
    headers['Authorization'] = f'Bearer {get_access_token()}'
    return requests.request(method, url, **kwargs)


def get_uid():
    result = authed_request('GET', f"{config['REBBLE_AUTH_URL']}/api/v1/me")
    if result.status_code != 200:
        abort(401)
    beeline.add_context_field("user", result.json()['uid'])
    return result.json()['uid']


def api_error(code):
    response = jsonify(ERROR_CODES[code])
    response.status_code = code
    beeline.add_context_field('timeline.failure', ERROR_CODES[code]['errorCode'])
    return response


def parse_time(time_str):
    try:
        return datetime.datetime.strptime(time_str, ISO_FORMAT)
    except ValueError:
        pass
    
    return datetime.datetime.strptime(time_str, ISO_FORMAT_MSEC)


def time_to_str(time):
    return time.strftime(ISO_FORMAT)


def time_valid(time):
    now = datetime.datetime.utcnow()
    if (time < now and (now - time).days > 2) or (time > now and (time - now).days > 366):
        return False  # Time must not be more than two days in the past, or a year in the future.
    return True


def pin_valid(pin_id, pin_json):
    try:
        if pin_json is None or pin_json.get('id') != pin_id:
            beeline.add_context_field('timeline.failure.details', 'parse_failure_or_id_mismatch')
            return False
        if not time_valid(parse_time(pin_json['time'])):
            beeline.add_context_field('timeline.failure.details', 'invalid_time')
            return False
        if 'createNotification' in pin_json and 'time' in pin_json['createNotification']:
            beeline.add_context_field('timeline.failure.details', 'invalid_time_attribute')
            return False  # The createNotification type does not require a time attribute.
        if 'updateNotification' in pin_json and not time_valid(parse_time(pin_json['updateNotification']['time'])):
            beeline.add_context_field('timeline.failure.details', 'invalid_time_for_update')
            return False
        if 'reminders' in pin_json:
            if len(pin_json['reminders']) > 3:
                beeline.add_context_field('timeline.failure.details', 'too_many_reminders')
                return False  # Max 3 reminders
            for reminder in pin_json['reminders']:
                if not time_valid(parse_time(reminder['time'])):
                    beeline.add_context_field('timeline.failure.details', 'invalid_reminder_time')
                    return False
    except (KeyError, ValueError, TypeError):
        beeline.add_context_field('timeline.failure.details', 'miscellaneous_failure')
        return False
    return True


def glance_valid(glance_json):
    try:
        if glance_json is None:
            beeline.add_context_field('glance.failure.details', 'parse_failure')
            return False
        if 'slices' in glance_json:
            for glance_slice in glance_json['slices']:
                if 'expirationTime' in glance_slice and not parse_time(glance_slice['expirationTime']):
                    beeline.add_context_field('glance.failure.details', 'invalid_expiration_time')
                    return False
        else:
            beeline.add_context_field('glance.failure.details', 'no_slices')
            return False
    except (KeyError, ValueError, TypeError):
        beeline.add_context_field('glance.failure.details', 'miscellaneous_failure')
        return False
    return True


def send_fcm_message(user_id, data):
    if user_id is None:
        raise ValueError

    fcm_tokens = db.session.query(FcmToken).filter_by(user_id=user_id)
    tokens = [fcm_token.token for fcm_token in fcm_tokens]

    message = firebase_admin.messaging.Message(
        data=data,
        tokens=tokens,
    )

    response = firebase_admin.messaging.send_each_for_multicast(message)

    if response.failure_count > 0:
        responses = response.responses
        for idx, resp in enumerate(responses):
            if not resp.success:
                FcmToken.query.filter_by(user_id=user_id, token=tokens[idx]).delete()


def send_fcm_message_to_topics(topics, data):
    condition = ' || '.join([f"'{str(topic.id)}' in topics" for topic in topics])

    message = firebase_admin.messaging.Message(
        data=data,
        condition=condition,
    )

    response = firebase_admin.messaging.send(message)

    if not response.success:
        return api_error(400)


def subscribe_to_fcm_topic(user_id, topic):
    if user_id is None:
        raise ValueError

    fcm_tokens = db.session.query(FcmToken).filter_by(user_id=user_id)
    tokens = [fcm_token.token for fcm_token in fcm_tokens]

    response = firebase_admin.messaging.subscribe_to_topic(tokens, str(topic.id))

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

    response = firebase_admin.messaging.unsubscribe_from_topic(tokens, str(topic.id))

    if response.failure_count > 0:
        responses = response.responses
        for idx, resp in enumerate(responses):
            if not resp.success:
                FcmToken.query.filter_by(user_id=user_id, token=tokens[idx]).delete()
