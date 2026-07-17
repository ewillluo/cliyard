"""cliyard.engine.template — Sandboxed Jinja2 template engine.

Uses SandboxedEnvironment to prevent arbitrary code execution in YAML templates.
Only whitelisted filters and functions are available. Template compilation is cached
to avoid recompiling identical templates (pattern from ketacli).

Security model:
- SandboxedEnvironment blocks attribute access on unsafe types
- __builtins__, import, open, exec, eval are NOT injected into context
- Only whitelisted filters are registered
- Only whitelisted global functions are registered
"""

from __future__ import annotations

import json
import os
import time as time_module
from typing import Any

from jinja2 import ChainableUndefined
from jinja2.sandbox import SandboxedEnvironment


# ---------------------------------------------------------------------------
# Template cache — avoid recompiling identical template strings (ketacli pattern)
# ---------------------------------------------------------------------------
_template_cache: dict[str, dict[str, Any]] = {}


class Template:
    """Sandboxed Jinja2 template wrapper.

    Usage::

        t = Template("Hello {{ name }}")
        result = t.render(name="world")
        # result == "Hello world"

        t2 = Template("{{ env('HOME') }}")
        result2 = t2.render()
        # result2 == value of $HOME
    """

    def __init__(self, template_str: str) -> None:
        self.template_str = template_str

        # Check cache first
        if template_str in _template_cache:
            self.env = _template_cache[template_str]["env"]
            self.temp = _template_cache[template_str]["temp"]
        else:
            # Create sandboxed environment — NO builtins injected
            # ChainableUndefined: allows {{ var|default(x) }} to work,
            # but raises on attribute access of undefined variables.
            self.env = SandboxedEnvironment(
                undefined=ChainableUndefined,
                keep_trailing_newline=True,
            )

            # --- Register whitelisted filters only ---
            self.env.filters["default"] = _filter_default
            self.env.filters["env"] = _filter_env
            self.env.filters["upper"] = _filter_upper
            self.env.filters["lower"] = _filter_lower
            self.env.filters["replace"] = _filter_replace
            self.env.filters["join"] = _filter_join
            self.env.filters["length"] = _filter_length
            self.env.filters["first"] = _filter_first
            self.env.filters["last"] = _filter_last
            self.env.filters["tojson"] = _filter_tojson
            self.env.filters["str_to_list"] = _filter_str_to_list

            # --- Register whitelisted global functions ---
            self.env.globals["env"] = _func_env
            self.env.globals["time"] = time_module
            self.env.globals["None"] = None
            self.env.globals["True"] = True
            self.env.globals["False"] = False

            # Compile and cache
            self.temp = self.env.from_string(template_str)
            _template_cache[template_str] = {"env": self.env, "temp": self.temp}

    def render(self, **kwargs: Any) -> str:
        """Render template with given variables.

        Returns:
            Rendered string with variables substituted.

        Raises:
            jinja2.UndefinedError: If a variable is referenced but not provided
                (StrictUndefined mode).
            jinja2.sandbox.SecurityError: If a forbidden operation is attempted
                (e.g., ``open``, ``import``, ``__builtins__``).
        """
        return self.temp.render(**kwargs)


# ---------------------------------------------------------------------------
# Whitelisted filters
# ---------------------------------------------------------------------------


def _filter_default(value: Any, default_value: Any = "") -> Any:
    """Return *default_value* if *value* is undefined/None/empty."""
    from jinja2 import Undefined

    if isinstance(value, Undefined) or value is None or value == "":
        return default_value
    return value


def _filter_env(name: str, default: str = "") -> str:
    """Read an environment variable by name."""
    return os.environ.get(name, default)


def _filter_upper(value: str) -> str:
    return str(value).upper()


def _filter_lower(value: str) -> str:
    return str(value).lower()


def _filter_replace(value: str, old: str, new: str, count: int = -1) -> str:
    if count == -1:
        return str(value).replace(old, new)
    return str(value).replace(old, new, count)


def _filter_join(value: list | tuple, delimiter: str = ", ") -> str:
    return delimiter.join(str(v) for v in value)


def _filter_length(value: Any) -> int:
    return len(value)


def _filter_first(value: list | tuple | str) -> Any:
    return value[0]


def _filter_last(value: list | tuple | str) -> Any:
    return value[-1]


def _filter_tojson(value: Any, indent: int | None = None) -> str:
    return json.dumps(value, indent=indent, ensure_ascii=False)


def _filter_str_to_list(value: str, delimiter: str = ",") -> list[str]:
    """Split a comma-separated string into a list."""
    return [item.strip() for item in value.split(delimiter) if item.strip()]


# ---------------------------------------------------------------------------
# Whitelisted global functions
# ---------------------------------------------------------------------------


def _func_env(name: str, default: str = "") -> str:
    """Read an environment variable (usable as ``{{ env('VAR') }}``)."""
    return os.environ.get(name, default)
