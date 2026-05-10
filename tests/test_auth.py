import pytest


class TestAuthGuard:
    def test_missing_token_browser_redirects_to_hub(self, client):
        r = client.get("/protected")
        assert r.status_code == 302
        assert "hub.example.com/login" in r.headers["Location"]

    def test_missing_token_json_client_returns_401(self, client):
        r = client.get("/protected", headers={"Accept": "application/json"})
        assert r.status_code == 401
        assert r.get_json()["error"] == "Authentication required"

    def test_valid_cookie_passes(self, client, valid_token):
        client.set_cookie("makr_token", valid_token)
        r = client.get("/protected")
        assert r.status_code == 200
        assert r.get_json()["user"] == "rick"

    def test_valid_bearer_passes(self, client, valid_token):
        r = client.get("/protected", headers={"Authorization": f"Bearer {valid_token}"})
        assert r.status_code == 200
        assert r.get_json()["user"] == "rick"

    def test_expired_token_browser_redirects(self, client, expired_token):
        client.set_cookie("makr_token", expired_token)
        r = client.get("/protected")
        assert r.status_code == 302
        assert "hub.example.com/login" in r.headers["Location"]

    def test_expired_token_json_returns_401(self, client, expired_token):
        client.set_cookie("makr_token", expired_token)
        r = client.get("/protected", headers={"Accept": "application/json"})
        assert r.status_code == 401
        assert "expired" in r.get_json()["error"].lower()

    def test_tampered_token_returns_redirect(self, client):
        client.set_cookie("makr_token", "totally.not.valid")
        r = client.get("/protected")
        assert r.status_code == 302

    def test_health_no_auth_required(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_version_no_auth_required(self, client):
        r = client.get("/version")
        assert r.status_code == 200


class TestContextProcessor:
    def test_hub_url_injected_into_template_context(self, app):
        with app.app_context():
            ctx = {}
            for proc in app.template_context_processors[None]:
                ctx.update(proc())
            assert ctx["hub_url"] == "https://hub.example.com"


class TestHealthBlueprint:
    def test_health_response_shape(self, client):
        data = client.get("/health").get_json()
        assert data["status"] == "ok"
        assert data["version"] == "0.0.0-test"
        assert data["app"] == "Test App"

    def test_version_response(self, client):
        data = client.get("/version").get_json()
        assert data["version"] == "0.0.0-test"
