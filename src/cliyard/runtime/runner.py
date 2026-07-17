"""cliyard.runtime.runner — Entry-point pipeline for spec-driven CLIs.

Provides :func:`run_with_spec`, the single function that a generated CLI
calls to load a YAML service spec, build Click commands, and execute the CLI.

Usage (from a generated CLI's ``__main__.py``)::

    import sys
    from cliyard.runtime import run_with_spec

    sys.exit(run_with_spec("path/to/spec-dir"))
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, NoReturn

import click


def create_cli(spec_dir: str) -> click.Group:
    """Load a cliyard service spec and build a Click CLI group.

    Returns a ``click.Group`` with all resource commands registered.
    Call ``cli()`` to execute, or attach to another Click app::

        from cliyard.runtime import create_cli
        app = click.Group()
        app.add_command(create_cli("path/to/spec"))

    Args:
        spec_dir: Path to the service spec directory.

    Returns:
        ``click.Group`` with resource commands ready to run.
    """
    from cliyard.engine.loader import load_service
    from cliyard.engine.builder import build_resource_group, ServiceContext

    spec_path = Path(spec_dir).resolve()
    if not spec_path.is_dir():
        raise FileNotFoundError(f"Spec directory not found: {spec_path}")

    service = load_service(spec_path)

    service_name: str = service.get("name", "cliyard")
    description: str = service.get("description", service_name)
    server: dict[str, Any] = service.get("server", {})
    auth_spec: dict[str, Any] | None = service.get("auth")

    # Override base_url with saved endpoint from current profile
    from cliyard.client.credentials import get_current_profile
    saved_profile = get_current_profile()
    saved_endpoint = saved_profile.get("endpoint") if saved_profile else None
    base_url = saved_endpoint or server.get("base_url", "http://localhost:8080")

    # Auto-read saved credentials if persist is configured
    pre_filled: dict[str, Any] | None = None
    if auth_spec and auth_spec.get("persist"):
        from cliyard.client.credentials import get_service_credentials

        service_id: str = auth_spec.get("id", service_name)
        saved = get_service_credentials(service_id)
        if saved:
            persist = auth_spec.get("persist", {})
            persist_fields = persist.get("fields", {})
            pre_filled = {}
            for storage_key, field_config in persist_fields.items():
                ref: str = field_config.get("from", "")
                if "." in ref:
                    step_name, field_name = ref.split(".", 1)
                    value = saved.get(storage_key)
                    if value is not None:
                        if step_name not in pre_filled:
                            pre_filled[step_name] = {}
                        pre_filled[step_name][field_name] = value
                else:
                    value = saved.get(storage_key)
                    if value is not None:
                        pre_filled[ref] = value
            if not persist_fields:
                pre_filled = saved

    ctx = ServiceContext(
        base_url=base_url,
        prefix=server.get("prefix", ""),
        auth_spec=auth_spec,
        pre_filled_auth=pre_filled,
    )

    cli = click.Group(name=service_name, help=description)

    from cliyard.runtime.auth_commands import add_auth_commands
    add_auth_commands(cli, service, base_url=server.get("base_url", "http://localhost:8080"))

    for resource in service.get("resources", []):
        group = build_resource_group(resource["name"], resource, ctx)
        cli.add_command(group)

    return cli


def run_with_spec(spec_dir: str) -> NoReturn:
    """Load a cliyard service spec and run the generated CLI.

    This is the primary entry point for generated CLIs.  It reads the
    YAML service spec from *spec_dir*, dynamically builds a Click CLI
    tree, and executes it.

    Args:
        spec_dir: Path to the service spec directory (must contain
            ``_service.yaml`` and ``*.yaml`` resource files).

    Returns:
        This function never returns; it calls ``sys.exit()`` with the
        appropriate exit code from Click.

    Example:
        >>> import sys
        >>> from cliyard.runtime import run_with_spec
        >>> sys.exit(run_with_spec("tests/fixtures/spec-dir"))
    """
    try:
        cli = create_cli(spec_dir)
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    try:
        code: int = cli(standalone_mode=False)
    except SystemExit as e:
        code = int(e.code) if e.code is not None else 0
    except Exception as exc:
        click.echo(f"Error: {exc}", err=True)
        code = 1

    sys.exit(code)
