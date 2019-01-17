from flask import Flask

from .settings import config
from .api import init_api

app = Flask(__name__)
app.config.update(**config)
init_api(app)
