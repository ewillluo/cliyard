# cliyard Auth System Design

## 完整认证流程

```
                  ┌─────────────────────────┐
                  │  ~/.cliyard/credentials  │
                  │  .yaml                   │
                  └────────┬────────────────┘
                           │ 读取
                           ▼
用户运行命令 ──→ run_with_spec()
                   │
                   ├─ 检查 ~/.cliyard/credentials.yaml
                   │  ├─ 有有效 token → 跳过 auth chain，直接 inject
                   │  └─ 无/过期 → 运行 auth chain
                   │
                   ▼
             auth chain 执行
                   │
                   ├─ [env]    读取环境变量
                   ├─ [login]  HTTP 请求拿凭证
                   │             支持引用上一步结果
                   │             {{ auth_state.step_name.field }}
                   ├─ [inject] 注入到请求
                   │
                   ▼
             保存到 ~/.cliyard/credentials.yaml
```

## 1. Auth State 引用

当前 auth chain 各 step 的 config 模板渲染时只注入了 `env()` 函数。
需要在上下文中注入 `auth_state`，让后面的 step 能引用前面的结果。

```yaml
auth:
  steps:
    - name: login_step
      type: login
      config:
        endpoint: /api/v1/account/login
        method: POST
        body:
          username: '{{ env("KETA_USER") }}'
          password: '{{ env("KETA_PASS") }}'
      extract:
        csrf_token: $.X-Csrf-Token

    - name: create_token
      type: login
      config:
        endpoint: /api/v1/auth/tokens
        method: POST
        headers:
          X-Csrf-Token: '{{ auth_state.login_step.csrf_token }}'
        body:
          username: '{{ env("KETA_USER") }}'
      extract:
        token: $.token
        ttl: $.expires_in

    - name: inject
      type: inject
      config:
        into: header
        name: Authorization
        prefix: "Bearer "
```

实现方式：`run_auth_chain()` 中，渲染每个 step 的 config 时，
把 `auth_state`（累积的 state dict）注入到 Jinja2 模板上下文。

## 2. `cliyard auth login` 命令

```bash
cliyard auth login --spec-dir ./ketaops/        # 手动初始化认证
cliyard auth status                              # 查看凭证状态
cliyard auth logout                              # 清除凭证
```

执行流程：
1. 加载 _service.yaml 中的 auth 配置
2. 执行 auth chain（env → login → inject）
3. 根据 auth.persist 配置保存凭证

## 3. 凭证存储

`~/.cliyard/credentials.yaml`:
```yaml
services:
  ketaops:
    token: eyJhbGciOiJIUzUxMiIs...
    expires_at: 1700000000000
  github:
    token: ghp_xxx
    expires_at: 1700000000000
```

自动读取：
1. `run_with_spec()` 加载 service 时，检查 `~/.cliyard/credentials.yaml`
2. 如果找到该 service 的有效 token（未过期），跳过 auth chain 的 env/login step
3. 只执行 inject step（从缓存取 token 注入）

## 4. YAML Persist 配置

```yaml
auth:
  id: ketaops                     # 标识，用于 credentials.yaml 的 key
  steps:
    - name: get_token
      type: login
      config:
        endpoint: /api/v1/auth/tokens
      extract:
        token: $.token
        ttl: $.expires_in

    - name: inject
      type: inject
      config:
        into: header
        name: Authorization
        prefix: "Bearer "

  persist:
    to: cliyard-config            # 保存到 cliyard 配置文件
    fields:
      token:
        from: get_token.token     # step_name.field_name
      expires_at:
        from: get_token.ttl       # 可选：从响应提取的 TTL
        default: 3600             # 可选：默认 TTL（秒）
```

## 5. 实现步骤

1. **Auth state 引用**：修改 `auth.py`，在渲染 step config 时注入 `auth_state`
2. **`cliyard auth login` 命令**：创建 `src/cliyard/cli/auth.py`
3. **凭证存储**：创建 `src/cliyard/client/credentials.py`（读写 ~/.cliyard/credentials.yaml）
4. **自动读取**：修改 `runner.py`，在 `run_with_spec()` 中自动检查凭证缓存
5. **YAML persist schema**：更新 `types.py` 中的 AuthChain 定义
