"""Plugin discovery: entry points + directory scanning.

Discovers plugins from three sources:
1. Python entry points (``cliyard.auth``, ``cliyard.types``, ``cliyard.hooks``)
2. Spec-local plugin directory: ``{spec_dir}/plugins/*.py``
3. Global plugin directory: ``~/.cliyard/plugins/*.py``
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any

from cliyard.plugin import PluginRegistry


def discover_plugins(spec_dir: str | None = None) -> None:
    """Discover plugins from all sources.

    1. Entry points: ``cliyard.auth``, ``cliyard.types``, ``cliyard.hooks``
    2. Spec directory: ``{spec_dir}/plugins/*.py``
    3. Global dir: ``~/.cliyard/plugins/*.py``

    Only runs once; subsequent calls are no-ops after first successful load.

    Args:
        spec_dir: Optional path to a spec directory whose ``plugins/``
            subdirectory should be scanned.
    """
    if PluginRegistry._loaded:
        return

    _discover_entry_points()
    if spec_dir:
        _discover_directory(Path(spec_dir) / "plugins")
        # Also check alongside spec dir (e.g. src/<pkg>/plugins/)
        _discover_directory(Path(spec_dir).parent / "plugins")
    _discover_directory(Path.home() / ".cliyard" / "plugins")

    PluginRegistry._loaded = True


def _discover_entry_points() -> None:
    """Discover plugins via Python entry points.

    Uses Python's ``importlib.metadata`` entry_points API (PEP 621 / setuptools
    entry point groups). Each entry point's value should be a fully-qualified
    import path to the plugin class/function.

    Group mapping:
        ``cliyard.auth``  → PluginRegistry._auth_steps
        ``cliyard.types`` → PluginRegistry._field_types
        ``cliyard.hooks`` → PluginRegistry._hooks
    """
    try:
        from importlib.metadata import entry_points
    except ImportError:
        return  # Python < 3.9 — entry_points() not available

    for group_name, registry_attr in [
        ("cliyard.auth", "_auth_steps"),
        ("cliyard.types", "_field_types"),
        ("cliyard.hooks", "_hooks"),
    ]:
        try:
            eps = entry_points(group=group_name)
            for ep in eps:
                try:
                    obj = ep.load()
                    getattr(PluginRegistry, registry_attr)[ep.name] = obj
                except Exception:
                    # Silently skip plugins that fail to load
                    pass
        except Exception:
            # entry_points(group=...) raises TypeError in Python < 3.12
            # when the group is not found; TypeErrors are also acceptable
            # for missing optional dependencies
            pass


def _discover_directory(plugins_dir: Path) -> None:
    """Scan a directory for ``.py`` plugin files and import them.

    Each file's import triggers its ``@register_*`` decorators, which
    automatically register the plugin with ``PluginRegistry``.

    Ignores files starting with ``_`` and ``setup.py``.

    Args:
        plugins_dir: Directory path to scan.
    """
    if not plugins_dir.is_dir():
        return

    for py_file in sorted(plugins_dir.glob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "setup.py":
            continue
        module_name = py_file.stem
        try:
            # Import via file location — plugins dir is not on the Python path
            spec = importlib.util.spec_from_file_location(
                module_name, py_file
            )
            if spec is not None and spec.loader is not None:
                mod = importlib.util.module_from_spec(spec)
                sys.modules.setdefault(module_name, mod)
                spec.loader.exec_module(mod)
        except Exception:
            pass
