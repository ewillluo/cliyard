"""Auth commands for generated CLIs (add/status/switch/logout)."""

import os
import time
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from cliyard.client.auth import run_auth_chain
from cliyard.client.credentials import (
    save_profile,
    get_profile,
    get_current_profile,
    load_credentials,
    delete_profile,
    switch_profile,
)
from cliyard.client.http import HttpClient

_console = Console()


def add_auth_commands(cli: click.Group, service: dict, base_url: str = "") -> None:
    """Register auth command group on a CLI group."""

    @cli.group()
    def auth():
        "Manage authentication credentials."

    @auth.command("add")
    @click.option("-n", "--name", default=None, help="Environment name (default: prod)")
    @click.option("-u", "--username", help="Login username")
    @click.option("-p", "--password", help="Login password")
    @click.option("-t", "--token", help="API token (skip login, save directly)")
    @click.option("-e", "--endpoint", help="Server endpoint URL")
    @click.option("--default", "set_default", is_flag=True, help="Set as default environment")
    @click.option("--set", "set_vars", type=str, multiple=True, help="Set env vars, e.g. --set API_KEY=abc")
    def auth_add(name, username, password, token, endpoint, set_default, set_vars):
        profile_name = name or "prod"
        auth_spec = service.get("auth")
        if not auth_spec:
            _console.print("[red]No auth config found[/red]")
            return
        _base_url = endpoint or base_url
        client = HttpClient(_base_url)
        if token:
            save_profile(profile_name, {"token": token, "endpoint": _base_url},
                         set_current=set_default or not get_current_profile())
            _console.print(f"[green]Token saved for '{profile_name}'[/green]")
            return
        # Set env vars from YAML auth.params mapping
        auth_params = auth_spec.get("params", {})
        if username:
            env_user = auth_params.get("username", "KETA_USER")
            os.environ[env_user] = username
        if password:
            env_pass = auth_params.get("password", "KETA_PASS")
            os.environ[env_pass] = password
        # Set arbitrary env vars from --set
        for kv in (set_vars or ()):
            if "=" in kv:
                k, v = kv.split("=", 1)
                os.environ[k.strip()] = v.strip()
        try:
            auth_state = run_auth_chain(auth_spec, http_client=client)
        except Exception as e:
            _console.print(f"[red]Auth failed: {e}[/red]")
            return
        persist = auth_spec.get("persist", {})
        if persist.get("to") == "cliyard-config":
            fields = {"endpoint": base_url}
            for fn, fc in persist.get("fields", {}).items():
                ref = fc.get("from", "")
                dft = fc.get("default")
                if "." in ref:
                    step, key = ref.split(".", 1)
                    sv = auth_state.get(step)
                    val = sv.get(key) if isinstance(sv, dict) else None
                else:
                    val = auth_state.get(ref)
                if val is not None:
                    fields[fn] = val
                elif dft is not None:
                    fields[fn] = dft
            if fields:
                save_profile(profile_name, fields, set_current=set_default or not get_current_profile())
                _console.print(f"[green]Credentials saved for '{profile_name}'[/green]")
            else:
                _console.print("[yellow]No credentials to save.[/yellow]")

    @auth.command("status")
    def auth_status():
        creds = load_credentials()
        profiles = creds.get("profiles", {})
        current = creds.get("current")
        if not profiles:
            _console.print("[yellow]No environments configured.[/yellow]")
            return
        table = Table()
        for col in ("Environment", "Endpoint", "Token", "Expires"):
            table.add_column(col)
        for nm, flds in profiles.items():
            m = "* " if nm == current else "  "
            ep = flds.get("endpoint", "-")
            tk = (flds.get("token", "")[:20] + "...") if flds.get("token") else "-"
            exp = flds.get("expires_at")
            exs = f"{int(exp) - int(time.time()) // 3600}h" if exp else "never"
            table.add_row(f"{m}{nm}", ep, tk, exs)
        _console.print(table)

    @auth.command("switch")
    @click.argument("env_name", required=False)
    def auth_switch(env_name):
        if not env_name:
            cur = get_current_profile()
            if cur:
                _console.print(f"[bold]{cur.get('_name', '?')}[/bold]")
            else:
                _console.print("[yellow]No default set.[/yellow]")
            return
        if switch_profile(env_name):
            _console.print(f"[green]Switched to '{env_name}'[/green]")
        else:
            _console.print(f"[red]Not found: {env_name}[/red]")

    @auth.command("logout")
    @click.argument("env_name", required=False)
    @click.option("--all", "clear_all", is_flag=True)
    def auth_logout(env_name, clear_all):
        if env_name:
            delete_profile(env_name)
            _console.print(f"[green]Removed: {env_name}[/green]")
        elif clear_all:
            p = os.path.expanduser("~/.cliyard/credentials.yaml")
            if os.path.exists(p):
                os.remove(p)
                _console.print("[green]All cleared.[/green]")
        else:
            cur = get_current_profile()
            if cur:
                _console.print(f"Current: {cur.get('_name', '?')}")
