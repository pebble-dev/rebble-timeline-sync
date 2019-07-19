from flask import Flask

from .settings import config
from .api import init_api
from .models import init_app, delete_expired_pins

app = Flask(__name__)
app.config.update(**config)
init_app(app)
init_api(app)  # Includes both private (timeline-sync) and public (timeline-api) APIs

@app.route('/heartbeat')
def heartbeat():
    return 'ok'

def nightly_maintenance():
    delete_expired_pins(app)
