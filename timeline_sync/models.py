from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .utils import parse_time, time_to_str
import uuid
import datetime


db = SQLAlchemy()


class SandboxToken(db.Model):
    __tablename__ = "sandbox_tokens"
    user_id = db.Column(db.Integer, primary_key=True)
    app_uuid = db.Column(UUID(as_uuid=True), primary_key=True)
    token = db.Column(db.String, index=True)


class TimelinePin(db.Model):
    __tablename__ = "timeline_pins"
    guid = db.Column(UUID(as_uuid=True), primary_key=True)
    app_uuid = db.Column(UUID(as_uuid=True), nullable=False)
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
    def from_json(cls, pin_json, app_uuid, user_id, data_source, source, topic_keys):
        try:
            pin = cls(
                guid=uuid.uuid4(),
                id=pin_json['id'],
                app_uuid=app_uuid,
                user_id=user_id,
                data_source=data_source,
                source=source,
                create_time=datetime.datetime.utcnow(),
                topic_keys=topic_keys   # TODO: proper pin.topic_keys
            )
            pin.update_from_json(pin_json)
            return pin
        except KeyError:
            return None

    def update_from_json(self, pin_json):
        self.time = parse_time(pin_json['time'])
        self.duration = pin_json.get('duration')
        self.create_notification = TimelineNotification.from_json(pin_json.get('createNotification'))
        self.update_notification = TimelineNotification.from_json(pin_json.get('updateNotification'))
        self.layout = TimelineLayout.from_json(pin_json['layout'])
        self.reminders = TimelineReminder.from_json(pin_json.get('reminders'))
        self.actions = TimelineAction.from_json(pin_json.get('actions'))
        self.update_time = datetime.datetime.utcnow()

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


db.Index('timeline_pin_appuuid_uid_pinid_index', TimelinePin.app_uuid, TimelinePin.user_id, TimelinePin.id, unique=True)


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
    layout_json = db.Column(JSONB)

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

    pin_id = db.Column(UUID(as_uuid=True), db.ForeignKey('timeline_pins.guid'))

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
    action_json = db.Column(JSONB)

    pin_id = db.Column(UUID(as_uuid=True), db.ForeignKey('timeline_pins.guid'))

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
    pin_id = db.Column(UUID(as_uuid=True), db.ForeignKey('timeline_pins.guid'))
    # TODO: topicKey, subDate

    def to_json(self):
        if self.type == 'timeline.pin.create' or self.type == 'timeline.pin.delete':
            return {"type": self.type, "data": self.pin.to_json()}
        else:
            return None  # TODO: timeline.topic.subscribe, timeline.topic.unsubscribe


def init_app(app):
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    db.create_all(app=app)
