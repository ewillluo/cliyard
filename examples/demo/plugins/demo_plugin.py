"""Demo plugins — 演示 cliyard 的 6 种插件类型。"""

import json
import time

import click
from rich.console import Console

from cliyard.plugin import (
    register_auth_step,
    register_field_type,
    register_hook,
    register_method,
    register_command,
    register_field_resolver,
)

console = Console()

# ---------------------------------------------------------------------------
# 1. @register_auth_step — 自定义认证步骤
# ---------------------------------------------------------------------------

@register_auth_step("demo_auth")
class DemoAuth:
    """演示认证步骤：直接从环境变量读取 token。"""

    def execute(self, auth_state, config, http_client):
        import os
        token = os.environ.get("DEMO_TOKEN", config.get("default_token", "demo-token"))
        http_client.default_headers["Authorization"] = f"Bearer {token}"
        auth_state["token"] = token
        return token


# ---------------------------------------------------------------------------
# 2. @register_field_type — 自定义字段类型验证
# ---------------------------------------------------------------------------

@register_field_type("phone")
class PhoneField:
    """演示自定义字段类型：手机号格式验证。"""

    @staticmethod
    def validate(value):
        import re
        if not re.match(r"^1[3-9]\d{9}$", str(value)):
            raise ValueError(f"无效的手机号: {value}")
        return str(value)


# ---------------------------------------------------------------------------
# 3. @register_hook — 请求前后钩子
# ---------------------------------------------------------------------------

@register_hook("add_timestamp")
def add_timestamp(req):
    """演示请求前钩子：在 query 中添加时间戳。"""
    req.query_params["_t"] = str(int(time.time() * 1000))
    return req


@register_hook("pretty_print")
def pretty_print_response(resp):
    """演示响应后钩子：格式化打印响应。"""
    import json as _json
    try:
        data = resp.json()
        console.print(_json.dumps(data, indent=2, ensure_ascii=False))
    except Exception:
        console.print(resp.text[:500])
    return resp


# ---------------------------------------------------------------------------
# 4. @register_method — 多步骤业务方法
# ---------------------------------------------------------------------------

@register_method("place_and_pay")
def place_and_pay(params, http_client, config):
    """演示业务方法：两步完成下单+支付。

    用法 YAML:
      methods:
        quick_buy:
          type: plugin:place_and_pay
          config:
            payment_method: credit_card
          params:
            body:
              - name: pet_id
                type: string
                required: true
    """
    # Step 1: 下单
    order_data = {
        "petId": params.get("pet_id"),
        "quantity": params.get("quantity", 1),
        "status": "placed",
    }
    order_resp = http_client.request("POST", "/api/v1/store/orders", data=order_data)
    order = order_resp.json()
    order_id = order.get("id")

    # Step 2: 支付
    payment = config.get("payment_method", "credit_card")
    pay_resp = http_client.request(
        "PUT", f"/api/v1/store/orders/{order_id}/pay",
        data={"method": payment},
    )

    return {"order": order, "payment": pay_resp.json()}


# ---------------------------------------------------------------------------
# 5. @register_command — 顶级命令
# ---------------------------------------------------------------------------

@register_command("health")
def register_health(cli, ctx):
    """注册顶级 health 命令。"""

    @click.command("health")
    @click.option("--verbose", is_flag=True, help="显示详细信息")
    def health(verbose):
        """检查 API 健康状态。"""
        from cliyard.client.http import HttpClient
        client = HttpClient(ctx.base_url)
        try:
            resp = client.request("GET", "/api/v1/health")
            data = resp.json()
            if verbose:
                console.print(json.dumps(data, indent=2))
            else:
                status = data.get("status", "unknown")
                console.print(f"[green]✓[/green] API Status: {status}")
        except Exception as e:
            console.print(f"[red]✗[/red] Health check failed: {e}")

    cli.add_command(health)


# ---------------------------------------------------------------------------
# 6. @register_field_resolver — 字段值动态解析
# ---------------------------------------------------------------------------

@register_field_resolver("current_timestamp")
def current_timestamp(params, http_client, config):
    """演示字段解析器：自动填入当前时间戳。

    用法 YAML:
      params:
        body:
          - name: created_at
            type: string
            resolver: plugin:current_timestamp
    """
    return str(int(time.time() * 1000))
