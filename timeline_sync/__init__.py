import os

from flask import Flask, request
from werkzeug.middleware.proxy_fix import ProxyFix
from rws_common import honeycomb
import firebase_admin
from firebase_admin import credentials

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


def _normalize_private_key_pem(raw: str) -> str:
    """Turn env-safe PEM into real PEM (newlines, optional base64 wrapper)."""
    s = raw.strip()
    if not s:
        return s
    # Some loaders leave matching quotes in the value
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ('"', "'"):
        s = s[1:-1].strip()
    s = s.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
    return s.strip()


def _get_firebase_credential():
    project_id = os.environ.get("FIREBASE_PROJECT_ID")
    client_email = os.environ.get("FIREBASE_CLIENT_EMAIL")
    private_key = os.environ.get("FIREBASE_PRIVATE_KEY")
    if project_id and client_email and private_key:
        private_key = _normalize_private_key_pem(private_key)
        cred_dict = {
            "type": "service_account",
            "project_id": project_id,
            "private_key": private_key,
            "client_email": client_email,
            "token_uri": "https://oauth2.googleapis.com/token",
        }
        return credentials.Certificate(cred_dict)

    return None


_cred = _get_firebase_credential()
if _cred is not None:
    firebase_admin.initialize_app(_cred)

@app.route('/heartbeat')
@app.route('/timeline-sync/heartbeat')
def heartbeat():
    return 'ok'

def nightly_maintenance():
    delete_expired_pins(app)

