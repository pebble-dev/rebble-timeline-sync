from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
from rws_common import honeycomb
import firebase_admin

from .settings import config
from .api import init_api
from .models import init_app, delete_expired_pins

app = Flask(__name__)
app.config.update(**config)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

honeycomb.init(app, 'timeline_sync')
honeycomb.sample_routes['api.sync'] = 10

init_app(app)
init_api(app)  # Includes both private (timeline-sync) and public (timeline-api) APIs

if app.config['FIREBASE_PROJECT_ID'] is not None:
    credentials = firebase_admin.credentials.Certificate({
        "type": "service_account",
        "project_id": app.config['FIREBASE_PROJECT_ID'],
        "client_email": app.config['FIREBASE_CLIENT_EMAIL'],
        "token_uri": "https://oauth2.googleapis.com/token",
        "private_key": app.config['FIREBASE_PRIVATE_KEY'],
    })

    firebase_admin.initialize_app(credentials)


@app.route('/heartbeat')
@app.route('/timeline-sync/heartbeat')
def heartbeat():
    return 'ok'

def nightly_maintenance():
    delete_expired_pins(app)

