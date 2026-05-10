# CLAUDE.md — makr-platform

This file is read by Claude Code in every tool repo that installs `makr-platform`.
It is the contract between the platform and any AI agent working in this ecosystem.
Read this entire file before touching any code in a tool repo.

---

## What this platform is

MAKR Holdings runs a suite of Flask tool apps (Invoicing, SOW, etc.) that all share
a single sign-on system, a common AI interface (MCP), and standard deployment
infrastructure. `makr-platform` is the Python package that provides all of that
shared scaffolding.

**Three moving parts:**

```
Browser / Cowork (AI)
        │
        ▼
  ┌─────────────────────────────────────────────────────┐
  │  makr-hub  (hub.makrholdings.com)                   │
  │  Flask :5100  ─  login, dashboard, JWT issuing      │
  │  MCP   :6100  ─  MCP gateway (proxies to tools)     │
  └─────────────┬───────────────────────────────────────┘
                │  Docker internal network
     ┌──────────┼────────────────┐
     ▼                           ▼
  ┌──────────────────┐    ┌──────────────────┐
  │  makr-invoicing  │    │  makr-other-tool  │
  │  Flask :5101     │    │  Flask :5102      │
  │  MCP   :6101     │    │  MCP   :6102      │
  └──────────────────┘    └──────────────────┘
```

- **Hub** owns authentication. It issues JWTs signed with `HUB_SECRET`.
- **Tool apps** validate those JWTs on every request via `makr_platform.auth`.
- **MCP sidecars** (Flask servers running alongside each tool's Flask app) expose
  two HTTP endpoints the Hub polls: `GET /tools` and `POST /call`.
  The Hub wraps them as first-class MCP tools and presents them to Cowork.

The sidecar **is not publicly reachable**. Plesk only proxies the Flask port.
The sidecar port is internal-network only between containers.

---

## Package modules

### `makr_platform/config.py` — env var loader

```python
from makr_platform.config import load_config
cfg = load_config()   # raises RuntimeError listing all missing vars on startup
```

Call once at the top of `app.py`. If any required variable is missing the process
exits with a clear message — it never starts in a broken state.

Required vars: `HUB_SECRET`, `APP_NAME`, `APP_PORT`, `MCP_PORT`
Optional vars: `APP_VERSION` (default `"dev"`), `HUB_URL`, `DATABASE_URL`,
`S3_BUCKET`, `S3_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`

---

### `makr_platform/auth.py` — JWT middleware

```python
from makr_platform.auth import init_auth
init_auth(app)
```

Registers a `before_request` handler that:
- Reads the JWT from the `makr_token` cookie (set by the Hub on login) or
  an `Authorization: Bearer <token>` header.
- Verifies with `HUB_SECRET` / HS256. The Hub signs all tokens — tool apps
  only verify, they never issue.
- Stores the decoded payload in `flask.g.user` for downstream use
  (`g.user["sub"]` is the username).
- Exempts `/health`, `/version`, and `static` from auth.
- On missing/invalid token: redirects browsers to `{HUB_URL}/login?next=<url>`.
  Returns 401 JSON for requests with `Accept: application/json`.

**Do not call `init_auth` more than once per app.**

---

### `makr_platform/health.py` — Flask blueprint

```python
from makr_platform.health import health_bp
app.register_blueprint(health_bp)
```

Adds two unauthenticated routes:
- `GET /health` → `{"status": "ok", "version": "...", "app": "..."}`
- `GET /version` → `{"version": "..."}`

The Hub dashboard polls `/health` to show live status. The `/version` endpoint
confirms that a new deployment is live (Hub shows it in the tool cards).

---

### `makr_platform/mcp_base.py` — MCP sidecar scaffold

```python
from makr_platform.mcp_base import MCPSidecar

sidecar = MCPSidecar(
    app_name=os.environ["APP_NAME"],
    version=os.environ.get("APP_VERSION", "dev"),
    db_check_fn=lambda: db.execute_one("SELECT 1") is not None,
)
```

`MCPSidecar` is a Flask app that speaks the Hub's sidecar protocol:
- `GET /tools` — returns `{"tools": [{"name": "...", "description": "..."}]}`
- `POST /call` — JSON-RPC 2.0 body → `{"result": ...}` or `{"error": "..."}`

**Standard tools pre-registered automatically:**
- `health_check` — app name, version, uptime, db connectivity
- `get_app_info` — app name, version, list of tool names
- `import_package` — **raises `NotImplementedError` by default** (see below)

**Register custom tools with the `.tool` decorator:**

```python
@sidecar.tool
def list_clients() -> list:
    """Return all active clients."""
    return db.execute("SELECT id, name FROM clients WHERE active = true")
```

The function name becomes the tool name; the first line of the docstring is
shown to Cowork as the tool description. Return values must be JSON-serialisable.

**Start the sidecar** (in `mcp_server.py`):

```python
if __name__ == "__main__":
    sidecar.run(port=int(os.environ["MCP_PORT"]))
```

---

### `makr_platform/db.py` — Postgres connection helper

```python
from makr_platform import db
db.init_db(os.environ["DATABASE_URL"])     # once in app.py
```

Then anywhere in the app:

```python
rows = db.execute("SELECT id, name FROM clients WHERE active = %s", (True,))
row  = db.execute_one("SELECT * FROM clients WHERE id = %s", (client_id,))
```

`get_conn()` is a context manager that commits on success and rolls back on
exception. Use it directly when you need cursor-level control:

```python
with db.get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute("INSERT INTO ...")
        new_id = cur.fetchone()[0]
```

**SQLite → Postgres migration cheat sheet:**

| SQLite | Postgres |
|---|---|
| `INTEGER PRIMARY KEY AUTOINCREMENT` | `SERIAL PRIMARY KEY` |
| `datetime('now')` | `NOW()` |
| `PRAGMA foreign_keys = ON` | enabled by default |
| `?` placeholders | `%s` placeholders |
| `REAL` | `NUMERIC` or `FLOAT` |

---

### `makr_platform/storage.py` — S3 helpers

```python
from makr_platform import storage
storage.init_storage(
    bucket=os.environ["S3_BUCKET"],
    region=os.environ["S3_REGION"],
    access_key=os.environ["AWS_ACCESS_KEY_ID"],
    secret_key=os.environ["AWS_SECRET_ACCESS_KEY"],
)
```

Then:

```python
storage.upload_file(request.files["logo"], f"logos/{filename}")
url = storage.get_url(f"logos/{filename}", expires_in=3600)
data = storage.download_file("exports/report.pdf")
storage.delete_file("logos/old_logo.png")
```

`upload_file` accepts a file-like object (from `request.files`) or a local path string.

---

## Three-step wiring process

This is all it takes to integrate an existing Flask app.

**Step 1 — `requirements.txt`**

```
makr-platform @ git+ssh://git@github.com/rickearley/makr-platform.git@main
```

On the dev server the SSH agent handles auth transparently.
In GitHub Actions the runner has implicit HTTPS access to all repos in the same account — no extra config needed.

**Step 2 — `app.py`** (add three lines, nothing else changes)

```python
from makr_platform.auth import init_auth
from makr_platform.health import health_bp

app = Flask(__name__)
init_auth(app)                     # JWT check on every request
app.register_blueprint(health_bp)  # /health and /version
```

**Step 3 — `.env`** (copy from `templates/.env.example`)

The app refuses to start if any required variable is missing.

---

## Writing custom MCP tools

Create (or edit) `mcp_tools.py` in the tool repo:

```python
from makr_platform.mcp_base import MCPSidecar

def register_tools(sidecar: MCPSidecar) -> None:

    @sidecar.tool
    def import_package(package: dict) -> dict:
        """Receive a project package from Cowork and create records.

        Expected keys: client_name, project_name, budget
        """
        client_id = db.execute_one(
            "INSERT INTO clients (name) VALUES (%s) RETURNING id",
            (package["client_name"],)
        )[0]
        return {"imported": True, "client_id": client_id}

    @sidecar.tool
    def list_clients() -> list:
        """Return all active clients."""
        rows = db.execute("SELECT id, name FROM clients WHERE active = true")
        return [{"id": r[0], "name": r[1]} for r in rows]
```

Then in `mcp_server.py`:

```python
import os
from makr_platform.mcp_base import MCPSidecar
from mcp_tools import register_tools
import db

sidecar = MCPSidecar(
    app_name=os.environ["APP_NAME"],
    version=os.environ.get("APP_VERSION", "dev"),
    db_check_fn=lambda: db.execute_one("SELECT 1") is not None,
)
register_tools(sidecar)

if __name__ == "__main__":
    sidecar.run(port=int(os.environ["MCP_PORT"]))
```

**`import_package` is intentionally unimplemented by default.** If you wire up
the sidecar without overriding it, calling it returns HTTP 501 with:
`"import_package not implemented — add it to mcp_tools.py"`. This is a
deliberate fail-loud signal, not a silent no-op.

**Tool naming convention in the Hub:**
The Hub registers sidecar tools as `{tool_id}__{tool_name}`, e.g.
`invoicing__list_clients`. Keep tool names short and snake_case.

**Return format rules:**
- Always return a `dict` or `list` of dicts (not raw tuples from db).
- All values must be JSON-serialisable (no `datetime` objects — use `.isoformat()`).
- On error, raise an exception — the sidecar wraps it in a JSON-RPC error response.

---

## Hub sidecar protocol (what the Hub expects)

The Hub calls these two HTTP endpoints on startup and on each tool invocation:

```
GET  /tools
→ {"tools": [{"name": "health_check", "description": "..."},  ...]}

POST /call
body: {"jsonrpc": "2.0", "method": "list_clients", "params": {}, "id": 1}
→    {"jsonrpc": "2.0", "id": 1, "result": [...]}
  or {"jsonrpc": "2.0", "id": 1, "error": "..."}  (HTTP 500/501)
```

`MCPSidecar` implements both endpoints correctly. You never touch these directly.

---

## All environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `HUB_SECRET` | ✅ | — | JWT signing secret — must match the Hub's value exactly |
| `APP_NAME` | ✅ | — | Human-readable name (e.g. `MAKR Invoicing`) |
| `APP_PORT` | ✅ | — | Flask port (5101, 5102, …) |
| `MCP_PORT` | ✅ | — | Sidecar port — always APP_PORT + 1000 |
| `APP_VERSION` | — | `dev` | Injected by Docker `--build-arg VERSION=...` |
| `HUB_URL` | — | `https://hub.makrholdings.com` | Used for login redirects |
| `DATABASE_URL` | if using db | — | `postgresql://user:pass@host/db` |
| `S3_BUCKET` | if using storage | — | S3 bucket name |
| `S3_REGION` | if using storage | `us-east-1` | AWS region |
| `AWS_ACCESS_KEY_ID` | if using storage | — | AWS credentials |
| `AWS_SECRET_ACCESS_KEY` | if using storage | — | AWS credentials |

**Generating values:**
```bash
# HUB_SECRET — copy the value already in makr-hub's .env
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## Dockerfile + supervisord pattern

Each tool runs **two processes in one container**: Flask (the web app) and the
MCP sidecar. `supervisord` manages both. This is intentional — they share the
same Python environment, database connection pool, and business logic.

```
supervisord
├── flask  (python app.py  → port APP_PORT)
└── mcp    (python mcp_server.py → port MCP_PORT)
```

Copy `templates/supervisord.conf` and `templates/Dockerfile` into the tool repo.
Update the `EXPOSE` line in the Dockerfile to match your ports.

**Host networking:** All tool containers run with `network_mode: host`. This means:
- The app binds directly to the host port — no `ports:` mapping needed in docker-compose.
- `DATABASE_URL` uses `localhost` to reach the host Postgres (not `host.docker.internal`).
- `extra_hosts: host.docker.internal:host-gateway` is not needed.
- This matches how all tools (including DayCompass) are deployed on this server.

The sidecar port is **never exposed through Plesk**. Plesk only proxies APP_PORT.
MCP_PORT is reachable on the host network by the Hub container.

---

## GitHub Actions deploy workflow

`templates/.github/workflows/deploy.yml` builds a Docker image on every push
to `main` (and on version tags) and pushes to `ghcr.io`.

**Private dependency auth:**
`requirements.txt` uses the SSH URL (`git+ssh://git@github.com/rickearley/makr-platform.git`).

- **Dev server**: the SSH agent supplies credentials automatically — no extra config.
- **GitHub Actions**: the Actions runner has implicit HTTPS access to all repos in the
  same account, so the SSH URL resolves without any secrets or build args.
- **CI fallback**: if a future Actions run fails to pull `makr-platform`, add this line
  to the Dockerfile before the `pip install` step:
  ```dockerfile
  RUN git config --global url."https://github.com/".insteadOf "git+ssh://git@github.com/"
  ```

**Version stamping:**
The workflow passes `--build-arg VERSION=<git-ref>` so the running container
knows its own version. The Hub reads `/version` from each tool and displays it
in the dashboard, confirming a deploy is live.

---

## Deployment checklist for a new tool on Plesk

1. Push repo to GitHub → Actions builds and pushes image to `ghcr.io`.
2. On Plesk server:
   ```bash
   docker pull ghcr.io/rearley/<tool-name>:latest
   docker run -d \
     --name <tool-name> \
     --env-file /path/to/.env \
     -p APP_PORT:APP_PORT \
     -p MCP_PORT:MCP_PORT \
     --label com.centurylinklabs.watchtower.enable=true \
     --restart unless-stopped \
     ghcr.io/rearley/<tool-name>:latest
   ```
3. Create subdomain `<tool>.makrholdings.com` on Plesk.
4. Add nginx proxy config from `templates/vhost_nginx.conf` (swap APP_PORT).
5. Add entry to `makr-hub/tools.yaml`:
   ```yaml
   - id: <tool-name>
     name: MAKR Tool Name
     url: https://<tool>.makrholdings.com
     description: One line description
     icon: 🔧
     mcp_port: MCP_PORT
   ```
6. Restart the Hub (or send SIGHUP) so it discovers the new sidecar tools.
7. Confirm: Hub dashboard shows the tool as healthy; `/version` shows the right tag.

Watchtower polls `ghcr.io` every 5 minutes and auto-restarts containers when
a new image is pushed — no manual redeploy needed after the initial setup.
