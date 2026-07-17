# cliyard AGENTS.md

## Project overview

cliyard = YAML → CLI generator + runtime library. Users define REST APIs in YAML specs, then either generate a standalone CLI or use `create_cli()` at runtime.

Two usage modes:
- **Library mode**: `create_cli("./specs/")` → returns `click.Group` — dynamic, no gen step
- **Gen mode**: `cliyard gen --name mycli --defs-path ./specs/` → generates pip-installable package

## Key commands

```bash
# dev install
source venv/bin/activate && pip install -e .

# test
pytest tests/ -v                     # all tests
pytest tests/test_integration.py -v  # integration only

# generate a CLI from specs
cliyard gen --name mycli --defs-path ./examples/ketaops/

# regenerate (re-reads specs/ from output dir)
cliyard gen --name mycli

# library mode (import in your code)
python3 -c "from cliyard.runtime import create_cli; cli = create_cli('examples/ketaops'); cli()"
```

## Architecture

```
src/cliyard/
├── cli/              # cliyard CLI itself (gen, init, run)
│   ├── __main__.py   # entry point: cliyard --version, gen, etc.
│   └── gen.py        # scaffold generator for standalone CLIs
├── client/           # HTTP + auth
│   ├── http.py       # HttpClient + standalone request()
│   ├── auth.py       # auth chain engine (env → login → inject → plugin)
│   └── credentials.py # profile-based ~/.cliyard/credentials.yaml
├── engine/           # core pipeline
│   ├── loader.py     # YAML spec loading + discovery
│   ├── builder.py    # Click command builder (dynamic)
│   ├── assembler.py  # Request dataclass + multipart/JSON assembly
│   ├── binder.py     # CLI kwargs → validated params
│   ├── template.py   # Jinja2 sandbox
│   ├── errors.py     # CliyError hierarchy
│   ├── error_handler.py
│   └── hooks.py      # pre/post request hook runner
├── output/           # response formatting
│   ├── formatter.py  # table / json / csv
│   └── handler.py    # JSONPath response parsing
├── plugin/           # plugin system
│   ├── __init__.py   # PluginRegistry + @register_* decorators
│   └── discovery.py  # entry points + directory scanning
├── runtime/          # high-level API
│   ├── runner.py     # create_cli() + run_with_spec()
│   └── auth_commands.py  # auth add/status/switch/logout CLI commands
├── schema/           # YAML type definitions
│   ├── types.py      # TypedDict specs
│   └── validator.py  # YAML schema validation
└── validate/         # field type validators + dependencies
    ├── types.py      # string/int/float/bool/enum/file
    └── dependency.py # depends_on.eq
```

## Key design decisions

- **Commands are dynamic**: `create_cli()` reads YAML at runtime via `builder.py`. No codegen needed for daily use.
- **YAML is the truth**: spec files define resources, methods, params, output. `gen` creates a thin wrapper that calls `create_cli()`.
- **Auth chain**: multi-step sequential pipeline (env → login → inject). Steps reference each other via `auth_state.step_name.field`.
- **Plugin system**: 3 extension points (`auth`, `types`, `hooks`). Registration via decorator or YAML `plugins:` section. Discovery scans `{spec_dir}/plugins/` and `{spec_dir.parent}/plugins/`.
- **Profile-based credentials**: `~/.cliyard/credentials.yaml` stores named profiles with `endpoint` + `token`. `auth add -n <name>` creates profiles.

## YAML spec conventions

```yaml
# _service.yaml — service config
name: myapi
server:
  base_url: http://localhost:8080
  prefix: /api/v1
auth:
  steps:
    - name: login
      type: login
      config:
        endpoint: /auth/login
        method: POST
        body:
          username: '{{ env("USER") }}'
      extract:
        token: $.token
    - name: inject
      type: inject
      config:
        source: login
        into: header
        name: Authorization
        prefix: "Bearer "
  persist:
    to: cliyard-config
    fields:
      token:
        from: login
```

```yaml
# repos.yaml — resource definition
description: 仓库管理
path: repos
methods:
  list:
    http:
      method: GET
    params:
      query:
        - name: pageNo
          field: pageNo
          type: int
          default: 1
    output:
      items_path: $.repos
      fields:
        - name: name
          alias: 仓库名称
  create:
    http:
      method: POST
      path: repos/{{ name }}
    params:
      body:
        - name: name
          type: string
          required: true
    request_body:
      name: '{{ name }}'
      type: '{{ repo_type | default("EVENTS") }}'
```

## Param field mapping

| YAML `name` | CLI option | API param (via `field`) |
|-------------|-----------|------------------------|
| `with_doc_size` | `--with-doc-size` | `withDocSize` |
| `pageNo` | `--page-no` | `pageNo` |
| `asset_id` | `--asset-id` | `assetId` |

## Plugin authoring

```python
from cliyard.plugin import register_auth_step, register_hook

@register_auth_step("my_login")
class MyLogin:
    def execute(self, auth_state, config, http_client):
        token = http_client.request(...)
        auth_state["token"] = token
        http_client.default_headers["Authorization"] = f"Bearer {token}"
        return token

@register_hook("my_hook")
def my_hook(req):
    req.query_params["extra"] = "value"
    return req
```

## Testing

```bash
pytest tests/ -v                          # 123 tests
pytest tests/test_integration.py -v       # E2E pipeline tests
pytest tests/test_auth.py -v              # auth chain tests
pytest tests/test_validate_types.py -v    # field validation tests
```

Tests use httpbin.org for HTTP integration. Auth tests mock HTTP calls. Fixtures in `tests/fixtures/`.

## Constraints & gotchas

- No `setup.py` (single source: `pyproject.toml`)
- Jinja2 `SandboxedEnvironment` — no `__builtins__`, no `eval()`, no file access in templates
- `type: enum` requires `choices:` field
- `type: file` generates `--file PATH` (Click path validator)
- `type: bool` generates `is_flag=True` (no `--flag value`, just `--flag` / `--no-flag`)
- `multiple: true` allows `--tag a --tag b` → tuple
- `field:` maps CLI name to API param name (camelCase → kebab-case auto for CLI)
- `request_body:` template takes precedence over auto-assembled `params.body`
- `body_type: multipart` sends form fields as query params + file as `files=` (ketacli pattern)
