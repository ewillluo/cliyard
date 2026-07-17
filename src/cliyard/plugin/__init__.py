"""Plugin registry for cliyard extensions.

Extension points:
- auth: Custom authentication step types
- types: Custom field types (validation + conversion)
- hooks: Custom pre/post request processing hooks
"""

from __future__ import annotations

from typing import Any, Callable


class PluginRegistry:
    """Central registry for all plugin types."""

    _auth_steps: dict[str, type] = {}
    _field_types: dict[str, type] = {}
    _hooks: dict[str, Callable] = {}
    _loaded: bool = False

    @classmethod
    def register_auth_step(cls, name: str, step_class: type) -> None:
        """Register a custom auth step class under a name.

        Args:
            name: Step type name (e.g. "my_oauth" accessible as "plugin:my_oauth").
            step_class: Class implementing the auth step protocol.
        """
        cls._auth_steps[name] = step_class

    @classmethod
    def register_field_type(cls, name: str, type_class: type) -> None:
        """Register a custom field type validator.

        Args:
            name: Field type name used in YAML specs (e.g. "email", "url").
            type_class: Class with a ``validate(value)`` classmethod/staticmethod.
        """
        cls._field_types[name] = type_class

    @classmethod
    def register_hook(cls, name: str, hook_fn: Callable) -> None:
        """Register a pre/post request processing hook.

        Args:
            name: Hook name for reference in YAML specs.
            hook_fn: Callable that receives request/response context.
        """
        cls._hooks[name] = hook_fn

    @classmethod
    def get_auth_step(cls, name: str) -> type | None:
        """Look up a registered auth step class by name.

        Returns:
            The registered class, or None if not found.
        """
        return cls._auth_steps.get(name)

    @classmethod
    def get_field_type(cls, name: str) -> type | None:
        """Look up a registered field type class by name.

        Returns:
            The registered class, or None if not found.
        """
        return cls._field_types.get(name)

    @classmethod
    def get_hook(cls, name: str) -> Callable | None:
        """Look up a registered hook function by name.

        Returns:
            The registered callable, or None if not found.
        """
        return cls._hooks.get(name)

    @classmethod
    def clear(cls) -> None:
        """Clear all registrations (primarily for testing)."""
        cls._auth_steps.clear()
        cls._field_types.clear()
        cls._hooks.clear()
        cls._loaded = False


# ---------------------------------------------------------------------------
# Decorator helpers
# ---------------------------------------------------------------------------


def register_auth_step(name: str):
    """Decorator that registers a class as an auth step plugin.

    Usage::

        @register_auth_step("my_oauth")
        class MyOAuthStep:
            def execute(self, auth_state, config, http_client):
                ...
    """
    def decorator(cls):
        PluginRegistry.register_auth_step(name, cls)
        return cls
    return decorator


def register_field_type(name: str):
    """Decorator that registers a class as a field type validator.

    Usage::

        @register_field_type("email")
        class EmailType:
            @staticmethod
            def validate(value):
                ...
    """
    def decorator(cls):
        PluginRegistry.register_field_type(name, cls)
        return cls
    return decorator


def register_hook(name: str):
    """Decorator that registers a function as a request hook.

    Usage::

        @register_hook("add_timestamp")
        def add_timestamp(context):
            ...
    """
    def decorator(fn):
        PluginRegistry.register_hook(name, fn)
        return fn
    return decorator
