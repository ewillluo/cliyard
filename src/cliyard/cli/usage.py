"""``cliyard usage`` — Generate documentation from spec directory.

Scans a cliyard spec directory and outputs a structured reference
covering all resources, methods, parameters, and flow orchestrations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click


def _fmt_type(t: str) -> str:
    """Format a YAML type string for display."""
    return {"string": "str", "int": "int", "float": "float",
            "bool": "bool", "enum": "enum", "file": "path"}.get(t, t)


def _generate_docs(spec_dir: str) -> str:
    """Generate full documentation from a cliyard spec directory."""
    from cliyard.engine.loader import load_service, load_flows
    from cliyard.runtime.runner import create_cli
    from click.testing import CliRunner

    spec_path = Path(spec_dir).resolve()
    lines: list[str] = []
    P = lines.append

    P(f"# {spec_path.name} — CLI Reference")
    P("")

    # ── Load data ──
    service = load_service(spec_path)
    flows = load_flows(spec_path)
    P(f"Auto-generated from [cliyard](https://github.com/guolong123/cliyard) specs.")
    P(f"**Resources**: {len(service.get('resources', []))}  ")
    if flows:
        P(f"**Flows**: {len(flows)}  ")
    P("")

    # ── Build CLI and capture --help ──
    P("## Usage")
    P("")
    P("```")
    try:
        cli = create_cli(spec_path)
        runner = CliRunner()
        r = runner.invoke(cli, ["--help"])
        P(r.output)
    except Exception:
        P("(unable to build CLI)")
    P("```")
    P("")

    # ── Resources ──
    resources = service.get("resources", [])
    if resources:
        P("## Resource Commands")
        P("")
        P("| Resource | Methods | Description |")
        P("|----------|---------|-------------|")
        for res in resources:
            rname = res.get("name", "?")
            desc = res.get("description", "")
            methods = list(res.get("methods", {}).keys())
            methods_str = ", ".join(f"`{m}`" for m in methods)
            P(f"| `{rname}` | {methods_str} | {desc} |")
        P("")

        # Detailed method docs
        for res in resources:
            rname = res.get("name", "?")
            methods = res.get("methods", {})
            for mname, mspec in methods.items():
                desc = mspec.get("description", "")
                http = mspec.get("http", {})
                method = http.get("method", "?")
                path = http.get("path", rname)

                P(f"### `{rname} {mname}`")
                if desc:
                    P(f"{desc}  ")
                P(f"`{method} {path}`  ")
                P("")

                params = mspec.get("params", {})
                has_params = any(params.get(loc) for loc in ("query", "body", "path", "header"))
                if has_params:
                    P("| Option | Type | Required | Default | Description |")
                    P("|--------|------|----------|---------|-------------|")
                    for loc in ("path", "query", "body", "header", "argument"):
                        for p in params.get(loc, []):
                            pname = p.get("name", "?")
                            ptype = _fmt_type(p.get("type", "string"))
                            req = "yes" if p.get("required") else ""
                            default = str(p.get("default", ""))
                            pdesc = p.get("description", "")
                            choices = p.get("choices")
                            if choices:
                                ptype += f" ({','.join(choices)})"
                            P(f"| `--{pname}` | {ptype} | {req} | {default} | {pdesc} |")
                    P("")

                output = mspec.get("output", {})
                if output.get("items_path"):
                    P(f"Output fields (from `{output['items_path']}`):  ")
                    fields = output.get("fields", [])
                    if fields:
                        for f in fields:
                            fname = f.get("name", "?")
                            falias = f.get("alias", "")
                            P(f"- **{fname}** — {falias}")
                    P("")

    # ── Flows ──
    if flows:
        P("## Flow Orchestrations")
        P("")
        P("| Command | Description | Steps |")
        P("|---------|-------------|-------|")
        for f in flows:
            desc = f.description or ""
            step_count = len(f.steps)
            P(f"| `{f.command}` | {desc} | {step_count} |")
        P("")

        for f in flows:
            P(f"### `flow-run {f.command}`")
            if f.description:
                P(f"{f.description}  ")
            P("")

            if f.params:
                P("| Option | Type | Required | Default | Description |")
                P("|--------|------|----------|---------|-------------|")
                for loc in ("query", "body", "header"):
                    for p in f.params.get(loc, []):
                        pname = p.get("name", "?")
                        ptype = _fmt_type(p.get("type", "string"))
                        req = "yes" if p.get("required") else ""
                        default = str(p.get("default", ""))
                        pdesc = p.get("description", "")
                        choices = p.get("choices")
                        if choices:
                            ptype += f" ({','.join(choices)})"
                        P(f"| `--{pname}` | {ptype} | {req} | {default} | {pdesc} |")
                P("")

            P("Steps:")
            for i, step in enumerate(f.steps, 1):
                sid = step.id or f"step{i}"
                use = step.use or ""
                desc = step.description or sid
                if use:
                    P(f"{i}. **{desc}** — `{use}`")
                else:
                    onr = "on_result" if step.on_result else ""
                    P(f"{i}. **{desc}** — {onr}")
            P("")

    return "\n".join(lines)


@click.command()
@click.argument(
    "spec_dir",
    required=False,
    type=click.Path(exists=False, file_okay=False, resolve_path=True),
)
@click.option(
    "-o",
    "--output",
    default=None,
    type=click.Path(file_okay=False, resolve_path=False),
    help="Output file path (default: stdout)",
)
def usage(spec_dir: str | None, output: str | None) -> None:
    """Generate usage documentation from YAML specs.

    Scans a cliyard spec directory and produces a structured reference
    of all resources, methods, parameters, and flow orchestrations.

    If SPEC_DIR is omitted, auto-discovers by looking for ``_auth.yaml``
    in the current directory or ``specs/`` subdirectory.
    """
    # Resolve spec directory
    if spec_dir:
        spec_path = Path(spec_dir).resolve()
    else:
        cwd = Path.cwd().resolve()
        for candidate in [cwd, cwd / "specs"]:
            if (candidate / "_auth.yaml").is_file():
                spec_path = candidate
                break
        else:
            click.echo("Error: no _auth.yaml found. Specify directory or run from a project root.", err=True)
            raise SystemExit(1)

    click.echo(f"Scanning {spec_path}...", err=True)

    docs = _generate_docs(str(spec_path))

    if output:
        out_path = Path(output)
        out_path.write_text(docs, encoding="utf-8")
        click.echo(f"Written to {out_path}", err=True)
    else:
        click.echo(docs)
