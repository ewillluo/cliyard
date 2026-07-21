# cliyard

**CLI + YAML + Yard** — a framework that generates CLI commands from YAML specs. Define your REST API in a few YAML files, and cliyard produces a fully-structured Click CLI with parameters, types, response formatting, and auto-generated help.

## Installation

```bash
pip install cliyard

# Or for development
pip install -e .
```

## Quick Start

```bash
# Generate a CLI from spec files
cliyard gen --name mycli --defs-path ./specs/
cd mycli && pip install -e .

# Use it
mycli --help
mycli repos list --page-size 10
```

## How It Works

cliyard turns a directory of YAML files into CLI commands. One directory equals one API service. Each YAML file becomes a resource group with subcommands for every defined method.

```
specs/
├── _auth.yaml      # Service config: name, servers, auth chain
├── repos.yaml      # Resource: repos (list, create, get, update, delete)
├── users.yaml      # Resource: users (list, create, delete)
└── _groups.yaml    # (optional) Group definitions for nesting
```

**Data flow** for a single invocation:

```
CLI input → bind & validate → auth chain → assemble request → HTTP call → format response
```

## Features

- **YAML-driven**: Add a new API resource by creating a `.yaml` file, no code changes
- **Plugin system**: 6 extension points for auth, types, hooks, methods, commands, field resolvers
- **Multi-server**: Support multiple API endpoints in a single CLI
- **Rich output**: Tables, JSON, CSV formatting with datetime conversion
- **Resource grouping**: Nest related commands under parent groups

## Examples

See the [examples/](examples/) directory for ready-to-use spec sets:

- `examples/ketaops/` — KetaDB Operations API (40+ resources)
- `examples/ketacli-repos/` — Simple repository management API
- `examples/xiyu/` — xiyu platform API

## Documentation

Generated CLI projects include a `README.md` with full usage docs covering:

- Usage & environment management
- Adding new resources
- Plugin authoring (all 6 plugin types)
- Multi-server configuration
- Custom method plugins

## License

MIT
