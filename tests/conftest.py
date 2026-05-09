import os
import time
import pytest
import jwt

# Set env vars before any app imports
os.environ.setdefault("HUB_SECRET", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("APP_NAME", "Test App")
os.environ.setdefault("APP_PORT", "5999")
os.environ.setdefault("MCP_PORT", "6999")
os.environ.setdefault("APP_VERSION", "0.0.0-test")
os.environ.setdefault("HUB_URL", "https://hub.example.com")

from flask import Flask
from makr_platform.auth import init_auth
from makr_platform.health import health_bp
from makr_platform.mcp_base import MCPSidecar

SECRET = os.environ["HUB_SECRET"]


# ── Flask app fixtures ──────────────────────────────────────────────────────


@pytest.fixture()
def app():
    flask_app = Flask(__name__)
    flask_app.config["TESTING"] = True
    init_auth(flask_app)
    flask_app.register_blueprint(health_bp)

    @flask_app.route("/protected")
    def protected():
        from flask import g
        return {"user": g.user.get("sub")}

    return flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def valid_token():
    now = int(time.time())
    return jwt.encode(
        {"sub": "rick", "iat": now, "exp": now + 28800},
        SECRET,
        algorithm="HS256",
    )


@pytest.fixture()
def expired_token():
    now = int(time.time())
    return jwt.encode(
        {"sub": "rick", "iat": now - 36000, "exp": now - 100},
        SECRET,
        algorithm="HS256",
    )


# ── MCP sidecar fixtures ────────────────────────────────────────────────────


@pytest.fixture()
def mcp():
    def db_check():
        return True

    return MCPSidecar("Test App", "0.0.0-test", db_check_fn=db_check)


@pytest.fixture()
def mcp_client(mcp):
    mcp._flask.config["TESTING"] = True
    return mcp._flask.test_client()
