"""KetaDB dashboard get plugin — raw JSON or chart DSL YAML output.

Supports ``--chart-yaml`` flag to reverse the dashboard_create flow:
fetch a dashboard by name, extract Pithos XML, convert to chart DSL YAML
via :func:`.chart_dsl.xml_to_chart_yaml`, and write to stdout.

YAML method usage::

    methods:
      get:
        type: plugin:dashboard_get
        config:
          endpoint: /api/v1/dashboard
        params:
          path:
            - name: name
              type: string
              required: true
              description: 仪表盘名称
          body:
            - name: chart_yaml
              type: bool
              default: false
              description: 以 chart DSL YAML 格式输出
"""

import sys

import yaml

from cliyard.plugin import register_method

from chart_dsl import xml_to_chart_yaml


@register_method("dashboard_get")
def dashboard_get(params: dict, http_client, config: dict) -> dict:
    """Fetch a KetaDB dashboard, optionally converting to chart DSL YAML.

    When ``chart_yaml`` is truthy in *params*, the plugin reads the XML
    from the API response, converts it to chart DSL via
    :func:`xml_to_chart_yaml`, and writes YAML directly to stdout.
    A ``{"_formatted": True}`` dict is returned to tell the builder
    that output has already been handled.

    Otherwise returns the raw API response dict for default JSON output.

    Args:
        params: Merged CLI parameters.
        http_client: :class:`cliyard.client.http.HttpClient` instance.
        config: Plugin config dictionary with ``endpoint`` key.

    Returns:
        API response dict, or ``{"_formatted": True}`` for YAML mode.
    """
    name = params.get("name")
    endpoint_base = config.get("endpoint", "/api/v1/dashboard")
    endpoint = f"{endpoint_base}/{name}"

    resp = http_client.request("GET", endpoint)
    data = resp.json()

    if params.get("chart_yaml"):
        xml_text = data.get("xml", "")
        chart_data = xml_to_chart_yaml(xml_text, data)
        yaml.dump(
            chart_data,
            sys.stdout,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            width=1000000,
        )
        return {"_formatted": True}

    return data
