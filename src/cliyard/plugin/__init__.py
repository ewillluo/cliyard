"""Plugin registry for cliyard extensions.

Extension points:
- auth: Custom authentication step types
- types: Custom field types (validation + conversion)
- hooks: Custom pre/post request processing hooks
- methods: Custom business logic methods (multi-step API calls)
- commands: Custom top-level Click commands
"""

from __future__ import annotations

from typing import Any, Callable


class PluginRegistry:
    """Central registry for all plugin types."""

    _auth_steps: dict[str, type] = {}
    _field_types: dict[str, type] = {}
    _hooks: dict[str, Callable] = {}
    _methods: dict[str, Callable] = {}
    _commands: dict[str, Callable] = {}
    _loaded: bool = False

    @classmethod
    def register_auth_step(cls, name: str, step_class: type) -> None:
        cls._auth_steps[name] = step_class

    @classmethod
    def register_field_type(cls, name: str, type_class: type) -> None:
        cls._field_types[name] = type_class

    @classmethod
    def register_hook(cls, name: str, hook_fn: Callable) -> None:
        cls._hooks[name] = hook_fn

    @classmethod
    def register_method(cls, name: str, method_fn: Callable) -> None:
        """Register a custom business logic method.

        The function receives ``(params, http_client, config)`` and returns
        a dict that will be formatted as JSON output.

        Usage in YAML::

            methods:
              complex_task:
                type: plugin:my_method
                config:
                  key: value
                params:
                  body:
                    - name: input
                      type: string
        """
        cls._methods[name] = method_fn

    @classmethod
    def register_command(cls, name: str, command_fn: Callable) -> None:
        """Register a custom top-level Click command builder.

        The function receives ``(cli, ctx)`` where *cli* is the top-level
        ``click.Group`` and *ctx* is the ``ServiceContext``.
        """
        cls._commands[name] = command_fn

    @classmethod
    def get_auth_step(cls, name: str) -> type | None:
        return cls._auth_steps.get(name)

    @classmethod
    def get_field_type(cls, name: str) -> type | None:
        return cls._field_types.get(name)

    @classmethod
    def get_hook(cls, name: str) -> Callable | None:
        return cls._hooks.get(name)

    @classmethod
    def get_method(cls, name: str) -> Callable | None:
        return cls._methods.get(name)

    @classmethod
    def get_command(cls, name: str) -> Callable | None:
        return cls._commands.get(name)

    @classmethod
    def get_all_commands(cls) -> dict[str, Callable]:
        return dict(cls._commands)

    @classmethod
    def clear(cls) -> None:
        cls._auth_steps.clear()
        cls._field_types.clear()
        cls._hooks.clear()
        cls._methods.clear()
        cls._commands.clear()
        cls._loaded = False


# ---------------------------------------------------------------------------
# Decorator helpers
# ---------------------------------------------------------------------------


def register_auth_step(name: str):
    def decorator(cls):
        PluginRegistry.register_auth_step(name, cls)
        return cls
    return decorator


def register_field_type(name: str):
    def decorator(cls):
        PluginRegistry.register_field_type(name, cls)
        return cls
    return decorator


def register_hook(name: str):
    def decorator(fn):
        PluginRegistry.register_hook(name, fn)
        return fn
    return decorator


def register_method(name: str):
    """Decorator that registers a function as a custom method plugin.

    Usage::

        @register_method("multi_step_import")
        def multi_step_import(params, http_client, config):
            r1 = http_client.request("POST", "/api/step1", data=params)
            r2 = http_client.request("POST", "/api/step2", json=r1.json())
            return {"result": r2.json()}
    """
    def decorator(fn):
        PluginRegistry.register_method(name, fn)
        return fn
    return decorator


def register_command(name: str):
    """Decorator that registers a function as a top-level command builder.

    The function receives ``(cli, ctx)`` and should call
    ``cli.add_command(...)`` with the built Click command.
    """
    def decorator(fn):
        PluginRegistry.register_command(name, fn)
        return fn
    return decorator
