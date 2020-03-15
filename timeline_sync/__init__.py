from flask import Flask, request

from .honeycomb import init_app as init_honeycomb
from .settings import config
from .api import init_api
from .models import init_app, delete_expired_pins

from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.config.update(**config)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
init_honeycomb(app)
init_app(app)
init_api(app)  # Includes both private (timeline-sync) and public (timeline-api) APIs

@app.route('/heartbeat')
def heartbeat():
    return 'ok'

def nightly_maintenance():
    delete_expired_pins(app)

