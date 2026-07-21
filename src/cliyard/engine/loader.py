"""YAML spec loader for cliyard services.

Loads a service directory structure into a merged dict::

    spec_dir/
    ├── _auth.yaml      # Service config (server, auth)
    ├── repos.yaml          # Resource definition → resource name "repos"
    ├── users.yaml          # Resource definition → resource name "users"
    └── ...

Usage::

    from cliyard.engine.loader import load_service, load_resource

    service = load_service("/path/to/specs/github")
    resource = load_resource("/path/to/specs/github/repos.yaml")
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml


def load_service(spec_dir: str | Path) -> dict[str, Any]:
    """Load a cliyard service from a directory.

    Reads ``_auth.yaml`` for service metadata, then scans for
    ``*.yaml`` resource files (excluding ``_auth.yaml`` and
    ``_service.*.yaml`` variants like ``_service.local.yaml``).

    Each resource YAML filename (minus ``.yaml``) becomes the resource name.

    Args:
        spec_dir: Path to the service spec directory.

    Returns:
        Dict with keys: ``name``, ``version``, ``description``,
        ``server``, ``auth``, ``resources`` (list of resource dicts).

    Raises:
        FileNotFoundError: If ``_auth.yaml`` is missing.
        yaml.YAMLError: If any YAML file has syntax errors.
        ValueError: If ``_auth.yaml`` is missing required fields.
    """
    spec_dir = Path(spec_dir)
    service_path = spec_dir / "_auth.yaml"

    if not service_path.exists():
        raise FileNotFoundError(
            f"Missing _auth.yaml in {spec_dir}"
        )

    # Load service config
    service = _load_yaml(service_path)

    # Normalize server config: support both list (new) and dict (old) format
    server_raw = service.get("server", {})
    if isinstance(server_raw, list):
        # New format: [{name: "serve1", base_url: "...", prefix: "..."}, ...]
        servers: dict[str, Any] = {}
        for entry in server_raw:
            sname = entry.get("name", "")
            if sname:
                servers[sname] = entry
        if not servers:
            raise ValueError(f"{service_path}: 'server' list must contain at least one entry with a 'name'")
        service["servers"] = servers
        # First server is default
        service["server"] = servers[list(servers.keys())[0]]
    elif isinstance(server_raw, dict):
        # Old format: {base_url: "...", prefix: "..."}
        # Check if it's already a named dict
        if "base_url" in server_raw:
            service["servers"] = {"default": server_raw}
        else:
            # Already a named dict like {serve1: {base_url: ...}}
            service["servers"] = server_raw
    else:
        raise ValueError(f"{service_path}: 'server' is required and must be a mapping or list")

    # Scan for resource YAML files
    resources: list[dict[str, Any]] = []
    for yaml_file in sorted(spec_dir.glob("*.yaml")):
        if _is_resource_file(yaml_file):
            resource_name = yaml_file.stem  # e.g. "repos" from "repos.yaml"
            resource_spec = _load_yaml(yaml_file)

            # Validate resource has methods
            if not isinstance(resource_spec.get("methods"), dict):
                raise ValueError(
                    f"{yaml_file}: 'methods' is required and must be a mapping"
                )

            # Tag with resource name for downstream use (YAML name > filename)
            if "name" not in resource_spec:
                resource_spec["name"] = resource_name
            resources.append(resource_spec)

    # Ensure auth defaults to empty steps
    if "auth" not in service:
        service["auth"] = {"steps": []}

    # Discover plugins from the spec directory's plugins/ subdirectory
    from cliyard.plugin.discovery import discover_plugins

    discover_plugins(str(spec_dir))

    # Register plugins from YAML spec
    _register_plugins(service.get("plugins", {}))

    service["resources"] = resources
    return service


def load_resource(yaml_path: str | Path) -> dict[str, Any]:
    """Load a single resource YAML file.

    Args:
        yaml_path: Path to a resource YAML file.

    Returns:
        Parsed resource dict with ``methods`` key.

    Raises:
        FileNotFoundError: If the file does not exist.
        yaml.YAMLError: If the YAML has syntax errors.
        ValueError: If ``methods`` is missing or not a mapping.
    """
    yaml_path = Path(yaml_path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Resource YAML not found: {yaml_path}")

    resource = _load_yaml(yaml_path)

    if not isinstance(resource.get("methods"), dict):
        raise ValueError(f"{yaml_path}: 'methods' is required and must be a mapping")

    resource["name"] = yaml_path.stem
    return resource


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read and parse a YAML file with safe_load."""
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{path}: YAML must parse to a mapping (dict), got {type(data).__name__}")

    return data


def _is_resource_file(path: Path) -> bool:
    """Check if a YAML file is a resource file (not config files)."""
    name = path.name
    if name == "_auth.yaml":
        return False
    if name.startswith("_service.") and name.endswith(".yaml"):
        return False
    if name.startswith("_"):
        return False  # _groups.yaml, _other config files
    return True


def _register_plugins(plugins_config: dict[str, Any]) -> None:
    """Register plugins from a YAML ``plugins:`` section.

    Expected format::

        plugins:
          auth:
            my_oauth: mypackage.auth.MyOAuthStep
          types:
            email: mypackage.validators.EmailType
          hooks:
            add_timestamp: mypackage.hooks.add_timestamp

    Args:
        plugins_config: Dict parsed from the ``plugins:`` key in ``_auth.yaml``.
    """
    if not plugins_config:
        return

    from cliyard.plugin import PluginRegistry

    category_registry_map = {
        "auth": PluginRegistry._auth_steps,
        "types": PluginRegistry._field_types,
        "hooks": PluginRegistry._hooks,
    }

    for category, items in plugins_config.items():
        registry_attr = category_registry_map.get(category)
        if registry_attr is None:
            continue

        for name, import_path in items.items():
            try:
                module_path, attr_name = import_path.rsplit(".", 1)
                module = importlib.import_module(module_path)
                attr = getattr(module, attr_name)
                registry_attr[name] = attr
            except Exception as e:
                import sys
                print(
                    f"Warning: failed to load plugin {name!r} "
                    f"({import_path!r}): {e}",
                    file=sys.stderr,
                )
