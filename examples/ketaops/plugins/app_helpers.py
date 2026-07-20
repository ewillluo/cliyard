"""App management helper plugins — field resolvers for app operations."""

from cliyard.plugin import register_field_resolver


@register_field_resolver("get_latest_version")
def get_latest_version(params, http_client, config):
    """Resolve the latest version of an app from the market.

    Called when ``--version`` is not provided during app install.
    Queries ``/api/v1/package/list`` to find the matching app's latest version.
    """
    name = params.get("name")
    if not name:
        return ""
    try:
        resp = http_client.request("GET", "/api/v1/package/list")
        apps = resp.json().get("items", [])
        for app in apps:
            if app.get("name") == name:
                return app.get("latestVersion", "")
    except Exception:
        pass
    return ""
