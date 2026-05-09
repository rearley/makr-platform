"""App-specific MCP tools.

Import this module in mcp_server.py and call register_tools(sidecar) after
creating the MCPSidecar instance.

Each function decorated with @sidecar.tool becomes callable by the Hub's
MCP gateway. The function name is the tool name; the docstring is its
description (shown to Claude / Cowork).

Return values must be JSON-serialisable (dict, list, str, int, bool, None).
"""

from makr_platform.mcp_base import MCPSidecar


def register_tools(sidecar: MCPSidecar) -> None:

    @sidecar.tool
    def import_package(package: dict) -> dict:
        """Receive a JSON package pushed from Cowork and create records.

        Expected keys: (document what Cowork sends here)
        """
        # TODO: implement
        # Example: create a client from a SOW package
        # client_id = db.execute_one(
        #     "INSERT INTO clients (name) VALUES (%s) RETURNING id",
        #     (package["client_name"],)
        # )[0]
        return {"imported": True, "keys": list(package.keys())}

    @sidecar.tool
    def example_list_records() -> list:
        """Return all active records (replace with real query)."""
        # return db.execute("SELECT id, name FROM records WHERE active = true")
        return []

    @sidecar.tool
    def example_get_record(record_id: int) -> dict:
        """Return a single record by ID."""
        # row = db.execute_one("SELECT * FROM records WHERE id = %s", (record_id,))
        # if not row: return {"error": "Not found"}
        # return {"id": row[0], "name": row[1]}
        return {"id": record_id, "name": "example"}
