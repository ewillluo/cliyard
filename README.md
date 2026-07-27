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
├── _auth.yaml              # Service config: name, servers, auth chain
├── _groups.yaml            # (optional) Group definitions for nesting
├── _flows.yaml             # (optional) Flow orchestration index
├── resources/              # Resource YAML files
│   ├── repos.yaml
│   └── ...
├── flows/                  # (optional) Flow step definitions
│   ├── _flow_create_repo.yaml
│   └── ...
└── plugins/                # Python plugins
    └── *.py
```

**Data flow** for a single invocation:

```
CLI input → bind & validate → auth chain → assemble request → HTTP call → format response
```

## Features

- **YAML-driven**: Add a new API resource by creating a `.yaml` file, no code changes
- **Plugin system**: 7 extension points for auth, types, hooks, methods, commands, field resolvers, flow steps
- **Flow orchestration**: Define multi-step workflows with conditional branching, loops, and lifecycle hooks
- **Multi-server**: Support multiple API endpoints in a single CLI
- **Rich output**: Tables, JSON, CSV formatting with datetime conversion
- **Resource grouping**: Nest related commands under parent groups

## Examples

See the [examples/](examples/) directory for ready-to-use spec sets:

- `examples/demo/` — Pet Store API demo with resource commands, plugins, and flow orchestration

```
# Library mode (read YAML at runtime)
python3 -c "from cliyard.runtime import create_cli; create_cli('examples/demo')()"

# Flow orchestration
petstore flow-run add-user --name 张三
petstore flow-run retry-demo
petstore flow-run plugin-demo
petstore flow-run hook-demo
```

## Documentation

Generated CLI projects include a `README.md` with full usage docs covering:

- Usage & environment management
- Adding new resources
- Plugin authoring (all 7 plugin types)
- Flow orchestration with conditional branching, loops, and hooks
- Multi-server configuration
- Custom method plugins

## License

MIT
