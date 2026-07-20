
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
