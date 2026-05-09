"""MCP sidecar — runs alongside app.py via supervisord.

This process is started automatically by supervisord and listens on MCP_PORT
(internal Docker network only — never exposed through Plesk).

The Hub polls GET /tools on startup to discover available tools, then forwards
Cowork calls via POST /call (JSON-RPC 2.0).
"""

import os
from makr_platform.mcp_base import MCPSidecar
from mcp_tools import register_tools

# Import your app's db module if you want the sidecar's health_check
# to report database connectivity. Remove db_check_fn if not using Postgres.
import db

sidecar = MCPSidecar(
    app_name=os.environ["APP_NAME"],
    version=os.environ.get("APP_VERSION", "dev"),
    db_check_fn=lambda: db.execute_one("SELECT 1") is not None,
)

register_tools(sidecar)

if __name__ == "__main__":
    sidecar.run(port=int(os.environ["MCP_PORT"]))
