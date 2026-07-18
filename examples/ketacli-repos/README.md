# ketacli-repos: KetaDB 仓库管理示例

cliyard 示例 spec，通过 YAML 定义 KetaDB repos 资源的 CLI 命令。

## 结构

```
examples/ketacli-repos/
├── _service.yaml    # 服务配置（API地址、认证）
└── repos.yaml       # 仓库资源（list, create, get, update, delete）
```

## 快速开始

```bash
# 设置认证令牌
export KETA_SERVICE_TOKEN="your-token-here"

# 列出仓库
cliyard --spec-dir examples/ketacli-repos/ repos list

# 带参数列出
cliyard --spec-dir examples/ketacli-repos/ repos list --page 2 --per-page 10

# 创建仓库
cliyard --spec-dir examples/ketacli-repos/ repos create \
  --name my-repo \
  --repo-type EVENTS

# 获取仓库详情
cliyard --spec-dir examples/ketacli-repos/ repos get my-repo

# 更新仓库
cliyard --spec-dir examples/ketacli-repos/ repos update my-repo --description "更新描述"

# 删除仓库
cliyard --spec-dir examples/ketacli-repos/ repos delete --names "repo1,repo2"
```

## 认证方式

使用两步认证链：

1. `env` 步骤：从环境变量 `KETA_SERVICE_TOKEN` 读取令牌
2. `inject` 步骤：将令牌注入到 HTTP 请求头 `Authorization: Bearer <token>`

## 对照 ketacli

此 spec 将 ketacli 的 `repos.yaml` 结构映射为 cliyard 格式：

| ketacli 字段 | cliyard 字段 |
|-------------|-------------|
| `template_fields` | `params.body` |
| `data` 模板 | `request_body.template` |
| `default_fields` | `output.fields` |
| `api_prefix` | `server.prefix` |
