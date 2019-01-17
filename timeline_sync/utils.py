import requests
from flask import request, abort
from .settings import config

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
