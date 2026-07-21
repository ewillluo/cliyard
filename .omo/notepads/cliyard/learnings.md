
## Test Infrastructure (Task 6)

- `schema/types.py` defines 11 TypedDict types (ServiceSpec, ResourceSpec, etc.) — all importable
- pytest fixtures in conftest.py use Path-based fixture loading with yaml.safe_load
- All 6 smoke tests pass (0.16s), covering: imports, fixture loading, shape validation, bad fixture detection
- `run_tests.sh` activates venv if present, passes through extra args via "$@"

## Runtime Pipeline (Task: run_with_spec)

- `--spec-dir` option requires sys.argv interception BEFORE Click command resolution.
  Using `invoke_without_command=True` + `@click.pass_context` does not work because
  Click resolves the command name (e.g. `repos`) before invoking the group callback,
  and the spec-driven commands don't exist as registered Click subcommands.
  Solution: `_intercept_spec_dir()` scans sys.argv for `--spec-dir`, extracts the
  value, removes both flag and value from argv, then delegates to `run_with_spec()`.
- `run_with_spec()` calls `sys.exit()` (NoReturn) so the main CLI code after the
  interception call is never reached when `--spec-dir` is used.
- Test fixture spec directory created at `tests/fixtures/spec-dir/` with `_service.yaml`
  and `repos.yaml` for live integration verification.
- All 73 existing tests still pass after changes.

## Search SDK Analysis (ketacli search → cliyard plugin)

### 1. API Endpoints

Base URL pattern: `{endpoint}/api/v1/jobs` (client.py ROOT_PATH = "api/v1")

| Endpoint | Method | File | Function |
|----------|--------|------|----------|
| `POST /api/v1/jobs` | POST | search.py:42 | `create_search_job()` |
| `GET /api/v1/jobs/{jobid}` | GET | search.py:49 | `get_search_job_status()` |
| `GET /api/v1/jobs/{jobid}/results` | GET | search.py:55 | `get_search_job_result()` |
| `GET /api/v1/jobs/{jobid}/summary` | GET | search.py:58 | `get_search_job_summary()` |

### 2. Request/Response Formats

#### POST /api/v1/jobs (Create Job)

Request body (JSON, gzipped by default via `request_post` with `_gzip=True`):

```json
{
    "query": "<spl string>",
    "startTime": <int: epoch ms>,
    "endTime": <int: epoch ms>,
    "collectSize": <int: limit, default 100>,
    "timeout": <int: ms, default 1000>,
    "app": "search",
    "preview": false,
    "mode": "smart"
}
```

- `startTime`/`endTime`: defaults to last 5 minutes if not provided. Accepts both `datetime` objects and raw int timestamps (epoch ms).
- `collectSize`: maps to CLI `--limit` flag (default 100).
- `timeout`: hardcoded to 3000ms in `search_spl()`, adjustable in `search_spl_meta()`.

Response (sync completion): `{"meta": {"process": 1, "failed": null, "resultSize": N}, "result": {"fields": [...], "rows": [...]}}`
Response (async): `{"id": "<job-uuid>"}` — then poll for completion.

#### GET /api/v1/jobs/{jobid} (Poll Status)

Response when done: `{"process": 1, "meta": {"resultSize": N}}`
Response when running: `{"process": 0}`

Polling loop in `search_spl()`: `time.sleep(0.2)` every iteration. No max retries.

#### GET /api/v1/jobs/{jobid}/results (Fetch Results)

Response:
```json
{
    "fields": [{"name": "field1"}, {"name": "field2"}, ...],
    "rows": [["val1", "val2"], ...]
}
```

`fields` is a list of dicts with `name` key. `rows` is a list of lists.

Error response handling: `resp.get("failed")` returns `{"failed": "...", "fields": [], "rows": []}` for proper error rendering.

#### GET /api/v1/jobs/{jobid}/summary (Fetch Summary)

Used by `search_spl_meta()` for debug mode. Returns aggregate statistics about the query results.

### 3. SPL Parsing Logic

There is NO client-side SPL parsing. The SPL string is passed verbatim as the `query` field in the job creation request. The server handles all SPL parsing and execution. The CLI just:

1. Accepts SPL as a positional argument: `ketacli search 'search2 repo="*"'`
2. Parses `--start` / `--end` from CLI string format `"YYYY-MM-DD HH:MM:SS"` → `datetime` → epoch ms
3. Passes everything to `create_search_job(query=spl, ...)`

### 4. Output Formatting Pipeline

Pipeline: `search_spl() → search_result_output() → format_table() → console.print()`

#### Phase 1: `search_spl()` (search.py:60)

```python
resp = create_search_job(query=spl, start=start, end=end, limit=limit, timeout_ms=req_timeout)
# if sync completion → returns resp["result"] immediately
# otherwise → poll → returns get_search_job_result(jobid)
# error: returns {"failed": "...", "fields": [], "rows": []}
```

Returns raw server response: `{"fields": [...], "rows": [...]}`

#### Phase 2: `search_result_output()` (output.py:101)

```python
def search_result_output(result=None, transpose=False):
    header = [f["name"] for f in result["fields"]]  # extract field names
    rows = result["rows"]
    return make_table(header, rows, transpose)  # → OutputTable
```

Simplicity: no `field_aliases`, no `field_converters`, no `find_result_field`. Just straight header-from-fields + rows.

#### Phase 3: `format_table()` (format.py:154)

```python
def format_table(table, format=None, prettify=True, raw_output=False):
    if prettify and not raw_output:
        table = table.prettify()  # timestamp formatting
    if format == "json":
        return table.get_json_string()
    return table.get_formatted_string(format)  # "table" → Rich Table
```

#### OutputTable (format.py:10-71)

Core types:
- `get_json_string()`: list-of-dicts with `ensure_ascii=False`
- `get_formatted_string(format)`:
  - `"table"`: Rich `Table(expand=True, header_style="bold magenta")` with `overflow="fold"`
  - `"toon"`: toon_py encoding
  - other: PrettyTable `get_formatted_string()` (text, csv, html, latex)
- `prettify()`: timestamps ending in "time" → `datetime.fromtimestamp(val/1000).strftime('%Y-%m-%d %H:%M:%S')`

Supported formats: `table`, `text`, `json`, `csv`, `html`, `latex`, `toon`

Key detail: `make_table()` creates OutputTable with `transpose=False`. The search output is always a NxM matrix, never transposed (unlike `get_asset_output` which uses `["field", "value"]` transposition).

### 5. Watch Mode (--watch)

In `search.py:58-70`:

```python
if watch:
    table_func = generate_table_with_debug if debug else generate_table
    with Live(table_func(), console=console, refresh_per_second=1) as live:
        while True:
            table, is_error = table_func()
            if is_error or table is None: break
            live.update(table)
            time.sleep(interval)
```

Uses Rich `Live` context manager. Re-runs the full search pipeline every `--interval` seconds (default 3.0). On `KeyboardInterrupt`, `live.stop()` + `sys.exit()`. No cleanup of old data — just replaces the live display.

### 6. Debug Mode (--debug)

In `search.py:45-56`:

```python
def generate_table_with_debug():
    # Fire TWO API calls in sequence:
    # 1. search_spl_meta() — fires search_spl job, accumulates elapsed time
    # 2. search_spl() — fires ANOTHER job (same params) for display
    meta_resp = search_spl_meta(spl=spl, start=start_ts, end=end_ts, limit=limit)
    resp = search_spl(spl=spl, start=start, end=end, limit=limit)
    ...
    console.print(f"[dim][DEBUG] Server query duration: {meta_resp.get('duration', 0)}ms[/dim]")
```

`search_spl_meta()` (search.py:89-124):
- Converts start/end to epoch ms (int * 1000)
- Calls `create_search_job()` with `return_type="raw"` (returns `requests.Response` not `.json()`)
- Accumulates `resp.elapsed.total_seconds() * 1000` for each API call duration
- Also polls status with `return_type="raw"` to accumulate polling time
- Returns `{"duration": N, "status_code": N, "resultSize": N, "query": ..., "range": ...}`

Important: debug mode fires TWO independent search jobs (one for meta timing, one for display). This means the displayed data may differ from the timed data.

### 7. Auth / Client Config

`client.py`:
- Auth: Bearer token from `~/.keta/config.yaml` (default cluster) or `KETA_SERVICE_ENDPOINT`/`KETA_SERVICE_TOKEN` env vars
- `_cluster_override` global: set via `set_cluster_override(name)` — used for `-c/--cluster` CLI flag
- `request()`: builds URL as `{endpoint}/api/v1/{path}`, adds `Authorization: Bearer {token}`, timeout 300s
- `request_post()`: calls `request('post', ...)` with `_gzip=True` by default (gzip-compresses JSON body)
- Error handling: 400→499 raises `Exception("Bad request", ...)`, 500→599 raises `Exception("Server error", ...)`
- `format_error()`: extracts Code/Message from JSON response body, escapes Rich markup

### 8. Key Design Patterns for Plugin Replication

All search functions accept these params:
- `spl`: the raw SPL query string (NOT parsed client-side)
- `start`: `datetime` object or None (defaults to now-5min)
- `end`: `datetime` object or None (defaults to now)
- `limit`: int, default 100
- `req_timeout` / `timeout_ms`: int, default 3000ms (for the job completion wait, not HTTP timeout)
- `return_type`: "json" (returns dict) or "raw" (returns Response)

The search flow has two paths:
1. **Sync completion**: if `meta.process == 1` in first response, return immediately
2. **Async polling**: otherwise poll `GET /jobs/{id}` with 200ms intervals until `process == 1`

Error pattern: `{"failed": "error message", "fields": [], "rows": []}` — empty fields/rows so downstream formatting always works.

### 9. cliyard Plugin Integration Notes

For `@register_method("search_spl")`:
- Need an HTTP POST endpoint that accepts: `query`, `startTime`, `endTime`, `collectSize`, `timeout`
- Need polling via GET to `jobs/{id}` with `process` field check
- Need results via GET to `jobs/{id}/results` returning `{fields: [...], rows: [...]}`
- Output should produce same `OutputTable`-compatible structure for `format_table()`
- Watch mode can be replicated with Rich `Live` + sleep loop
- Debug mode fires two sequential search jobs (one for timing, one for display)

The `search_spl()` function (search.py:60) is the most complete entry point — it handles:
- Job creation
- Sync vs async detection  
- Polling
- Error extraction
- Result retrieval
All in ~16 lines. Replicating this core loop is the main task.

---

## Multi-Server Support: Current State Analysis & Change Plan

### 0. Goal

Transform the current single-server model into a multi-server model where:

```yaml
# _auth.yaml — server becomes a named list
server:
  - name: serve1
    base_url: http://localhost:8080
    prefix: /api/v1
  - name: serve2
    base_url: https://other.com
    prefix: /api/v2
```

Resource YAMLs and auth steps can specify `server: serve1` to select which server.

### 1. Current Server Resolution Flow

#### 1a. `loader.py` → `load_service()` (L28–101)

```python
service = _load_yaml(service_path)  # parse _auth.yaml

# Current validation:
# L63: isinstance(server, dict) — REJECTS list format
# L65: server["server"]["base_url"] must exist
```

**Current behavior:** Validates `server` is a single `dict` with `base_url`. Returns `service["server"]` as `{base_url: "…", prefix: "…"}`.

**Already broken:** The ketaops example already uses the list format (L25–28):
```yaml
server:
  - name: serve1
    base_url: http://localhost:8080
    prefix: /api/v1
```
This will raise `ValueError` at L63 because `isinstance(server, dict)` is `False` for a list.

#### 1b. `runner.py` → `create_cli()` (L23–170)

Flow:
```
L50: server = service.get("server", {})                  # single dict
L54–57: saved_profile = get_current_profile()
        saved_endpoint = saved_profile.get("endpoint")
        base_url = saved_endpoint or server.get("base_url", "http://localhost:8080")  # ← single string
L86–91: ctx = ServiceContext(
            base_url=base_url,                           # single base_url
            prefix=server.get("prefix", ""),              # single prefix
            auth_spec=auth_spec,
            pre_filled_auth=pre_filled,
        )
L101: add_auth_commands(cli, service, base_url=server.get("base_url", ...))  # ← single base_url
L131: grp = build_resource_group(resource["name"], resource, ctx)  # ctx has single server
```

**Key observation:** The profile's saved `endpoint` can override the YAML `base_url`, but there's no notion of which server the endpoint belongs to.

#### 1c. `builder.py` → `ServiceContext` (L29–42)

```python
@dataclass
class ServiceContext:
    base_url: str        # ← single string
    prefix: str = ""     # ← single string
    auth_spec: dict | None = None
    pre_filled_auth: dict | None = None
```

This is passed through **all** builder/callback functions. Every callback that needs to make HTTP requests uses `service_ctx.base_url`:

| Location | Usage |
|---|---|
| L276 | `_HC(service_ctx.base_url)` — field resolver |
| L303 | `HttpClient(service_ctx.base_url)` — auth chain in callback |
| L319 | `assemble_request(..., base_url=service_ctx.base_url, prefix=service_ctx.prefix)` |
| L526 | `HttpClient(ctx.base_url)` — plugin callback |

#### 1d. `assembler.py` → `assemble_request()` (L113–281)

Receives `base_url` and `prefix` as separate params. No awareness of multi-server. URL construction:

```python
base, base_path = _strip_url_path(base_url)  # split scheme+host from path
full_url = _join_path(base, base_path, prefix, rendered_path)
```

**No change needed here** — as long as we pass the correct `(base_url, prefix)` pair, the assembler works fine.

#### 1e. `auth.py` → `run_auth_chain()` (L146–279)

Receives `http_client` (already initialized with a `base_url`). Auth steps that make HTTP requests (login steps) use `http_client.request(url=endpoint)` which prepends `http_client.base_url` for relative paths.

**No awareness of server identity.** The `http_client` is created once with a base URL, and all auth steps use the same client.

#### 1f. `credentials.py` (L1–154)

Profile-based storage at `~/.cliyard/credentials.yaml`:

```yaml
profiles:
  prod:
    endpoint: https://prod.example.com
    token: eyJ...
  dev:
    endpoint: https://dev.example.com
    token: eyJ...
current: dev
```

Profiles are identified by name and store `endpoint` + `token` (+ optional `expires_at`). **No association with server names from YAML.**

#### 1g. `auth_commands.py` → `add_auth_commands()` (L25–143)

```python
def add_auth_commands(cli, service, base_url: str = "") -> None:
```

Receives a single `base_url` string. The `auth add` command:
```
L46: _base_url = endpoint or base_url  # endpoint from -e flag, or YAML base_url
L47: client = HttpClient(_base_url)
L49: save_profile(profile_name, {"token": token, "endpoint": _base_url}, ...)
L73: fields = {"endpoint": base_url}  # ← BUG: uses base_url not _base_url when saving after login chain
```

**Bug on L73:** Uses `base_url` (YAML default) instead of `_base_url` (user-specified via `-e`) when saving credentials after a login chain. This means `auth add -e https://custom.com` will still save `endpoint: http://localhost:8080` if the password-based login path is taken.

#### 1h. `cli/auth_cmd.py` → `auth_login()` (L29–113)

```python
L58: server = service.get("server", {})          # single dict
L59: base_url = server.get("base_url", "...")     # single string
L60: client = HttpClient(base_url)                # single server
```

Same pattern — single server assumption.

#### 1i. `schema/validator.py` → `validate_service()` (L36–86)

```python
L58: server = spec.get("server")
L59: if isinstance(server, dict):
L60:     _require_non_empty(server, filename, "server", "base_url", result)
```

Only validates `dict` format. No handling for `list` format.

#### 1j. `schema/types.py` → `ServerConfig` (L30–42)

```python
class ServerConfig(TypedDict, total=False):
    base_url: str
    prefix: str
    timeout: int
```

No `name` field. `ServiceSpec.server` is typed as `ServerConfig` (single), not `ServerConfig | list[ServerConfig]`.

#### 1k. `cli/gen.py` → `gen()` (L249–361)

Generates scaffold `_auth.yaml` with single-server format:
```yaml
server:
  base_url: http://localhost:8080
```

### 2. All Files Touching `server` / `base_url`

| File | Line(s) | Current Pattern | Change Needed? |
|---|---|---|---|
| `engine/loader.py` | L63–68 | `isinstance(server, dict)` validation | **YES** — accept both dict and list |
| `runtime/runner.py` | L50–57 | Single `server.get("base_url")` | **YES** — resolve server by name |
| `runtime/runner.py` | L86–91 | `ServiceContext(base_url=...)` | **YES** — pass all servers |
| `runtime/runner.py` | L101 | `add_auth_commands(cli, ..., base_url=...)` | **YES** — pass all servers |
| `engine/builder.py` | L29–42 | `ServiceContext` with single `base_url` | **YES** — hold servers map |
| `engine/builder.py` | L204–389 | `_make_callback` uses `service_ctx.base_url` | **YES** — resolve per-resource server |
| `engine/builder.py` | L396–489 | `build_list_command`, `build_operation_command` | **YES** — pass correct server to callback |
| `engine/builder.py` | L492–542 | `_make_plugin_callback` uses `ctx.base_url` | **YES** — resolve per-resource server |
| `engine/builder.py` | L545–582 | `build_resource_group` | **YES** — read `server` from resource spec |
| `engine/assembler.py` | L113–281 | `assemble_request(base_url, prefix)` | **NO** — already parameterized |
| `client/auth.py` | L146–279 | `run_auth_chain(auth_spec, http_client)` | **YES** — auth steps may pick server |
| `client/http.py` | L8–45 | `HttpClient(base_url)` | **NO** — already parameterized |
| `client/credentials.py` | L1–154 | Profiles with `endpoint` | **MAYBE** — add server_name association |
| `runtime/auth_commands.py` | L25–143 | `add_auth_commands(cli, service, base_url)` | **YES** — multi-server auth |
| `runtime/auth_commands.py` | L46–52, L73 | `base_url` vs `_base_url` bug | **YES** — fix bug + multi-server |
| `cli/auth_cmd.py` | L58–60 | Single `server.get("base_url")` | **YES** |
| `schema/validator.py` | L58–60 | Only validates dict format | **YES** — validate list format |
| `schema/types.py` | L30–42 | `ServerConfig` has no `name` | **YES** — add `name`, update `ServiceSpec` |
| `cli/gen.py` | L300–306 | Scaffold uses single-server format | **NO** — backward compat via dict→list conversion |

### 3. Change Plan

#### Phase 1: Schema & Validation (low risk, no behavior change)

**File: `schema/types.py`**
- Add `name: str` to `ServerConfig`
- Add `default: bool` to `ServerConfig` (for marking default server)
- Change `ServiceSpec.server` to `ServerConfig | list[ServerConfig]`

**File: `schema/validator.py`**
- `validate_service()`: handle both `dict` (legacy) and `list` (new):
  ```python
  server = spec.get("server")
  if isinstance(server, dict):
      _require_non_empty(server, filename, "server", "base_url", result)
  elif isinstance(server, list):
      for i, srv in enumerate(server):
          _require_non_empty(srv, filename, f"server[{i}]", "name", result)
          _require_non_empty(srv, filename, f"server[{i}]", "base_url", result)
  else:
      result.add(filename, "server", "must be a dict or list")
  ```
- Update `_VALID_AUTH_TYPES` if `plugin:*` types are valid (currently L93 only has `{"env", "login", "inject"}` but ketaops uses `plugin:keta_login`)

#### Phase 2: Loader Normalization (backward-compatible)

**File: `engine/loader.py` → `load_service()`**

```python
# New normalized format: always return servers as list of dicts
server_raw = service.get("server")
if isinstance(server_raw, dict):
    # Legacy single-server → normalize to list
    servers = [{"name": "default", **server_raw}]
elif isinstance(server_raw, list):
    servers = server_raw
    # Validate each has name + base_url
    for srv in servers:
        if not srv.get("name"):
            raise ValueError("Each server entry must have a 'name' field")
        if not srv.get("base_url"):
            raise ValueError(f"Server '{srv.get('name', '?')}' must have 'base_url'")
else:
    raise ValueError("'server' must be a dict or list of dicts")

service["servers"] = servers  # normalized
# Keep service["server"] as first/default server for backward compat
service["server"] = servers[0]
```

#### Phase 3: ServiceContext Evolution

**File: `engine/builder.py` → `ServiceContext`**

```python
@dataclass
class ServerInfo:
    name: str
    base_url: str
    prefix: str = ""

@dataclass
class ServiceContext:
    servers: dict[str, ServerInfo]  # name → server info
    auth_spec: dict | None = None
    pre_filled_auth: dict | None = None

    @property
    def base_url(self) -> str:
        """Backward-compat: return default server's base_url."""
        return self.get_server().base_url

    @property
    def prefix(self) -> str:
        """Backward-compat: return default server's prefix."""
        return self.get_server().prefix

    def get_server(self, name: str | None = None) -> ServerInfo:
        """Resolve a server by name. Falls back to first/default server."""
        if name and name in self.servers:
            return self.servers[name]
        # Return first server (or the one marked default)
        for s in self.servers.values():
            return s
        raise ValueError("No servers configured")
```

This preserves backward compatibility — existing code using `ctx.base_url` and `ctx.prefix` continues to work via properties.

#### Phase 4: Runner Adaptation

**File: `runtime/runner.py` → `create_cli()`**

```python
# Normalize servers (loader already normalized to list)
servers_raw: list[dict] = service.get("servers", [])
server_map: dict[str, ServerInfo] = {}
for srv in servers_raw:
    server_map[srv["name"]] = ServerInfo(
        name=srv["name"],
        base_url=srv.get("base_url", "http://localhost:8080"),
        prefix=srv.get("prefix", ""),
    )

# Override default server's base_url from saved profile endpoint
saved_profile = get_current_profile()
if saved_profile and saved_profile.get("endpoint"):
    default_server_name = saved_profile.get("server_name", next(iter(server_map)))
    if default_server_name in server_map:
        server_map[default_server_name].base_url = saved_profile["endpoint"]

# Pre-filled auth (unchanged)

ctx = ServiceContext(
    servers=server_map,
    auth_spec=auth_spec,
    pre_filled_auth=pre_filled,
)

# Pass all servers to auth commands
add_auth_commands(cli, service, servers=server_map)
```

#### Phase 5: Callback Server Resolution

**File: `engine/builder.py` → callback factories**

In `_make_callback()`, `_make_plugin_callback()`, `build_list_command()`, `build_operation_command()`, and `build_resource_group()`:

```python
# build_resource_group() reads resource-level server:
resource_server = resource_spec.get("server", None)  # "serve1" or None

# Inside _make_callback():
server = service_ctx.get_server(resource_server)  # or resource_server if specified
client = HttpClient(server.base_url)

# assemble_request():
req = assemble_request(
    method_spec, merged_params,
    base_url=server.base_url,
    prefix=server.prefix,
)
```

#### Phase 6: Auth Chain Multi-Server

**File: `runtime/auth_commands.py` → `add_auth_commands()`**

```python
def add_auth_commands(cli: click.Group, service: dict, servers: dict[str, ServerInfo]) -> None:
```

- `auth add` gets new `--server` option to pick which server definition
- Fix L73 bug: use `_base_url` instead of `base_url`
- Save `server_name` in profile fields

```python
@auth.command("add")
@click.option("-s", "--server", "server_name", help="Server name from _auth.yaml")
...
def auth_add(name, username, password, token, endpoint, set_default, set_vars, server_name):
    # Resolve server
    if server_name and server_name in servers:
        srv = servers[server_name]
    else:
        srv = next(iter(servers.values()))  # default
    
    _base_url = endpoint or srv.base_url
    client = HttpClient(_base_url)
    
    # Save with server_name
    save_profile(profile_name, {
        "token": token, 
        "endpoint": _base_url,
        "server_name": server_name or srv.name,
    }, ...)
```

#### Phase 7: Auth Step Server Selection

**File: `client/auth.py` → auth steps**

Auth steps in YAML can now have `server: serve1`. When processing auth steps:
- Each step that needs an HTTP client picks the correct server
- Currently the entire chain uses one `http_client` — need to handle per-step server switching

For simplicity, the first pass can keep using the default server for all auth steps. Multi-server auth (different servers for different auth steps) is a future enhancement.

**File: `cli/auth_cmd.py` → `auth_login()`**

Same treatment as `add_auth_commands()` — resolve server from the new `servers` list.

#### Phase 8: Resource YAML `server` Field

Resource YAMLs can already have any top-level key (YAML is flexible). Add `server: serve1` as an optional field:

```yaml
# repos.yaml
description: 仓库管理
server: serve1  # ← NEW: pick which server this resource uses
path: repos
methods: ...
```

The `build_resource_group()` in builder.py reads `resource_spec.get("server")` and passes it to the callbacks.

#### Phase 9: Credentials Enhancement

**File: `client/credentials.py`**

Profiles already work fine. Add `server_name` as an optional field to associate profiles with YAML-defined servers. No structural change needed — profiles remain flat.

### 4. Backward Compatibility Strategy

1. **Single server dict → auto-normalize**: `{"base_url": "...", "prefix": "..."}` becomes `[{"name": "default", "base_url": "...", "prefix": "..."}]`
2. **ServiceContext properties**: `.base_url` and `.prefix` remain as backward-compat properties returning the default server's values
3. **All existing tests pass without changes** — the normalized path produces identical behavior for single-server specs
4. **Existing YAML specs** (xiyu, ketacli-repos examples) continue to work unchanged

### 5. Implementation Order

1. `types.py` — update `ServerConfig`, `ServiceSpec`
2. `validator.py` — handle both dict and list
3. `loader.py` — normalize to list, produce `servers` key
4. `builder.py` — `ServiceContext` with `servers` dict, backward-compat properties
5. `runner.py` — build `server_map`, pass to `ServiceContext`
6. `builder.py` (callbacks) — resolve `server` from resource spec
7. `auth_commands.py` — multi-server `auth add`, fix L73 bug
8. `cli/auth_cmd.py` — multi-server `auth login`
9. Tests — add multi-server test cases, single-server backward compat tests
10. `gen.py` — update scaffold template (optional, backward compat handles it)

