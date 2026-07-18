# cliyard Examples

This directory contains example API specs that demonstrate the cliyard directory-as-service format.

## Available Examples

| Example | Description |
|---------|-------------|
| [ketacli-repos/](ketacli-repos/) | KetaDB repository management (list, create, get, update, delete) |

## Creating Your Own API Spec

Follow these steps to define a new API service for cliyard.

### Step 1: Create a directory

Each API service lives in its own directory:

```bash
mkdir my-api
```

### Step 2: Write `_service.yaml`

Every service directory must contain a `_service.yaml` file with the service name and server URL:

```yaml
# my-api/_service.yaml
name: my-api
version: "1.0"
description: My API service
server:
  base_url: https://api.example.com
```

If your API requires authentication, add an auth chain:

```yaml
auth:
  steps:
    - name: token
      type: env
      config:
        name: MY_API_TOKEN
    - name: inject
      type: inject
      config:
        into: header
        name: Authorization
        prefix: "Bearer "
```

Auth step types:
- `env` — read credentials from an environment variable
- `login` — send an HTTP request to obtain a token
- `inject` — attach the token to subsequent requests

### Step 3: Write resource YAML files

Each resource gets its own file. The filename (without `.yaml`) becomes the resource name used in CLI commands:

```yaml
# my-api/users.yaml
description: User management
path: users
methods:
  list:
    http:
      method: GET
    params:
      query:
        - name: page
          type: int
          default: 1
          description: Page number
        - name: status
          type: enum
          choices: [active, inactive, all]
          default: active
    output:
      items_path: $.users
      fields:
        - name: id
          alias: ID
        - name: email
          alias: Email

  create:
    http:
      method: POST
    params:
      body:
        - name: email
          type: string
          required: true
          description: User email
        - name: role
          type: enum
          choices: [admin, user]
          default: user
```

### Step 4: Run the CLI

```bash
cliyard --spec-dir my-api/ users list --help
cliyard --spec-dir my-api/ users list --page 1 --status active
```

## Directory Structure

```
my-api/
├── _service.yaml      # Required: service config (name, server, auth)
├── resource-a.yaml    # One YAML file per API resource
├── resource-b.yaml
└── ...
```

- `_service.yaml` — defines server connection, authentication, and global settings. This file is required.
- `*.yaml` — each other YAML file represents one API resource. The filename minus `.yaml` (e.g. `users` from `users.yaml`) becomes the CLI resource group name.
- Files named `_service.*.yaml` (e.g. `_service.local.yaml`) are reserved for future local overrides and are skipped during loading.

## YAML Field Reference

### `_service.yaml` fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Service identifier |
| `version` | string | no | Semver version string |
| `description` | string | no | Human-readable description |
| `server.base_url` | string | yes | Base URL of the API |
| `server.prefix` | string | no | URL prefix (e.g. `/api/v1`) |
| `server.timeout` | int | no | Request timeout in seconds (default: 30) |
| `auth.steps` | list | no | Ordered authentication steps |

### Auth step fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Step identifier (used to reference results) |
| `type` | string | yes | `env`, `login`, or `inject` |
| `config` | mapping | yes | Type-specific configuration |

**`env` step config:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Environment variable name |

**`login` step config:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `endpoint` | string | yes | Login API endpoint (e.g. `/auth/token`) |
| `method` | string | no | HTTP method (default: POST) |
| `body` | mapping | no | Request body payload |
| `extract.token` | string | yes | JSONPath to the token field (e.g. `$.data.token`) |
| `extract.ttl` | int | no | Token TTL in seconds for caching |

**`inject` step config:**

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `into` | string | yes | Injection target: `header` (query planned) |
| `name` | string | yes | Header name (e.g. `Authorization`) |
| `prefix` | string | no | Value prefix (e.g. `Bearer `) |

### Resource file top-level fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `description` | string | no | Resource description (shown in CLI help) |
| `path` | string | no | URL path segment for this resource |
| `methods` | mapping | yes | Method name to method spec mapping |

### Method fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `http.method` | string | yes | HTTP method: `GET`, `POST`, `PUT`, `DELETE` |
| `http.path` | string | no | URL path override (supports `{{ var }}` placeholders) |
| `params` | mapping | no | Parameter groups by location |
| `output` | mapping | no | Response output configuration |
| `request_body` | mapping | no | Request body template (future) |

### Parameters (`params`)

Parameters are organized by location:

```yaml
params:
  path:    # URL path segments (e.g. /users/{id})
  query:   # Query string parameters (e.g. ?page=1)
  body:    # Request body fields
  header:  # Custom HTTP headers (future)
```

Each parameter supports these fields:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Parameter name |
| `type` | string | no | `string`, `int`, `float`, `bool`, or `enum` (default: `string`) |
| `required` | bool | no | Whether the parameter is required |
| `default` | any | no | Default value |
| `description` | string | no | Help text shown in CLI |
| `choices` | list | yes* | Allowed values (required for `enum` type) |
| `depends_on` | mapping | no | Conditional required field (see below) |

**String constraints:**

| Field | Type | Description |
|-------|------|-------------|
| `min_length` | int | Minimum string length |
| `max_length` | int | Maximum string length |
| `pattern` | string | Regex pattern to match |

**Numeric constraints (int, float):**

| Field | Type | Description |
|-------|------|-------------|
| `min` | int/float | Minimum value (inclusive) |
| `max` | int/float | Maximum value (inclusive) |

**Conditional required fields (`depends_on`):**

```yaml
- name: db_password
  type: string
  required: true
  depends_on:
    field: auth_type
    eq: password
```

When `auth_type` equals `password`, `db_password` becomes required.

### Output (`output`)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `items_path` | string | no | JSONPath to the list of items in the response |
| `total_path` | string | no | JSONPath to total count (for pagination) |
| `fields` | list | no | List of field definitions for display |

Each field in the `fields` list:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | yes | Field name in the API response |
| `alias` | string | no | Display alias (shown as column header) |
