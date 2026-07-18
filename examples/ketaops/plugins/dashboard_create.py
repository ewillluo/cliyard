"""Dashboard create/update plugins — chart YAML ↔ Pithos XML."""

import json

from cliyard.plugin import register_method
from chart_dsl import chart_yaml_to_pithos


def _build_body(params, config, xml_content=None, xml_vars=None):
    return {
        "id": params.get("id"),
        "name": params.get("name") or params.get("id"),
        "title": params.get("title") or params.get("id"),
        "app": params.get("app", "search"),
        "description": params.get("description", ""),
        "preset": 2,
        "scope": config.get("scope", "app"),
        "owner": config.get("owner", "keta"),
        "dashboardType": "xml" if xml_content else "json",
        "xml": xml_content or "",
        "xmlVariables": xml_vars or {},
        "refresh": 0, "time": None, "theme": None,
        "variables": [], "options": None, "charts": [],
        "groupPathNames": None,
        "operations": ["list", "reassign_knowledge_objects", "share", "delete", "edit"],
        "appOperations": ["reassign_knowledge_objects", "list", "delete", "edit"],
    }


def _load_chart(chart_file):
    if not chart_file:
        return None, {}
    xml_content, xml_vars_json = chart_yaml_to_pithos(chart_file)
    xml_vars = json.loads(xml_vars_json) if isinstance(xml_vars_json, str) else xml_vars_json
    return xml_content, xml_vars


@register_method("dashboard_create")
def dashboard_create(params, http_client, config):
    xml_content, xml_vars = _load_chart(params.get("chart_file"))
    body = _build_body(params, config, xml_content, xml_vars)
    endpoint = config.get("endpoint", "/api/v1/dashboard")
    return http_client.request("POST", endpoint, data=body).json()


@register_method("dashboard_update")
def dashboard_update(params, http_client, config):
    xml_content, xml_vars = _load_chart(params.get("chart_file"))
    body = _build_body(params, config, xml_content, xml_vars)
    dash_id = params.get("id")
    base = config.get("endpoint", "/api/v1/dashboard")
    endpoint = f"{base}/{dash_id}" if dash_id else base
    return http_client.request("PUT", endpoint, data=body).json()
