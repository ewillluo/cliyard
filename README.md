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

## Web UI (cliyard serve)

`cliyard serve` 以 Web 方式启动 spec 目录：命令自动渲染为表单，执行过程以步骤流实时展示，并保留可重放的执行历史。

### 用法

```bash
cliyard serve ./specs
cliyard serve examples/demo --port 8080 --host 0.0.0.0
cliyard serve examples/demo --open --reload
```

### 选项

| 选项 | 默认值 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1` | 绑定地址 |
| `--port` | `8080` | 监听端口 |
| `--open` | 关闭 | 启动后自动打开浏览器 |
| `--reload` | 关闭 | uvicorn 自动重载（配合前端开发） |

### 前端构建

静态资源由 FastAPI 托管，首次使用前需构建前端：

```bash
cd webui && npm install && npm run build
```

未构建时访问 `/` 返回提示 JSON（而非 500）。开发模式可在 `webui/` 下运行 `npm run dev`（Vite 默认 `5173` 端口，已配置 CORS）。

### API 一览

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/spec` | 命令树 + flow 元数据（含 JSON Schema） |
| POST | `/api/execute` | 提交命令/流程执行，返回 `execution_id` |
| GET | `/api/executions/{id}/stream` | SSE 步骤流（validate→auth→…→done） |
| GET | `/api/executions/{id}` | 执行状态 + 全量步骤（轮询兜底） |
| GET | `/api/executions` | 历史列表（时间倒序、分页、kind 过滤） |
| POST | `/api/executions/{id}/replay` | 用历史参数重放执行 |
| DELETE | `/api/executions` | 清空历史 |
| GET | `/api/auth/profiles` | 凭据 profile 列表（token 掩码） |
| POST | `/api/auth/switch` | 切换当前 profile |

### 示例

```bash
# 启动 demo 服务
cliyard serve examples/demo --port 8080

# 提交一个命令执行
curl -X POST http://127.0.0.1:8080/api/execute \
  -H 'Content-Type: application/json' \
  -d '{"kind":"command","target":"user.list","params":{}}'
# => {"execution_id":"..."}

# 订阅步骤流（SSE）
curl -N http://127.0.0.1:8080/api/executions/<id>/stream

# 查看历史
curl http://127.0.0.1:8080/api/executions
```

## Examples

See the [examples/](examples/) directory for ready-to-use spec sets:

- `examples/demo/` — Pet Store API demo with resource commands, plugins, and flow orchestration

```
# Library mode (read YAML at runtime)
python3 -c "from cliyard.runtime import create_cli; create_cli('examples/demo')()"

# Flow orchestration
petstore flow list
petstore flow run add-user --name 张三
petstore flow run retry-demo
petstore flow run plugin-demo
petstore flow run hook-demo
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
