import os
import jwt
from flask import g, redirect, request, jsonify


_EXEMPT_ENDPOINTS = {"health.health", "health.version", "static"}
_EXEMPT_PREFIXES = ("/health", "/version")


def init_auth(app):
    """Register JWT authentication on every request.

    Reads HUB_SECRET from the environment at request time so the app can
    start before the config is fully validated (useful in testing).
    """

    @app.before_request
    def _check_auth():
        if request.endpoint in _EXEMPT_ENDPOINTS:
            return
        if request.path.startswith(_EXEMPT_PREFIXES):
            return

        token = (
            request.cookies.get("makr_token")
            or _bearer_token(request.headers.get("Authorization", ""))
        )

        if not token:
            return _unauthorized(request)

        secret = os.environ.get("HUB_SECRET", "")
        try:
            payload = jwt.decode(token, secret, algorithms=["HS256"])
            g.user = payload
        except jwt.ExpiredSignatureError:
            return _unauthorized(request, "Token expired")
        except jwt.InvalidTokenError:
            return _unauthorized(request, "Invalid token")


def _bearer_token(header: str) -> str:
    if header.startswith("Bearer "):
        return header[7:].strip()
    return ""


def _unauthorized(req, reason: str = "Authentication required"):
    wants_json = "application/json" in req.headers.get("Accept", "")
    if wants_json:
        return jsonify({"error": reason}), 401

    hub_url = os.environ.get("HUB_URL", "https://hub.makrholdings.com")
    next_url = req.url
    return redirect(f"{hub_url}/login?next={next_url}")
