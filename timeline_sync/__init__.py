from flask import Flask

from .settings import config
from .sandbox import init_sandbox

app = Flask(__name__)
app.config.update(**config)
init_sandbox(app)
