from flask import Flask

from .settings import config
from .api import init_api
from .models import init_app

app = Flask(__name__)
app.config.update(**config)
init_app(app)
init_api(app)  # Includes both private (timeline-sync) and public (timeline-api) APIs
