import json
import pytest


# ── /tools endpoint ─────────────────────────────────────────────────────────


class TestToolsEndpoint:
    def test_returns_standard_tools(self, mcp_client):
        data = mcp_client.get("/tools").get_json()
        names = [t["name"] for t in data["tools"]]
        assert "health_check" in names
        assert "get_app_info" in names
        assert "import_package" in names

    def test_each_tool_has_name_and_description(self, mcp_client):
        data = mcp_client.get("/tools").get_json()
        for tool in data["tools"]:
            assert "name" in tool
            assert "description" in tool

    def test_custom_tool_appears_in_list(self, mcp, mcp_client):
        @mcp.tool
        def my_custom_tool() -> dict:
            """Custom tool for testing."""
            return {}

        data = mcp_client.get("/tools").get_json()
        names = [t["name"] for t in data["tools"]]
        assert "my_custom_tool" in names


# ── /call endpoint — standard tools ─────────────────────────────────────────


def rpc(client, method, params=None):
    body = {"jsonrpc": "2.0", "method": method, "id": 1}
    if params:
        body["params"] = params
    return client.post("/call", json=body)


class TestHealthCheck:
    def test_returns_expected_shape(self, mcp_client):
        data = rpc(mcp_client, "health_check").get_json()
        result = data["result"]
        assert result["app"] == "Test App"
        assert result["version"] == "0.0.0-test"
        assert isinstance(result["uptime_seconds"], float)
        assert result["db_ok"] is True

    def test_db_ok_false_when_check_fails(self, mcp_client):
        from makr_platform.mcp_base import MCPSidecar
        bad_sidecar = MCPSidecar("Fail App", "0.1", db_check_fn=lambda: 1 / 0)
        bad_sidecar._flask.config["TESTING"] = True
        c = bad_sidecar._flask.test_client()
        data = rpc(c, "health_check").get_json()
        assert data["result"]["db_ok"] is False

    def test_no_db_key_when_no_check_fn(self, mcp_client):
        from makr_platform.mcp_base import MCPSidecar
        s = MCPSidecar("No DB App", "0.1")
        s._flask.config["TESTING"] = True
        c = s._flask.test_client()
        data = rpc(c, "health_check").get_json()
        assert "db_ok" not in data["result"]


class TestGetAppInfo:
    def test_returns_app_and_tool_list(self, mcp_client):
        data = rpc(mcp_client, "get_app_info").get_json()
        result = data["result"]
        assert result["app"] == "Test App"
        assert "health_check" in result["tools"]
        assert "import_package" in result["tools"]


class TestImportPackage:
    def test_default_raises_not_implemented(self, mcp_client):
        r = rpc(mcp_client, "import_package", {"package": {"foo": "bar"}})
        data = r.get_json()
        assert r.status_code == 501
        assert "import_package not implemented" in data["error"]
        assert "mcp_tools.py" in data["error"]

    def test_overridden_import_package_is_called(self, mcp, mcp_client):
        @mcp.tool
        def import_package(package: dict) -> dict:
            """Custom import_package."""
            return {"received": True, "keys": list(package.keys())}

        data = rpc(mcp_client, "import_package", {"package": {"name": "ACME"}}).get_json()
        assert data["result"]["received"] is True
        assert "name" in data["result"]["keys"]


class TestCallRouteEdgeCases:
    def test_unknown_method_returns_404_error(self, mcp_client):
        r = rpc(mcp_client, "nonexistent_tool")
        assert r.status_code == 404
        assert "Unknown tool" in r.get_json()["error"]

    def test_custom_tool_is_callable(self, mcp, mcp_client):
        @mcp.tool
        def ping() -> dict:
            """Simple ping."""
            return {"pong": True}

        data = rpc(mcp_client, "ping").get_json()
        assert data["result"]["pong"] is True

    def test_tool_exception_returns_500(self, mcp, mcp_client):
        @mcp.tool
        def broken_tool() -> dict:
            """This tool always fails."""
            raise ValueError("something went wrong")

        r = rpc(mcp_client, "broken_tool")
        assert r.status_code == 500
        assert "something went wrong" in r.get_json()["error"]
