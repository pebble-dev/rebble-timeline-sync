from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
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
    user_id = db.Column(db.Integer, nullable=False)
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

    @classmethod
    def from_json(cls, pin_json, app_uuid, user_id, data_source, source):
        try:
            pin = cls(
                guid=uuid.uuid4(),
                id=pin_json['id'],
                app_uuid=app_uuid,
                user_id=user_id,
                data_source=data_source,
                source=source,
                create_time=datetime.datetime.utcnow(),
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
            'topicKeys': []
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

db.Index('user_timeline_user_id', UserTimeline.user_id)

def delete_expired_pins(app):
    with app.app_context():
        expiration_time = datetime.datetime.utcnow() - datetime.timedelta(days=2)  # Remove pins older than 2 days
        expired_pins = db.session.query(TimelinePin).filter(TimelinePin.time < expiration_time)

        expired_pins.delete()
        db.session.commit()


def init_app(app):
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)
    migrate.init_app(app, db)

