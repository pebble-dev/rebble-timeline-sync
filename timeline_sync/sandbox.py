from flask import Blueprint, jsonify

sandbox = Blueprint('sandbox', __name__)


@sandbox.route('/<uuid>')
def get_sandbox_token(uuid):
    result = {"uuid": uuid}

    # TODO: check uuid, user auth, dev portal permissions? and actually get/generate token with database
    result["token"] = "sandbox-token-test"

    return jsonify(result)


def init_sandbox(app, url_prefix='/v1/tokens/sandbox'):
    app.register_blueprint(sandbox, url_prefix=url_prefix)
