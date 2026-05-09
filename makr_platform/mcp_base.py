import inspect
import os
import time
from flask import Flask, jsonify, request


class MCPSidecar:
    """HTTP sidecar that exposes the two endpoints the Hub expects.

    GET  /tools  ->  {"tools": [{"name": "...", "description": "..."}]}
    POST /call   ->  JSON-RPC 2.0  ->  {"result": ...} | {"error": "..."}

    Usage in mcp_server.py:
        from makr_platform.mcp_base import MCPSidecar
        from mcp_tools import register_tools

        sidecar = MCPSidecar(
            app_name=os.environ["APP_NAME"],
            version=os.environ.get("APP_VERSION", "dev"),
            db_check_fn=lambda: db.execute_one("SELECT 1") is not None,
        )
        register_tools(sidecar)

        if __name__ == "__main__":
            sidecar.run(port=int(os.environ["MCP_PORT"]))
    """

    def __init__(self, app_name: str, version: str, db_check_fn=None):
        self._app_name = app_name
        self._version = version
        self._db_check_fn = db_check_fn
        self._start_time = time.monotonic()
        self._tools: dict = {}
        self._flask = Flask(__name__)
        self._register_standard_tools()
        self._register_routes()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def tool(self, fn):
        """Decorator: register a callable as an MCP tool.

        The tool name is the function name; the description is its docstring.
        Registering a tool with the same name as a standard tool overrides it.
        """
        self._tools[fn.__name__] = fn
        return fn

    def run(self, port: int) -> None:
        self._flask.run(host="0.0.0.0", port=port)

    # ------------------------------------------------------------------
    # Standard tools
    # ------------------------------------------------------------------

    def _register_standard_tools(self):
        sidecar = self  # captured for closures

        def health_check() -> dict:
            """Return app version, uptime, and database connectivity."""
            db_ok = None
            if sidecar._db_check_fn:
                try:
                    db_ok = bool(sidecar._db_check_fn())
                except Exception:
                    db_ok = False

            result = {
                "app": sidecar._app_name,
                "version": sidecar._version,
                "uptime_seconds": round(time.monotonic() - sidecar._start_time, 1),
            }
            if db_ok is not None:
                result["db_ok"] = db_ok
            return result

        def get_app_info() -> dict:
            """Return app name, version, and the list of available MCP tools."""
            return {
                "app": sidecar._app_name,
                "version": sidecar._version,
                "tools": list(sidecar._tools.keys()),
            }

        def import_package(package: dict) -> dict:
            """Receive a JSON package pushed from Cowork (e.g. a SOW payload).

            Override this tool in mcp_tools.py to handle the package:
                @sidecar.tool
                def import_package(package: dict) -> dict:
                    ...
            """
            raise NotImplementedError(
                "import_package not implemented — add it to mcp_tools.py"
            )

        self._tools["health_check"] = health_check
        self._tools["get_app_info"] = get_app_info
        self._tools["import_package"] = import_package

    # ------------------------------------------------------------------
    # Flask routes
    # ------------------------------------------------------------------

    def _register_routes(self):
        sidecar = self

        @self._flask.route("/tools")
        def list_tools():
            tools = [
                {
                    "name": name,
                    "description": (inspect.getdoc(fn) or "").split("\n")[0],
                }
                for name, fn in sidecar._tools.items()
            ]
            return jsonify({"tools": tools})

        @self._flask.route("/call", methods=["POST"])
        def call_tool():
            body = request.get_json(silent=True) or {}
            method = body.get("method", "")
            params = body.get("params") or {}
            rpc_id = body.get("id", 1)

            fn = sidecar._tools.get(method)
            if fn is None:
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": f"Unknown tool: '{method}'",
                }), 404

            try:
                result = fn(**params) if params else fn()
                return jsonify({"jsonrpc": "2.0", "id": rpc_id, "result": result})
            except NotImplementedError as e:
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": str(e),
                }), 501
            except Exception as e:
                return jsonify({
                    "jsonrpc": "2.0",
                    "id": rpc_id,
                    "error": str(e),
                }), 500
