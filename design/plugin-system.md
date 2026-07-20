# cliyard 插件机制设计

## 架构

```
plugins/
├── __init__.py       # PluginRegistry + 装饰器
└── discovery.py      # entry point + 目录扫描

扩展点:
  auth  → 自定义认证步骤 (如 plugin:sigv4)
  types → 自定义字段类型 (如 ip_address)
  hooks → 自定义 pre/post 处理
```

## 注册表

```python
# 3 个注册表
_auth_steps: dict[str, type]    # "sigv4" → SigV4Auth
_field_types: dict[str, type]   # "ip" → IPAddressType  
_hooks: dict[str, callable]     # "mask_email" → fn

# 装饰器
@register_auth_step("sigv4")
@register_field_type("ip")
@register_hook("mask_email")

# 发现
discover_plugins(spec_dir)  #  扫描 entry points + plugins/ 目录
```

## YAML

```yaml
plugins:
  auth:
    sigv4: my_plugins.auth.SigV4Auth
  types:
    ip: my_plugins.types.IPAddress
```

## 集成

- auth.py: `type == "plugin:sigv4"` → `PluginRegistry.get_auth_step("sigv4")`
- validate/types.py: 未知 type → 查 PluginRegistry
