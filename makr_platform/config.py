import os
from dataclasses import dataclass, field


@dataclass
class Config:
    hub_secret: str
    app_name: str
    app_port: int
    mcp_port: int
    app_version: str
    hub_url: str
    database_url: str
    s3_bucket: str
    s3_region: str
    aws_access_key_id: str
    aws_secret_access_key: str


_REQUIRED = ["HUB_SECRET", "APP_NAME", "APP_PORT", "MCP_PORT"]


def load_config() -> Config:
    missing = [k for k in _REQUIRED if not os.environ.get(k)]
    if missing:
        raise RuntimeError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Copy .env.example to .env and fill in all required values."
        )

    return Config(
        hub_secret=os.environ["HUB_SECRET"],
        app_name=os.environ["APP_NAME"],
        app_port=int(os.environ["APP_PORT"]),
        mcp_port=int(os.environ["MCP_PORT"]),
        app_version=os.environ.get("APP_VERSION", "dev"),
        hub_url=os.environ.get("HUB_URL", ""),
        database_url=os.environ.get("DATABASE_URL", ""),
        s3_bucket=os.environ.get("S3_BUCKET", ""),
        s3_region=os.environ.get("S3_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID", ""),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY", ""),
    )
