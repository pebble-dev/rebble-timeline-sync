from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .utils import parse_time, time_to_str
import uuid
import datetime


db = SQLAlchemy()
migrate = Migrate()


class SandboxToken(db.Model):
    __tablename__ = 'sandbox_tokens'
    token = db.Column(db.String, primary_key=True)
    user_id = db.Column(db.Integer)
    app_uuid = db.Column(UUID(as_uuid=True))


db.Index('sandbox_token_uid_appuuid_index', SandboxToken.user_id, SandboxToken.app_uuid, unique=True)


class TimelinePin(db.Model):
    __tablename__ = 'timeline_pins'
    guid = db.Column(UUID(as_uuid=True), primary_key=True)
    app_uuid = db.Column(UUID(as_uuid=True), nullable=False)
    user_id = db.Column(db.Integer, nullable=True)

    id = db.Column(db.String(64), nullable=False)
    time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer)

    create_notification = db.Column(JSONB, nullable=True)
    update_notification = db.Column(JSONB, nullable=True)
    layout = db.Column(JSONB, nullable=False)

    reminders = db.Column(JSONB, nullable=True)
    actions = db.Column(JSONB, nullable=True)

    data_source = db.Column(db.String(64), nullable=False)
    source = db.Column(db.String(8), nullable=False)
    create_time = db.Column(db.DateTime, nullable=False)
    update_time = db.Column(db.DateTime, nullable=False)

    topics = db.relationship('TimelineTopic', secondary='timeline_pin_topic', backref='TimelinePin')

    @classmethod
    def from_json(cls, pin_json, app_uuid, user_id, data_source, source, topics):
        try:
            pin = cls(
                guid=uuid.uuid4(),
                id=pin_json['id'],
                app_uuid=app_uuid,
                user_id=user_id,
                data_source=data_source,
                source=source,
                create_time=datetime.datetime.utcnow(),
                topics=topics,
            )
            pin.update_from_json(pin_json)
            return pin
        except (KeyError, ValueError):
            return None

    def update_from_json(self, pin_json):
        self.time = parse_time(pin_json['time'])
        self.duration = pin_json.get('duration')
        self.create_notification = pin_json.get('createNotification')
        self.update_notification = pin_json.get('updateNotification')
        self.layout = pin_json['layout']
        self.reminders = pin_json.get('reminders')
        self.actions = pin_json.get('actions')
        self.update_time = datetime.datetime.utcnow()

    def to_json(self):
        result = {
            'time': time_to_str(self.time),
            'layout': self.layout,
            'guid': self.guid,
            'dataSource': self.data_source,
            'source': self.source,
            'createTime': time_to_str(self.create_time),
            'updateTime': time_to_str(self.update_time),
            'topicKeys': list(map(lambda t: t.name, self.topics))
        }

        if self.duration is not None:
            result['duration'] = self.duration
        if self.create_notification is not None:
            result['createNotification'] = self.create_notification
        if self.update_notification is not None:
            result['updateNotification'] = self.update_notification
        if self.reminders is not None and len(self.reminders) > 0:
            result['reminders'] = self.reminders
        if self.actions is not None and len(self.actions) > 0:
            result['actions'] = self.actions

        return result


db.Index('timeline_pin_appuuid_uid_pinid_index', TimelinePin.app_uuid, TimelinePin.user_id, TimelinePin.id, unique=True)


class UserTimeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    type = db.Column(db.String(32))

    pin = db.relationship('TimelinePin', lazy=False, uselist=False, backref=db.backref('timelines', passive_deletes=True))
    pin_id = db.Column(UUID(as_uuid=True), db.ForeignKey('timeline_pins.guid', ondelete='CASCADE'))

    def to_json(self):
        if self.type == 'timeline.pin.create' or self.type == 'timeline.pin.delete':
            return {'type': self.type, 'data': self.pin.to_json()}
        else:
            return None

db.Index('user_timeline_userid_pinid', UserTimeline.user_id, UserTimeline.pin_id, unique = True)

class TimelineTopic(db.Model):
    __tablename__ = 'timeline_topics'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(64), nullable=False)
    app_uuid = db.Column(UUID(as_uuid=True), nullable=False)

    subscriptions = db.relationship('TimelineTopicSubscription', backref='TimelineTopic')

    pins = db.relationship('TimelinePin', secondary='timeline_pin_topic', backref='TimelineTopic')

db.Index('timeline_topic_appuuid_name_index', TimelineTopic.app_uuid, TimelineTopic.name, unique=True)

class TimelinePinTopic(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    pin = db.relationship('TimelinePin', lazy=False, uselist=False, backref=db.backref('timeline_pin_topic', passive_deletes=True))
    pin_id = db.Column(UUID(as_uuid=True), db.ForeignKey('timeline_pins.guid', ondelete='CASCADE'))

    topic = db.relationship('TimelineTopic', lazy=False, uselist=False, backref=db.backref('timeline_pin_topic', passive_deletes=True))
    topic_id = db.Column(db.Integer, db.ForeignKey('timeline_topics.id', ondelete='CASCADE'))

db.Index('timeline_pin_topic_pinid_topicid_index', TimelinePinTopic.pin_id, TimelinePinTopic.topic_id, unique=True)

class TimelineTopicSubscription(db.Model):
    __tablename__ = 'timeline_topic_subscriptions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    topic = db.relationship('TimelineTopic', backref=db.backref('timeline_topic_subscriptions', passive_deletes=True))
    topic_id = db.Column(db.Integer, db.ForeignKey('timeline_topics.id', ondelete='CASCADE'))

db.Index('timeline_topic_subscription_userid_topicid_index', TimelineTopicSubscription.user_id, TimelineTopicSubscription.topic_id, unique=True)

def delete_expired_pins(app):
    with app.app_context():
        expiration_time = datetime.datetime.utcnow() - datetime.timedelta(days=2)  # Remove pins older than 2 days
        expired_pins = db.session.query(TimelinePin).filter(TimelinePin.time < expiration_time)

        expired_pins.delete()
        db.session.commit()

# Meant to be run once in command line to clean up after b77d214fe44c5c6a82e25e012bb9c917c2649fea.
def cleanup_duplicate_usertimeline():
    all_pins = UserTimeline.query.with_entities(UserTimeline.pin_id, func.count(UserTimeline.pin_id).label('total')).group_by(UserTimeline.pin_id).all()

    for pin, count in all_pins:
        if count <= 1:
            continue

        print(f"Cleaning up pin {pin} with {count} UserTimelines")

        # Look up the pin's max.
        baseq = UserTimeline.query.filter(UserTimeline.pin_id == pin)

        max_id = baseq.order_by(UserTimeline.id.desc()).first()

        remainder = baseq.filter(UserTimeline.id < max_id.id)

        assert(remainder.count() == count - 1)

        remainder.delete()
        db.session.commit()

def init_app(app):
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    migrate.init_app(app, db)

