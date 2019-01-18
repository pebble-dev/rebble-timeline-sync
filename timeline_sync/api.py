from flask import Blueprint, jsonify, url_for, request
import datetime
import secrets
from .models import db, SandboxToken, TimelinePin, UserTimeline
from .utils import get_uid, api_error
import uuid


api = Blueprint('api', __name__)


@api.route('/tokens/sandbox/<app_uuid>')
def get_sandbox_token(app_uuid):
    uid = get_uid()

    sandbox_token = SandboxToken.query.get((uid, app_uuid))

    if sandbox_token is None:
        # TODO: return 404 if app does not have timeline support or user is not authorised in dev portal
        sandbox_token = SandboxToken(user_id=uid, app_id=app_uuid, token=secrets.token_urlsafe(32))
        db.session.add(sandbox_token)
        db.session.commit()

    result = {"uuid": app_uuid, "token": sandbox_token.token}

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
    user_token = request.headers.get('X-User-Token')

    if user_token is None:
        return api_error(410)

    sandbox_token = SandboxToken.query.filter_by(token=user_token).one_or_none()
    if sandbox_token is None:
        # TODO try get ids from locker for user_token
        return api_error(410)
    else:
        app_id = sandbox_token.app_id
        user_id = sandbox_token.user_id
        data_source = f"sandbox-uuid:{app_id}"  # TODO: maybe it's not app_id. where does this uuid come from???

    if request.method == 'PUT':
        pin_json = request.json
        if pin_json is None or pin_json.get('id') != pin_id:
            return api_error(400)

        pin = TimelinePin.query.filter_by(app_id=app_id, id=pin_id).one_or_none()
        if pin is None:
            pin = TimelinePin.from_json(pin_json)
            if pin is None:
                return api_error(400)

            pin.guid = uuid.uuid4()
            pin.app_id = app_id
            pin.data_source = data_source
            pin.source = 'web'
            pin.create_time = datetime.datetime.utcnow()
            pin.update_time = pin.create_time  # TODO: is this right?
            pin.topic_keys = '[]'  # TODO: proper pin.topic_keys

            user_timeline = UserTimeline(user_id=user_id,
                                         type='timeline.pin.create',
                                         pin=pin)
            db.session.add(user_timeline)
            db.session.commit()
        else:
            pass  # TODO: update pin

    elif request.method == 'DELETE':
        pass  # TODO delete pin

    return 'OK'


def init_api(app, url_prefix='/v1'):
    app.register_blueprint(api, url_prefix=url_prefix)
