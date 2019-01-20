import requests
from flask import request, abort, jsonify
from .settings import config
import datetime


ERROR_CODES = {
    400:	{"errorCode": "INVALID_JSON"},
    403:	{"errorCode": "INVALID_API_KEY"},
    404:	{"errorCode": "NOT_FOUND"},
    410:	{"errorCode": "INVALID_USER_TOKEN"},
    429:	{"errorCode": "RATE_LIMIT_EXCEEDED"},
    500:    {"errorCode": "INTERNAL_SERVER_ERROR"}
}

ISO_FORMAT = '%Y-%m-%dT%H:%M:%SZ'

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
    return access_token


def authed_request(method, url, **kwargs):
    headers = kwargs.setdefault('headers', {})
    headers['Authorization'] = f'Bearer {get_access_token()}'
    return requests.request(method, url, **kwargs)


def get_uid():
    result = authed_request('GET', f"{config['REBBLE_AUTH_URL']}/api/v1/me?flag_authed=true")
    if result.status_code != 200:
        abort(401)
    return result.json()['uid']


def api_error(code):
    response = jsonify(ERROR_CODES[code])
    response.status_code = code
    return response


def parse_time(time_str):
    return datetime.datetime.strptime(time_str, ISO_FORMAT)


def time_to_str(time):
    return time.strftime(ISO_FORMAT)


def valid_time(time):
    now = datetime.datetime.utcnow()
    if (time < now and (now - time).days > 2) or (time > now and (time - now).days > 366):
        raise ValueError('Time must not be more than two days in the past, or a year in the future.')
    return time
