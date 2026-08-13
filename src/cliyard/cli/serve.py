"""``cliyard serve`` — Serve a web UI for YAML specs.

Usage::

    cliyard serve ./examples/demo --host 127.0.0.1 --port 8080
    cliyard serve ./examples/demo --open --reload

Starts a FastAPI server that turns the spec directory into a browsable web
interface (command tree, auto-generated forms, live execution steps, history).
"""

from __future__ import annotations

import os
import webbrowser

import click
import uvicorn

from cliyard.server.app import create_app


def _browser_url(host: str, port: int) -> str:
    """Build a browser-addressable URL (0.0.0.0/:: -> 127.0.0.1)."""
    display_host = "127.0.0.1" if host in ("0.0.0.0", "::") else host
    return f"http://{display_host}:{port}"


@click.command()
@click.argument(
    "spec_dir",
    type=click.Path(exists=True, file_okay=False, resolve_path=True),
)
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host address")
@click.option("--port", default=8080, type=int, show_default=True, help="Bind port")
@click.option("--open", is_flag=True, default=False, help="Open browser after startup")
@click.option("--reload", is_flag=True, default=False, help="Enable uvicorn auto-reload")
def serve(spec_dir: str, host: str, port: int, open: bool, reload: bool) -> None:
    """Serve a web UI for the YAML specs in SPEC_DIR.

    Turns the spec directory into a FastAPI-powered web interface with
    auto-generated forms, live execution steps, and execution history.
    """
    url = _browser_url(host, port)

    if reload:
        # Validate the spec up front (fail fast, clean error).
        _build_app_or_exit(spec_dir)
        # uvicorn --reload needs an import string, not an app instance.
        os.environ["CLIYARD_SPEC_DIR"] = spec_dir
        if open:
            webbrowser.open(url)
        click.echo(f"Serve spec {spec_dir} at {url} (reload on)")
        uvicorn.run(
            "cliyard.server.app:create_app_from_env",
            host=host,
            port=port,
            reload=True,
            factory=True,
        )
        return

    app = _build_app_or_exit(spec_dir)
    if open:
        webbrowser.open(url)
    click.echo(f"Serve spec {spec_dir} at {url}")
    uvicorn.run(app, host=host, port=port)


def _build_app_or_exit(spec_dir: str):
    """Build the app, converting invalid specs into a clean exit(1)."""
    try:
        return create_app(spec_dir)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
