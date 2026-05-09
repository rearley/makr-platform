import os
from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "version": os.environ.get("APP_VERSION", "dev"),
        "app": os.environ.get("APP_NAME", ""),
    })


@health_bp.route("/version")
def version():
    return jsonify({"version": os.environ.get("APP_VERSION", "dev")})
