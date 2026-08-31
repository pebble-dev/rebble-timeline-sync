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

default_app = firebase_admin.initialize_app()

@app.route('/heartbeat')
@app.route('/timeline-sync/heartbeat')
def heartbeat():
    return 'ok'

def nightly_maintenance():
    delete_expired_pins(app)

