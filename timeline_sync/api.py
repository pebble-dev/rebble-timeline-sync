from flask import Blueprint, jsonify, url_for, request
import datetime
import secrets
import uuid
import requests
from .models import db, SandboxToken, TimelinePin, UserTimeline, UserSubscription
from .utils import get_uid, api_error
from .settings import config

api = Blueprint('api', __name__)


def parse_user_token(user_token):
    if user_token is None:
        raise ValueError
    sandbox_token = SandboxToken.query.filter_by(token=user_token).one_or_none()
    if sandbox_token is not None:
        return sandbox_token.user_id, sandbox_token.app_uuid, f"sandbox-uuid:{sandbox_token.app_uuid}"
    else:
        result = requests.get(f"{config['APPSTORE_API_URL']}/api/v1/locker/by_token/{user_token}")
        if result.status_code != 200:
            raise ValueError
        locker_info = result.json()
        return locker_info['user_id'], locker_info['app_uuid'], f"uuid:{locker_info['app_uuid']}"
    # TODO: should dataSource be app_uuid or it's something else?


@api.route('/tokens/sandbox/<app_uuid>')
def get_sandbox_token(app_uuid):
    uid = get_uid()
    app_uuid = uuid.UUID(app_uuid)

    sandbox_token = SandboxToken.query.filter_by(user_id=uid, app_uuid=app_uuid).one_or_none()

    if sandbox_token is None:
        # TODO: return 404 if app does not have timeline support or user is not authorised in dev portal
        sandbox_token = SandboxToken(user_id=uid, app_uuid=app_uuid, token=secrets.token_urlsafe(32))
        db.session.add(sandbox_token)
        db.session.commit()

    result = {"uuid": sandbox_token.app_uuid, "token": sandbox_token.token}

    return jsonify(result)


@api.route('/sync')
def sync():
    user_id = get_uid()

    user_timeline = db.session.query(UserTimeline).filter_by(user_id=user_id)

    updates = [user_timeline_item.to_json() for user_timeline_item in user_timeline]

    user_timeline.delete()
    db.session.commit()

    result = {
        "updates": updates,
        "syncURL": url_for('api.sync', _external=True)
    }
    return jsonify(result)


@api.route('/user/pins/<pin_id>', methods=['PUT', 'DELETE'])
def user_pin(pin_id):
    try:
        user_token = request.headers.get('X-User-Token')
        user_id, app_uuid, data_source = parse_user_token(user_token)
    except ValueError:
        return api_error(410)

    if request.method == 'PUT':
        pin_json = request.json
        if pin_json is None or pin_json.get('id') != pin_id:
            return api_error(400)

        pin = TimelinePin.query.filter_by(app_uuid=app_uuid, user_id=user_id, id=pin_id).one_or_none()
        if pin is None:  # create pin
            pin = TimelinePin.from_json(pin_json, app_uuid, user_id, data_source, 'web', [])
            if pin is None:
                return api_error(400)

            user_timeline = UserTimeline(user_id=user_id,
                                         type='timeline.pin.create',
                                         pin=pin)
            db.session.add(pin)
            db.session.add(user_timeline)
            db.session.commit()
        else:  # update pin
            try:
                pin.update_from_json(pin_json)
                user_timeline = UserTimeline(user_id=user_id,
                                             type='timeline.pin.create',
                                             pin=pin)
                db.session.add(pin)
                db.session.add(user_timeline)
                db.session.commit()
            except (KeyError, ValueError):
                return api_error(400)

    elif request.method == 'DELETE':
        pin = TimelinePin.query.filter_by(app_uuid=app_uuid, user_id=user_id, id=pin_id).first_or_404()
        user_timeline = UserTimeline(user_id=user_id,
                                     type='timeline.pin.delete',
                                     pin=pin)
        db.session.add(user_timeline)
        db.session.commit()
    return 'OK'


@api.route('/shared/pins/<pin_id>', methods=['PUT', 'DELETE'])
def shared_pin(pin_id):
    api_key = request.headers.get('X-API-Key')
    return api_error(403)  # TODO: check api_key in dev portal, add/delete shared pins


@api.route('/user/subscriptions')
def user_subscriptions_list():
    try:
        user_token = request.headers.get('X-User-Token')
        user_id, app_uuid, _ = parse_user_token(user_token)
    except ValueError:
        return api_error(410)

    return jsonify(
        {
            "topics": [sub.topic for sub in UserSubscription.query.filter_by(app_uuid=app_uuid, user_id=user_id)]
        }
    )


@api.route('/user/subscriptions/<topic>', methods=['POST', 'DELETE'])
def user_subscriptions_manage(topic):
    try:
        user_token = request.headers.get('X-User-Token')
        user_id, app_uuid, _ = parse_user_token(user_token)
    except ValueError:
        return api_error(410)

    if request.method == 'POST':
        user_subscription = UserSubscription(user_id=user_id, app_uuid=app_uuid, topic=topic)
        user_timeline = UserTimeline(user_id=user_id,
                                     type='timeline.topic.subscribe',
                                     topic_key=topic,
                                     sub_date=datetime.datetime.utcnow())
        db.session.add(user_timeline)
        db.session.add(user_subscription)
        db.session.commit()
    elif request.method == 'DELETE':
        user_subscription = UserSubscription.query.filter_by(user_id=user_id, app_uuid=app_uuid, topic=topic).first_or_404()
        user_timeline = UserTimeline(user_id=user_id,
                                     type='timeline.topic.unsubscribe',
                                     topic_key=topic)
        db.session.add(user_timeline)
        db.session.delete(user_subscription)
        db.session.commit()

    return 'OK'


@api.errorhandler(404)
def page_not_found(e):
    return api_error(404)


@api.errorhandler(500)
def internal_server_error(e):
    return api_error(500)


def init_api(app, url_prefix='/v1'):
    app.register_blueprint(api, url_prefix=url_prefix)
