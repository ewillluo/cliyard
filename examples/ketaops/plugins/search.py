"""Search plugin — top-level search command for SPL queries.

Maps to the same API as ketacli search:
1. POST /api/v1/jobs — create search job
2. GET /api/v1/jobs/{id} — poll until process=1
3. GET /api/v1/jobs/{id}/results — fetch results

Usage: ketaops-cli search 'search2 start="-1h" repo="logs" "error" | limit 10'
"""

import sys
import time

import click
from rich.console import Console
from rich.live import Live

from cliyard.output.formatter import format_rows_as_json, format_rows_as_table
from cliyard.plugin import register_command
from spl_parser.validate import validate_spl

console = Console()


def _exec(client, spl, limit, format_, raw, debug):
    body = {
        "query": spl,
        "startTime": 0,
        "endTime": 0,
        "collectSize": limit,
        "timeout": 3000,
        "app": "search",
        "preview": False,
        "mode": "smart",
    }
    resp = client.request("POST", "/api/v1/jobs", data=body)
    resp_data = resp.json()

    meta = resp_data.get("meta", {})
    if meta.get("process") == 1:
        failed = meta.get("failed")
        if failed:
            console.print(f"[red]Error:[/red] {failed}")
            return None, True
        result = resp_data.get("result", {})
    else:
        job_id = resp_data.get("id")
        if not job_id:
            console.print("[red]Error:[/red] No job ID returned")
            return None, True
        while True:
            status = client.request("GET", f"/api/v1/jobs/{job_id}").json()
            if status.get("process") == 1:
                break
            time.sleep(0.2)
        result = client.request("GET", f"/api/v1/jobs/{job_id}/results").json()

    if debug:
        duration = meta.get("duration", 0) or resp.elapsed.total_seconds() * 1000
        console.print(f"[dim][DEBUG] Server query duration: {int(duration)}ms[/dim]")

    if not result or not result.get("fields") or not result.get("rows"):
        return None, False

    if format_ == "json":
        console.print(format_rows_as_json(result))
    else:
        output = format_rows_as_table(result, raw=raw)
        if output:
            console.print(output)
    return None, False


@register_command("search")
def register_search(cli, ctx):
    from cliyard.client.http import HttpClient
    from cliyard.client.auth import run_auth_chain
    from cliyard.client.credentials import get_service_credentials

    @click.command("search")
    @click.argument("spl", type=str)
    @click.option("-l", "--limit", type=int, default=100, show_default=True, help="结果数量限制")
    @click.option("-f", "--format", "format_", type=click.Choice(["table", "json"]), default="table", show_default=True, help="输出格式")
    @click.option("--raw", is_flag=True, help="输出原始时间戳")
    @click.option("-w", "--watch", is_flag=True, help="实时刷新模式")
    @click.option("--interval", type=float, default=3.0, show_default=True, help="刷新间隔(秒)")
    @click.option("--debug", is_flag=True, help="显示服务端查询耗时")
    def search(spl, limit, format_, raw, watch, interval, debug):
        """Execute SPL search query.

        SPL is the full query string, e.g.:

        ketaops-cli search 'search2 start="-1h" repo="logs" "error" | limit 10'

        ketaops-cli search 'mstats start="-1h" span="1m" avg(cpu_usage) by host'
        """
        from cliyard.client.http import HttpClient
        from cliyard.client.auth import run_auth_chain
        from cliyard.client.credentials import get_service_credentials

        # Validate SPL syntax before sending
        spl_errors = validate_spl(spl)
        if spl_errors:
            console.print("[red]SPL 语法错误:[/red]")
            for err in spl_errors:
                console.print(f"  [red]行 {err['line']}, 列 {err['column']}: {err['message']}[/red]")
            return

        client = HttpClient(ctx.base_url)

        if ctx.auth_spec:
            run_auth_chain(ctx.auth_spec, http_client=client, pre_filled=ctx.pre_filled_auth)

        if not ctx.pre_filled_auth and ctx.auth_spec and ctx.auth_spec.get("persist"):
            service_name = ctx.auth_spec.get("id", "ketaops")
            saved = get_service_credentials(service_name)
            token = saved.get("token") if saved else None
            if token:
                client.default_headers["Authorization"] = f"Bearer {token}"

        if watch:
            with Live(console=console, refresh_per_second=1) as live:
                while True:
                    try:
                        _, is_error = _exec(client, spl, limit, format_, raw, debug)
                        if is_error:
                            break
                        time.sleep(interval)
                    except KeyboardInterrupt:
                        sys.exit(0)
        else:
            _, is_error = _exec(client, spl, limit, format_, raw, debug)
            if is_error:
                return

    cli.add_command(search)
