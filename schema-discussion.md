# cliyard Schema 设计讨论 (v2)

## 一、目录即服务

一个 API 服务 = 一个目录。目录下有 n 个 YAML 文件，分工明确：

```
my-service/                        # ← 一个目录 = 一个 API 服务
├── _service.yaml                  #   服务级配置（server, auth, global hooks, plugins）
├── _service.local.yaml            #   .gitignore 掉，放个人 token/key 等敏感信息
├── users.yaml                     #   资源定义
├── posts.yaml
├── comments.yaml
└── plugins/                       #   自定义插件
    └── my_custom_auth.py
```

### _service.yaml

```yaml
name: My Cloud API
version: 1.0
description: 我的云服务 API

server:
  base_url: https://api.mycloud.com
  prefix: /api/v2
  timeout: 30
  retry:
    max_attempts: 3
    delay: 1

# 认证步骤链
auth:
  steps:
    - name: login
      type: login
      endpoint: /auth/token
      method: POST
      body:
        app_key: '{{ env("APP_KEY") }}'
        app_secret: '{{ env("APP_SECRET") }}'
      extract:
        token: $.data.access_token
        ttl: $.data.expires_in
    - name: inject
      type: inject
      into: header
      name: Authorization
      prefix: "Bearer "

# 全局 hook
hooks:
  pre:
    - name: rate_limit
      fn: builtins.rate_limit
      args:
        max_rps: 10
  post:
    - name: unwrap
      fn: builtins.unwrap
      args:
        path: $.data

# 插件注册
plugins:
  auth:
    sigv4: my_plugins.auth.SigV4Auth
  hooks:
    my_filter: my_plugins.hooks.MyFilter
```

### _service.local.yaml

```yaml
# 本地覆盖，不提交到 git
server:
  base_url: http://localhost:8080

auth:
  steps:
    - name: login
      body:
        app_key: my-dev-key
        app_secret: my-dev-secret
```

### users.yaml（资源定义）

```yaml
# 文件名 users = 资源名
description: 用户管理
path: users

# 可覆盖 _service.yaml 的 auth/hooks
# auth: ...
# hooks: ...

methods:
  list:
    http:
      method: GET
    params:
      query:
        - name: page
          type: int
          default: 1
          min: 1
        - name: per_page
          type: int
          default: 20
          max: 100
    output:
      items_path: $
      fields:
        - name: id
          alias: ID
        - name: email
          alias: 邮箱

  create:
    http:
      method: POST
    params:
      body:
        email:
          type: string
          required: true
          pattern: '^[\w.+-]+@[\w-]+\.[\w.]+$'
          message: 请输入有效邮箱
        role:
          type: enum
          choices: [admin, user, viewer]
          default: user
        tags:
          type: array
          item_type: string
          max_items: 10
    request_body:
      template:
        email: '{{ email }}'
        role: '{{ role | default("user") }}'
        tags: '{{ tags | default([]) }}'
```

### 与单文件方案对比

| 维度 | 单文件方案 | 目录方案 |
|------|-----------|---------|
| 组织 | 一个文件几百行 | 每个资源一个文件 |
| 复用 | 整文件复制 | 只复制 resources/ 目录 |
| 多人协作 | 一个文件改冲突 | 各改各的资源文件 |
| 本地开发 | 改全局配置 | `_service.local.yaml` 不提交 |
| 插件 | 混在 YAML 里 | plugins/ 目录管理 |

---

## 二、认证: 可注册的 Hook 链

### 认证的本质

```
[获取凭证]  →  [注入请求]
   │               │
   │               ├─ header: Authorization: Bearer xxx
   │               ├─ header: X-API-Key: xxx
   │               ├─ query:  ?access_token=xxx
   │               ├─ cookie: sessionid=xxx
   │               └─ body:   {"token": "xxx"}
   │
   ├─ env: 从环境变量读取
   ├─ file: 从文件读取
   ├─ prompt: 交互式输入
   ├─ login: HTTP 请求换取凭证
   └─ plugin:xxx: 自定义逻辑
```

### 内置 Auth Step 类型

| Step 类型 | 用途 | 关键配置 |
|-----------|------|---------|
| `login` | HTTP 请求换取 token | endpoint, method, body, extract |
| `env` | 从环境变量读取 | name (环境变量名) |
| `file` | 从文件读取 | path |
| `prompt` | 交互式输入 | message, secret (是否隐藏) |
| `inject` | 注入到请求 | into (header/query/cookie), name, prefix, value |
| `sign` | 请求签名 | 算法、密钥（插件化，如 SigV4） |

### 认证链示例

```yaml
# 场景 1: GitHub — 读环境变量 → 注入 header
auth:
  steps:
    - name: load
      type: env
      name: GITHUB_TOKEN
    - name: inject
      type: inject
      into: header
      name: Authorization
      prefix: "Bearer "

# 场景 2: 飞书 — login 拿 token → 注入 header
auth:
  steps:
    - name: get_token
      type: login
      endpoint: /open-apis/auth/v3/tenant_access_token/internal
      method: POST
      body:
        app_id: '{{ env("FEISHU_APP_ID") }}'
        app_secret: '{{ env("FEISHU_APP_SECRET") }}'
      extract:
        token: $.tenant_access_token
        ttl: $.expire
    - name: inject
      type: inject
      into: header
      name: Authorization
      prefix: "Bearer "

# 场景 3: 企业微信 — login 拿 token → 注入 query
auth:
  steps:
    - name: get_token
      type: login
      endpoint: /cgi-bin/gettoken
      method: GET
      query:
        corpid: '{{ env("WX_CORP_ID") }}'
        corpsecret: '{{ env("WX_CORP_SECRET") }}'
      extract:
        token: $.access_token
    - name: inject
      type: inject
      into: query
      name: access_token

# 场景 4: AWS SigV4 — 自定义插件
auth:
  steps:
    - name: sign
      type: plugin:sigv4           # 通过 plugins 注册
      config:
        service: ec2
        region: us-east-1
        access_key: '{{ env("AWS_ACCESS_KEY_ID") }}'
        secret_key: '{{ env("AWS_SECRET_ACCESS_KEY") }}'

# 场景 5: 交互式登录 + Cookie
auth:
  steps:
    - name: credentials
      type: prompt
      fields:
        - name: username
          message: 用户名
        - name: password
          message: 密码
          secret: true
    - name: login
      type: login
      endpoint: /login
      method: POST
      body:
        username: '{{ credentials.username }}'
        password: '{{ credentials.password }}'
      extract:
        session: $.session_id
    - name: inject
      type: inject
      into: cookie
```

### 自定义 Auth Step 注册

```yaml
# _service.yaml
plugins:
  auth:
    sigv4: my_plugins.auth.SigV4Auth
```

```python
# plugins/my_auth.py
from cliyard.plugin import AuthStep

class SigV4Auth(AuthStep):
    """AWS SigV4 请求签名"""

    def execute(self, ctx, config):
        # ctx: {auth_state, request}
        # config: 来自 YAML 的 plugin config

        access_key = config['access_key']
        secret_key = config['secret_key']
        service = config['service']
        region = config['region']

        # 对当前请求计算签名
        signature = self._sign_request(
            ctx.request, access_key, secret_key, service, region
        )

        # 注入签名到请求头
        ctx.request.headers['Authorization'] = signature
        ctx.request.headers['X-Amz-Date'] = self._get_date()

        return ctx
```

---

## 三、字段类型系统与校验

### 完整类型表

| 类型 | CLI 表示 | 校验属性 |
|------|---------|---------|
| `string` | `--name TEXT` | `pattern`, `min_length`, `max_length` |
| `int` | `--name INTEGER` | `min`, `max` |
| `float` | `--name FLOAT` | `min`, `max` |
| `bool` | `--name / --no-name` | 无 |
| `enum` | `--name [choices]` | `choices` (必填) |
| `array` | `--name ITEM` (multiple) | `item_type`, `min_items`, `max_items` |
| `dict` | `--name JSON` | `keys` (子 schema) |
| `secret` | `--name TEXT` (不回显) | 同 string |
| `file` | `--name PATH` | `exists`, `max_size`, `extensions` |
| `date` | `--name TEXT` | `format` (如 YYYY-MM-DD) |
| `datetime` | `--name TEXT` | `format` (如 ISO8601) |

### YAML 定义示例

```yaml
params:
  path:
    - name: project_id
      type: string
      pattern: '^[A-Z]{2}-\d+$'
      message: 项目 ID 格式错误，示例: PRJ-123

  body:
    - name: email
      type: string
      required: true
      pattern: '^[\w.+-]+@[\w-]+\.[\w.]+$'
      message: 请输入有效的邮箱地址

    - name: role
      type: enum
      choices: [admin, user, viewer]
      default: user

    - name: tags
      type: array
      item_type: string
      min_items: 1
      max_items: 10
      unique: true

    - name: metadata
      type: dict
      keys:
        source:
          type: string
        version:
          type: int
          min: 1

    - name: avatar
      type: file
      extensions: [.jpg, .png, .gif]
      max_size: 5MB

    - name: deploy_time
      type: datetime
      format: ISO8601

    - name: api_key
      type: secret
      required: true
```

### 校验触发流程

```
用户输入 → CLI 参数解析
              ↓
         类型转换 (str → int/float/bool)
              ↓
         格式校验 (pattern, min, max, choices...)
              ↓  ← 失败则报错，提示用户
         依赖校验 (depends_on 条件)
              ↓  ← 失败则提示具体字段条件
         提交给 HTTP 层
```

---

## 四、字段依赖策略

### 场景

```
部署策略:
  - rolling_update: 需要 max_surge, max_unavailable
  - recreate:       不需要额外参数
  - blue_green:     需要 pre_approval, traffic_ratio
```

### 方式 A: `depends_on`（条件必填/条件可见）

```yaml
params:
  body:
    - name: deploy_strategy
      type: enum
      choices: [rolling_update, recreate, blue_green]
      required: true

    - name: max_surge
      type: int
      description: 滚动更新最大额外副本数
      required: true
      depends_on:
        field: deploy_strategy
        eq: rolling_update

    - name: max_unavailable
      type: int
      description: 滚动更新最大不可用数
      default: 0
      depends_on:
        field: deploy_strategy
        eq: rolling_update

    - name: pre_approval
      type: bool
      description: 是否需要预审批
      depends_on:
        field: deploy_strategy
        in: [blue_green, recreate]

    - name: traffic_ratio
      type: int
      description: 蓝绿部署流量比例 (%)
      min: 0
      max: 100
      depends_on:
        field: deploy_strategy
        eq: blue_green
```

### 方式 B: 跨字段校验规则

```yaml
params:
  body:
    - name: start_port
      type: int
      default: 8000

    - name: end_port
      type: int
      default: 9000
      validate:
        - rule: gt
          field: start_port
          message: "end_port 必须大于 start_port"

    - name: cpu_limit
      type: int

    - name: memory_limit
      type: int
      validate:
        - rule: required_if
          field: cpu_limit
          present: true
          message: "设置了 CPU 限制时必须同时设置内存限制"
```

### 支持的校验规则

| 规则 | 含义 | 适用 |
|------|------|------|
| `eq` | 等于某值 | depends_on |
| `in` | 属于某集合 | depends_on |
| `gt` | 大于某字段值 | validate |
| `gte` | 大于等于 | validate |
| `lt` | 小于 | validate |
| `lte` | 小于等于 | validate |
| `required_if` | 另一字段满足条件时必填 | validate |
| `required_if_not` | 另一字段不满足条件时必填 | validate |
| `mutually_exclusive` | 与另一字段互斥 | validate |

---

## 五、完整的扩展点体系

### 四种可注册的扩展

| 扩展点 | 用途 | 注册方式 |
|--------|------|---------|
| `auth` | 自定义认证步骤 | `plugins.auth.my_step: MyModule.MyClass` |
| `hooks` | 自定义 pre/post hook | `plugins.hooks.my_hook: MyModule.MyHook` |
| `types` | 自定义字段类型 | `plugins.types.my_type: MyModule.MyType` |
| `convert` | 自定义值转换器 | `plugins.convert.my_fn: MyModule.MyFunc` |

### 插件搜索路径

```
1. 服务目录下的 plugins/ 子目录
2. pip install 的 Python 包 (entry point)
3. ~/.cliyard/plugins/ 全局目录
```

---

## 六、完整数据流回顾

```
CLI 输入
  │
  ▼
目录加载器
  ├─ 读取 _service.yaml → server, auth, hooks, plugins
  ├─ 读取 *.yaml → resource 定义
  └─ 注册 plugins → auth steps, hooks, types
  │
  ▼
Click 动态生成
  ├─ 根据 methods 生成子命令
  ├─ 根据 params 生成 CLI 选项（含类型校验）
  └─ 根据 depends_on 生成条件依赖
  │
  ▼
回调执行
  ├─ 1. CLI 参数校验（类型 + 格式 + 依赖）
  ├─ 2. Pre-hooks（含 auth 步骤链）
  │     ├─ env: 读环境变量
  │     ├─ login: 发请求拿 token
  │     ├─ inject: 注入凭据
  │     └─ user hooks: 限流/日志等
  ├─ 3. 请求组装
  │     ├─ path 模板渲染
  │     ├─ query 参数拼接
  │     ├─ header/cookie 注入
  │     └─ body 模板渲染
  ├─ 4. HTTP 请求
  ├─ 5. Post-hooks
  │     ├─ unwrap: 解响应包
  │     ├─ error handler
  │     └─ user hooks
  └─ 6. 输出渲染
        ├─ JSONPath 定位数据
        ├─ 字段转换器
        └─ Rich 表格输出
```
