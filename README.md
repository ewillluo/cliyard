# cliyard

**CLI + YAML + Yard** — a framework that generates CLI commands from YAML specs. Define your REST API in a few YAML files, and cliyard produces a fully-structured Click CLI with parameters, types, and auto-generated help. Originally inspired by [ketacli](https://gitee.com/xishuhq/ketacli)'s YAML-driven architecture, now generalized for any REST API.

## Installation

```bash
pip install cliyard
```

For local development:

```bash
pip install -e .
```

## Quick Start

```bash
# Explore the example spec
cliyard --spec-dir examples/ketacli-repos/ repos list --help

# Usage: repos list [OPTIONS]
#   --page INTEGER        Page number
#   --search TEXT         Search keyword
#   --help                Show this message and exit.
```

## How It Works

cliyard turns a directory of YAML files into CLI commands. One directory equals one API service. Each YAML file (except `_service.yaml`) becomes a resource group with subcommands for every defined method.

```
your-api/                          ┌─────────────────────────────────┐
├── _service.yaml  ── service ──►  │  cliyard Engine                 │
├── repos.yaml     ── resource ──► │                                 │
├── users.yaml     ── resource ──► │  Loader ──► Builder ──► Click   │
└── ...                            │    │            │           │    │
                                   │    │     Auth Chain          │    │
                                   │    ▼            ▼           ▼    │
                                   │  YAML       Commands    CLI run  │
                                   │  parsing    + params              │
                                   └─────────────────────────────────┘
```

**Data flow** for a single invocation:

```
cliyard --spec-dir examples/ketacli-repos/ repos list --page 1

    1. Loader reads _service.yaml + repos.yaml
    2. Auth chain runs (env → login → inject token)
    3. Builder generates Click commands from method specs
    4. Params are typed (int, string, enum, bool) and validated
    5. (Future) HTTP request is assembled and sent
    6. (Future) Response is formatted with Rich tables
```

## Directory Structure

Each service is a directory containing a `_service.yaml` for service-level config and one YAML file per resource:

```
ketacli-repos/
├── _service.yaml      # Service config: name, server, auth
└── repos.yaml         # Resource: repos (list, create, get, update, delete)
```

- `_service.yaml` defines the server URL, authentication chain, and global settings.
- Resource files (`repos.yaml`, `users.yaml`, etc.) define the methods, parameters, and output format for each API resource.
- Files prefixed with `_service.` (like `_service.local.yaml`) are reserved for future local overrides and are ignored during loading.

## Comparison with ketacli

| Feature | cliyard | ketacli |
|---------|---------|---------|
| API scope | Any REST API | KetaDB only |
| Config format | One directory per API service | Single YAML tree per resource |
| Auth model | Chain-based (env, login, inject) | Built-in, KetaDB-specific |
| Auth caching | In-memory TTL token cache | Session-based |
| Param types | string, int, float, bool, enum | Pre-defined per command |
| Adding resources | Add a YAML file to the directory | Requires code changes |
| CLI generation | Dynamic from spec at runtime | Pre-built Click commands |
| Purpose | General-purpose API-to-CLI framework | KetaDB management tool |

## Creating Your Own Spec

See [examples/README.md](examples/README.md) for a step-by-step guide to creating new API specs.

## License

MIT
