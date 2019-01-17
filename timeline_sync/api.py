from flask import Blueprint, jsonify, request, url_for
import datetime
from .utils import get_access_token

api = Blueprint('api', __name__)

ISO_FORMAT = '%Y-%m-%dT%H:%M:%S.%fZ'


@api.route('/tokens/sandbox/<uuid>')
def get_sandbox_token(uuid):
    print("Access token:", get_access_token())

    result = {"uuid": uuid}

    # TODO: check uuid, user auth, dev portal permissions? and actually get/generate token with database
    result["token"] = "sandbox-token-test"

    return jsonify(result)


@api.route('/sync')
def sync():
    print("Access token:", get_access_token())

    result = {
        "updates": [
            {
                "type": "timeline.pin.create",
                "data": {
                    "time": datetime.datetime.utcnow().strftime(ISO_FORMAT),
                    "layout": {
                        "type": "genericPin",
                        "title": "Test",
                        "subtitle": "It works!",
                        "tinyIcon": "system://images/NEWS_EVENT"
                    },
                    "reminders": [
                        {
                            "time": datetime.datetime.utcnow().strftime(ISO_FORMAT),
                            "layout": {
                                "type": "genericReminder",
                                "title": "Test reminder",
                                "locationName": "Reminder locationName",
                                "tinyIcon": "system://images/NEWS_EVENT"
                            }
                        }
                    ],
                    "guid": "63be57bc-2ba1-5bc3-baeb-c192024df172",
                    "dataSource": "uuid:771f7c75-aa40-4623-adbb-946a34b483d4",
                    "source": "web",
                    "createTime": datetime.datetime.utcnow().strftime(ISO_FORMAT),
                    "updateTime": datetime.datetime.utcnow().strftime(ISO_FORMAT),
                    "topicKeys": [

                    ]
                }
            }
        ],
        "syncURL": url_for('api.sync', _external=True)
    }
    return jsonify(result)


def init_api(app, url_prefix='/v1'):
    app.register_blueprint(api, url_prefix=url_prefix)
