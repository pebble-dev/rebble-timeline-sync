from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.types import TypeDecorator, CHAR, TEXT
from sqlalchemy.dialects.postgresql import UUID
from .utils import parse_time, time_to_str
import uuid
import json


class GUID(TypeDecorator):
    """Platform-independent GUID type.

    Uses PostgreSQL's UUID type, otherwise uses
    CHAR(32), storing as stringified hex values.

    """
    impl = CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(32))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return "%.32x" % uuid.UUID(value).int
            else:
                # hexstring
                return "%.32x" % value.int

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                value = uuid.UUID(value)
            return value


class JsonEncodedDict(TypeDecorator):
    """
        Enables JSON storage by encoding and decoding on the fly.
    """

    impl = TEXT

    def process_bind_param(self, value, dialect):
        if value is None:
            return '{}'
        else:
            return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        else:
            return json.loads(value)


db = SQLAlchemy()


class SandboxToken(db.Model):
    __tablename__ = "sandbox_tokens"
    user_id = db.Column(db.Integer, primary_key=True)
    app_id = db.Column(db.String(24), primary_key=True)
    token = db.Column(db.String(32), index=True)


class TimelinePin(db.Model):
    __tablename__ = "timeline_pins"
    guid = db.Column(GUID, primary_key=True)
    app_id = db.Column(db.String(24), nullable=False)
    user_id = db.Column(db.Integer, nullable=True)
    id = db.Column(db.String(32), nullable=False)
    time = db.Column(db.DateTime, nullable=False)
    duration = db.Column(db.Integer)

    create_notification_id = db.Column(db.Integer, db.ForeignKey('timeline_notifications.id'))
    create_notification = db.relationship('TimelineNotification', lazy=False, uselist=False, single_parent=True,
                                          cascade="all, delete-orphan", foreign_keys=[create_notification_id])

    update_notification_id = db.Column(db.Integer, db.ForeignKey('timeline_notifications.id'))
    update_notification = db.relationship('TimelineNotification', lazy=False, uselist=False, single_parent=True,
                                          cascade="all, delete-orphan", foreign_keys=[update_notification_id])

    layout_id = db.Column(db.Integer, db.ForeignKey('timeline_layouts.id'), nullable=False)
    layout = db.relationship('TimelineLayout', lazy=False, uselist=False, single_parent=True, cascade="all, delete-orphan")

    reminders = db.relationship('TimelineReminder', lazy=False, uselist=True, cascade="all, delete-orphan")
    actions = db.relationship('TimelineAction', lazy=False, uselist=True, cascade="all, delete-orphan")

    data_source = db.Column(db.String(64), nullable=False)
    source = db.Column(db.String(8), nullable=False)
    create_time = db.Column(db.DateTime, nullable=False)
    update_time = db.Column(db.DateTime, nullable=False)
    topic_keys = db.Column(db.String(8), nullable=False)  # TODO: proper topicKeys

    @classmethod
    def from_json(cls, pin_json):
        try:
            return cls(
                id=pin_json['id'],
                time=parse_time(pin_json['time']),
                duration=pin_json.get('duration'),
                create_notification=TimelineNotification.from_json(pin_json.get('createNotification')),
                update_notification=TimelineNotification.from_json(pin_json.get('updateNotification')),
                layout=TimelineLayout.from_json(pin_json['layout']),
                reminders=TimelineReminder.from_json(pin_json.get('reminders')),
                actions=TimelineAction.from_json(pin_json.get('actions'))
            )
        except KeyError:
            return None

    def to_json(self):
        result = {
            "time": time_to_str(self.time),
            "layout": self.layout.to_json(),
            "guid": self.guid,
            "dataSource": self.data_source,
            "source": self.source,
            "createTime": time_to_str(self.create_time),
            "updateTime": time_to_str(self.update_time),
            "topicKeys": self.topic_keys
        }

        if self.duration is not None:
            result["duration"] = self.duration
        if self.create_notification is not None:
            result["createNotification"] = self.create_notification
        if self.update_notification is not None:
            result["updateNotification"] = self.update_notification
        if self.reminders is not None and len(self.reminders) > 0:
            result["reminders"] = [reminder.to_json() for reminder in self.reminders]
        if self.actions is not None and len(self.actions) > 0:
            result["actions"] = [action.to_json() for action in self.actions]

        return result


db.Index('timeline_pin_appid_uid_pinid_index', TimelinePin.app_id, TimelinePin.user_id, TimelinePin.id, unique=True)


class TimelineNotification(db.Model):
    __tablename__ = "timeline_notifications"
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.DateTime)

    layout_id = db.Column(db.Integer, db.ForeignKey('timeline_layouts.id'), nullable=False)
    layout = db.relationship('TimelineLayout', lazy=False, uselist=False, single_parent=True, cascade="all, delete-orphan")

    @classmethod
    def from_json(cls, notification_json):
        if notification_json is None:
            return notification_json
        return cls(
            time=parse_time(notification_json.get('time')),
            layout=TimelineLayout.from_json(notification_json['layout'])
        )


class TimelineLayout(db.Model):
    __tablename__ = "timeline_layouts"
    id = db.Column(db.Integer, primary_key=True)
    layout_json = db.Column(JsonEncodedDict)

    @classmethod
    def from_json(cls, layout_json):
        if layout_json is None:
            return layout_json
        return cls(layout_json=layout_json)

    def to_json(self):
        return self.layout_json


class TimelineReminder(db.Model):
    __tablename__ = "timeline_reminders"
    id = db.Column(db.Integer, primary_key=True)
    time = db.Column(db.DateTime)

    layout_id = db.Column(db.Integer, db.ForeignKey('timeline_layouts.id'), nullable=False)
    layout = db.relationship('TimelineLayout', lazy=False, uselist=False, single_parent=True, cascade="all, delete-orphan")

    pin_id = db.Column(GUID, db.ForeignKey('timeline_pins.guid'))

    @classmethod
    def from_json(cls, reminders_json):
        if reminders_json is None:
            return []
        return [
            cls(
                time=parse_time(reminder_json['time']),
                layout=TimelineLayout.from_json(reminder_json['layout'])
            ) for reminder_json in reminders_json
        ]

    def to_json(self):
        return {"time": time_to_str(self.time), "layout": self.layout.to_json()}


class TimelineAction(db.Model):
    __tablename__ = "timeline_actions"
    id = db.Column(db.Integer, primary_key=True)
    action_json = db.Column(JsonEncodedDict)

    pin_id = db.Column(GUID, db.ForeignKey('timeline_pins.guid'))

    @classmethod
    def from_json(cls, actions_json):
        if actions_json is None:
            return []
        return [cls(action_json=action_json) for action_json in actions_json]

    def to_json(self):
        return self.action_json


class UserTimeline(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, index=True)
    type = db.Column(db.String(32))

    pin = db.relationship('TimelinePin', lazy=False, uselist=False)
    pin_id = db.Column(GUID, db.ForeignKey('timeline_pins.guid'))
    # TODO: topicKey, subDate

    def to_json(self):
        if self.type == 'timeline.pin.create':
            return {"type": self.type, "data": self.pin.to_json()}
        else:
            return None  # TODO: timeline.topic.subscribe, timeline.topic.unsubscribe, timeline.pin.delete


def init_app(app):
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    db.create_all(app=app)
