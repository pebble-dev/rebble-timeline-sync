from flask import Blueprint, jsonify, url_for, request
from flask.cli import with_appcontext
import secrets
import uuid
import requests
import click
from .models import db, SandboxToken, TimelinePin, UserTimeline, TimelineTopic, TimelineTopicSubscription, AppGlance
from .utils import get_uid, api_error, pin_valid, glance_valid
from .settings import config

import beeline

api = Blueprint('api', __name__)


def get_locker_info(user_token):
    if user_token is None:
        raise ValueError
    sandbox_token = SandboxToken.query.filter_by(token=user_token).one_or_none()
    if sandbox_token is not None:
        beeline.add_context_field('user', sandbox_token.user_id)
        beeline.add_context_field('app_uuid', sandbox_token.app_uuid)
        return sandbox_token.user_id, sandbox_token.app_uuid, f"sandbox-uuid:{sandbox_token.app_uuid}"
    else:
        result = requests.get(f"{config['APPSTORE_API_URL']}/api/v1/locker/by_token/{user_token}", headers={"Authorization": f"Bearer {config['SECRET_KEY']}"})
        if result.status_code != 200:
            raise ValueError
        locker_info = result.json()
        beeline.add_context_field('user', locker_info['user_id'])
        beeline.add_context_field('app_uuid', locker_info['app_uuid'])
        return locker_info['user_id'], locker_info['app_uuid'], f"uuid:{locker_info['app_uuid']}"


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
    last_timeline_id = request.args.get('timeline')

    user_timeline = db.session.query(UserTimeline).filter_by(user_id=user_id)
    if last_timeline_id is not None:
        user_timeline = user_timeline.filter(UserTimeline.id > last_timeline_id)

    last_timeline = user_timeline.order_by(UserTimeline.id.desc()).first()
    if last_timeline is not None:
        last_timeline_id = last_timeline.id

    timeline_updates = [user_timeline_item.to_json() for user_timeline_item in user_timeline.order_by(UserTimeline.id.asc())]

    result = {
        "updates": timeline_updates,
        "syncURL": url_for('api.sync', timeline=last_timeline_id, _external=True)
    }
    return jsonify(result)

@api.route('/user/pins/<pin_id>', methods=['PUT', 'DELETE'])
def user_pin(pin_id):
    try:
        user_token = request.headers.get('X-User-Token')
        user_id, app_uuid, data_source = get_locker_info(user_token)
    except ValueError:
        return api_error(410)

    if request.method == 'PUT':
        pin_json = request.json
        if not pin_valid(pin_id, pin_json):
            beeline.add_context_field('timeline.failure.cause', 'pin_valid')
            return api_error(400)

        pin = TimelinePin.query.filter_by(app_uuid=app_uuid, user_id=user_id, id=pin_id).one_or_none()
        if pin is None:  # create pin
            pin = TimelinePin.from_json(pin_json, app_uuid, user_id, data_source, 'web', [])
            if pin is None:
                beeline.add_context_field('timeline.failure.cause', 'from_json')
                return api_error(400)

            user_timeline = UserTimeline(user_id=user_id,
                                         type='timeline.pin.create',
                                         item=pin)
            db.session.add(pin)
            db.session.add(user_timeline)
            db.session.commit()
        else:  # update pin
            try:
                pin.update_from_json(pin_json)

                # Clean up old UserTimeline events first.  Note that this
                # has to be transactional with creating the new one --
                # which, luckily, it is!
                UserTimeline.query.filter(UserTimeline.item == pin).delete()

                user_timeline = UserTimeline(user_id=user_id,
                                             type='timeline.pin.create',
                                             item=pin)
                db.session.add(pin)
                db.session.add(user_timeline)
                db.session.commit()
            except (KeyError, ValueError):
                beeline.add_context_field('timeline.failure.cause', 'update_pin')
                return api_error(400)

    elif request.method == 'DELETE':
        pin = TimelinePin.query.filter_by(app_uuid=app_uuid, user_id=user_id, id=pin_id).first_or_404()

        # No need to post even old create events, since nobody will render
        # them, after all.
        UserTimeline.query.filter(UserTimeline.item == pin).delete()

        user_timeline = UserTimeline(user_id=user_id,
                                     type='timeline.pin.delete',
                                     item=pin)
        db.session.add(user_timeline)
        db.session.commit()
    return 'OK'


def get_app_info(timeline_token):
    if timeline_token is None:
        raise ValueError
    result = requests.get(f"{config['APPSTORE_API_URL']}/api/v1/apps/by_token/{timeline_token}", headers={"Authorization": f"Bearer {config['SECRET_KEY']}"})
    if result.status_code != 200:
        raise ValueError
    app_info = result.json()
    beeline.add_context_field('app_uuid', app_info['app_uuid'])
    return app_info['app_uuid'], f"uuid:{app_info['app_uuid']}"



@api.route('/shared/pins/<pin_id>', methods=['PUT', 'DELETE'])
def shared_pin(pin_id):
    try:
        timeline_token = request.headers.get('X-API-Key')
        app_uuid, data_source = get_app_info(timeline_token)
    except ValueError:
        return api_error(410)

    if request.method == 'PUT':
        try:
            topic_strings = request.headers.get('X-Pin-Topics').split(",")
            topics = []
            for topic_string in topic_strings:
                topic = TimelineTopic.query.filter_by(app_uuid=app_uuid, name=topic_string).one_or_none()

                if topic is None:
                    topic = TimelineTopic(app_uuid=app_uuid, name=topic_string, create_time=datetime.datetime.utcnow())
                    db.session.add(topic)

                topics.append(topic)
                pin_json = request.json
        except (ValueError, AttributeError):
            return api_error(410)

        if not pin_valid(pin_id, pin_json):
            beeline.add_context_field('timeline.failure.cause', 'pin_valid')
            return api_error(400)

        pin = TimelinePin.query.filter_by(app_uuid=app_uuid, id=pin_id, user_id=None).one_or_none()
        if pin is None:  # create pin
            pin = TimelinePin.from_json(pin_json, app_uuid, None, data_source, 'web', topics)
            if pin is None:
                beeline.add_context_field('timeline.failure.cause', 'from_json')
                return api_error(400)

            db.session.add(pin)

            for topic in topics:
                for subscription in topic.subscriptions:
                    user_timeline = UserTimeline(user_id=subscription.user_id,
                                                 type='timeline.pin.create',
                                                 item=pin)
                    db.session.add(user_timeline)

            db.session.commit()
        else:  # update pin
            try:
                pin.update_from_json(pin_json)

                # Clean up old UserTimeline events first.  Note that this
                # has to be transactional with creating the new one --
                # which, luckily, it is!
                UserTimeline.query.filter(UserTimeline.item == pin).delete()

                db.session.add(pin)

                for topic in topics:
                    for subscription in topic.subscriptions:
                        user_timeline = UserTimeline(user_id=subscription.user_id,
                                                     type='timeline.pin.create',
                                                     item=pin)
                        db.session.add(user_timeline)

                db.session.commit()
            except (KeyError, ValueError):
                beeline.add_context_field('timeline.failure.cause', 'update_pin')
                return api_error(400)

    elif request.method == 'DELETE':
        pin = TimelinePin.query.filter_by(app_uuid=app_uuid, user_id=None, id=pin_id).first_or_404()

        # No need to post even old create events, since nobody will render
        # them, after all.
        UserTimeline.query.filter(UserTimeline.item == pin).delete()

        for topic in pin.topics:
            for subscription in topic.subscriptions:
                user_timeline = UserTimeline(user_id=subscription.user_id,
                                             type='timeline.pin.delete',
                                             item=pin)
                db.session.add(user_timeline)

        db.session.commit()
    return 'OK'


@api.route('/user/subscriptions')
def user_subscriptions_list():
    try:
        user_token = request.headers.get('X-User-Token')
        user_id, app_uuid, data_source = get_locker_info(user_token)
    except ValueError:
        return api_error(410)

    topics = TimelineTopic.query.join(TimelineTopicSubscription, TimelineTopic.id == TimelineTopicSubscription.topic_id).filter(TimelineTopic.app_uuid == app_uuid, TimelineTopicSubscription.user_id == user_id)
    result = {
        "topics": list(map(lambda t: t.name, topics))
    }

    return jsonify(result)


@api.route('/user/subscriptions/<topic_string>', methods=['POST', 'DELETE'])
def user_subscriptions_manage(topic_string):
    try:
        user_token = request.headers.get('X-User-Token')
        user_id, app_uuid, data_source = get_locker_info(user_token)
    except ValueError:
        return api_error(410)

    topic = TimelineTopic.query.filter_by(app_uuid=app_uuid, name=topic_string).one_or_none()
    if topic is None:
        topic = TimelineTopic(app_uuid=app_uuid, name=topic_string, create_time=datetime.datetime.utcnow())
        db.session.add(topic)

    subscription = TimelineTopicSubscription.query.filter_by(user_id=user_id, topic=topic).one_or_none()

    if request.method == 'POST':
        if subscription is None:
            subscription = TimelineTopicSubscription(user_id=user_id, topic=topic)
            db.session.add(subscription)

            # Add pins user now has a subscription for
            for pin in topic.pins:
                user_timeline = UserTimeline.query.filter_by(user_id==user_id, item=pin).one_or_none()

                if user_timeline is None:
                    # TODO: Was this pin formerly deleted for other subscribers? If so, type should be `timeline.pin.delete` or not in there at all
                    user_timeline = UserTimeline(user_id=user_id,
                                                 type='timeline.pin.create',
                                                 item=pin)
                    db.session.add(user_timeline)

            user_timeline = UserTimeline(user_id=user_id, type='timeline.topic.subscription', item=topic)
            db.session.add(user_timeline)

            db.session.commit()

    elif request.method == 'DELETE':
        if subscription is not None:
            TimelineTopicSubscription.query.filter_by(user_id=user_id, topic=topic).delete()

            # Clean up pins user no longer has a subscription for
            for pin in topic.pins:
                pin_subscriptions = TimelineTopicSubscription.query.filter(
                    TimelineTopicSubscription.user_id == user_id,
                    TimelineTopicSubscription.topic.in_(pin.topics)
                ).one_or_none()

                if pin_subscriptions is None:
                    UserTimeline.query.filter_by(user_id=user_id, item=pin).delete()

                    user_timeline = UserTimeline(user_id=user_id,
                                                 type='timeline.pin.delete',
                                                 item=pin)

                    db.session.add(user_timeline)

            user_timeline = UserTimeline(user_id=user_id, type='timeline.topic.unsubscription', item=topic)
            db.session.add(user_timeline)

            db.session.commit()

    return 'OK'


@api.route('/user/glance', methods=['PUT'])
def user_app_glance():
    try:
        user_token = request.headers.get('X-User-Token')
        user_id, app_uuid, data_source = get_locker_info(user_token)
    except ValueError:
        return api_error(410)

    glance_json = request.json
    if not glance_valid(glance_json):
        beeline.add_context_field('glance.failure.cause', 'glance_valid')
        return api_error(400)

    glance = AppGlance.query.filter_by(app_uuid=app_uuid, user_id=user_id).one_or_none()

    if glance is None:
      glance = AppGlance(app_uuid=app_uuid, user_id=user_id)

    glance = glance.from_json(glance_json['slices'], app_uuid, user_id, data_source)
    if glance is None:
        beeline.add_context_field('glance.failure.cause', 'from_json')
        return api_error(400)

    db.session.add(glance)

    UserTimeline.query.filter_by(user_id=user_id, item=glance).delete()

    user_timeline = UserTimeline(user_id=user_id, type='appglance.slice.create', item=glance)
    db.session.add(user_timeline)

    db.session.commit()
    return 'OK'


@api.errorhandler(404)
def page_not_found(e):
    return api_error(404)


@api.errorhandler(500)
def internal_server_error(e):
    return api_error(500)

@click.command('fill-timelines')
@with_appcontext
# Meant to be run once in command line
def fill_user_timelines():
    for subscription in TimelineTopicSubscription.query.all():
        user_timeline = UserTimeline(user_id=subscription.user_id, type='timeline.topic.subscription', item=subscription.topic)
        db.session.add(user_timeline)

    for glance in AppGlance.query.all():
        user_timeline = UserTimeline(user_id=glance.user_id, type='appglance.slice.create', item=glance)
        db.session.add(user_timeline)

    db.session.commit()

def init_api(app, url_prefix='/v1'):
    app.register_blueprint(api, url_prefix=url_prefix)
    app.cli.add_command(fill_user_timelines)
