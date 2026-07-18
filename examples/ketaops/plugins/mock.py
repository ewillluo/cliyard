"""Data injection plugin — generate mock data or insert raw data into repositories.

APIs:
- POST /api/v1/data?repo=<name> — insert records

Usage:
  # Generate mode
  ketaops-cli mock --type log --repo logs -n 100
  ketaops-cli mock --type data --data '{"test":1}' -n 100 --render

  # Insert mode
  ketaops-cli mock --repo logs --data 'line1\nline2'
  ketaops-cli mock -f /var/log/syslog --repo logs
  echo '{"raw":"test"}' | ketaops-cli mock --repo logs
"""

import json
import os
import random
import sys
import time

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
)

from cliyard.plugin import register_command

console = Console()


# ---------------------------------------------------------------------------
# Log type templates
# ---------------------------------------------------------------------------

LOG_TEMPLATES = {
    "nginx": {
        "render": '{"raw":"{{ random.choice(["192.168.1.1","192.168.1.2","192.168.1.3"]) }} - - '
        '[{{ datetime.datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000") }}] '
        '\\"{{ random.choice(["GET","POST","PUT"]) }} {{ random.choice(["/","/index.html","/api/v1/users"]) }} HTTP/1.1\\" '
        '{{ random.choice(["200","404","500"]) }} {{ random.randint(100,10000) }}",'
        '"host":"{{ random.choice(["web-01","web-02","web-03"]) }}","origin":"nginx"}',
        "no_render": '{{"raw":"{ip} - - [{date}] \\"{method} {path} HTTP/1.1\\" {status} {size}",'
        '"host":"{host}","origin":"nginx"}}',
    },
    "java": {
        "render": '{"raw":"{{ datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f"[:23]) }} '
        '[{{ random.choice(["main","http-nio-8080","pool-1-thread-1"]) }}] '
        '{{ random.choice(["INFO","WARN","ERROR"]) }} '
        'com.example.Service - {{ faker.sentence() }}",'
        '"host":"{{ random.choice(["app-01","app-02"]) }}",'
        '"level":"{{ random.choice(["INFO","WARN","ERROR"]) }}",'
        '"origin":"java"}',
        "no_render": '{{"raw":"{date} [{thread}] {level} com.example.Service - {msg}",'
        '"host":"{host}","level":"{level}","origin":"java"}}',
    },
    "linux": {
        "render": '{"raw":"{{ datetime.datetime.now().strftime("%b %d %H:%M:%S") }} '
        '{{ random.choice(["localhost","server-01","server-02"]) }} '
        '{{ random.choice(["kernel","sshd","systemd"]) }}: {{ faker.sentence() }}",'
        '"host":"{{ random.choice(["linux-01","linux-02"]) }}",'
        '"origin":"linux"}',
        "no_render": '{{"raw":"{date} {hostname} {service}: {msg}","host":"{host}","origin":"linux"}}',
    },
    "apache": {
        "render": '{"raw":"{{ random.choice(["10.0.0.1","10.0.0.2","10.0.0.3"]) }} - - '
        '[{{ datetime.datetime.now().strftime("%d/%b/%Y:%H:%M:%S +0000") }}] '
        '\\"{{ random.choice(["GET","POST","HEAD"]) }} {{ random.choice(["/","/about","/contact"]) }} HTTP/1.1\\" '
        '{{ random.choice(["200","404","500"]) }} {{ random.randint(200,5000) }}",'
        '"host":"{{ random.choice(["apache-01","apache-02"]) }}","origin":"apache"}',
        "no_render": '{{"raw":"{ip} - - [{date}] \\"{method} {path} HTTP/1.1\\" {status} {size}",'
        '"host":"{host}","origin":"apache"}}',
    },
    "mysql": {
        "render": '{"raw":"{{ datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) }} '
        '{{ random.choice(["[Note]","[Warning]","[ERROR]"]) }} {{ faker.sentence() }}",'
        '"host":"{{ random.choice(["mysql-01","mysql-02"]) }}",'
        '"level":"{{ random.choice(["Note","Warning","ERROR"]) }}",'
        '"origin":"mysql"}',
        "no_render": '{{"raw":"{date} [{level}] {msg}","host":"{host}","level":"{level}","origin":"mysql"}}',
    },
    "windows": {
        "render": '{"raw":"{{ datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")) }} '
        'EventID: {{ random.randint(1000,9999) }} '
        'Source: {{ random.choice(["System","Application","Security"]) }} '
        'Level: {{ random.choice(["Information","Warning","Error"]) }} '
        'Description: {{ faker.sentence() }}",'
        '"host":"{{ random.choice(["WIN-01","WIN-02"]) }}",'
        '"event_id":"{{ random.randint(1000,9999) }}",'
        '"source":"{{ random.choice(["System","Application","Security"]) }}",'
        '"level":"{{ random.choice(["Information","Warning","Error"]) }}",'
        '"origin":"windows"}',
        "no_render": '{{"raw":"{date} EventID: {eid} Source: {src} Level: {lvl} Description: {msg}",'
        '"host":"{host}","event_id":{eid},"source":"{src}","level":"{lvl}","origin":"windows"}}',
    },
    "mongodb": {
        "render": '{"raw":"{{ datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000+0000") }} '
        '{{ random.choice(["I","W","E"]) }} '
        '{{ random.choice(["COMMAND","QUERY","WRITE","NETWORK"]) }} '
        '{{ faker.sentence() }}",'
        '"host":"{{ random.choice(["mongo-01","mongo-02"]) }}",'
        '"severity":"{{ random.choice(["I","W","E"]) }}",'
        '"component":"{{ random.choice(["COMMAND","QUERY","WRITE","NETWORK"]) }}",'
        '"origin":"mongodb"}',
        "no_render": '{{"raw":"{date} {sev} {comp} {msg}","host":"{host}",'
        '"severity":"{sev}","component":"{comp}","origin":"mongodb"}}',
    },
    "docker": {
        "render": '{"raw":"{{ datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S.000000000Z") }} '
        'container={{ random.choice(["web-app","database","redis"]) }} '
        'level={{ random.choice(["info","warn","error"]) }} '
        'msg=\\"{{ faker.sentence() }}\\"",'
        '"host":"{{ random.choice(["docker-01","docker-02"]) }}",'
        '"container":"{{ random.choice(["web-app","database","redis"]) }}",'
        '"level":"{{ random.choice(["info","warn","error"]) }}",'
        '"origin":"docker"}',
        "no_render": '{{"raw":"{date} container={container} level={lvl} msg=\\"{msg}\\"",'
        '"host":"{host}","container":"{container}","level":"{lvl}","origin":"docker"}}',
    },
}

LOG_TYPES = list(LOG_TEMPLATES.keys())

METRICS_TEMPLATE_RENDER = (
    '{"host":"{{ faker.ipv4_private() }}",'
    '"region":"{{ random.choice(["us-west-2","ap-shanghai","ap-nanjing"]) }}",'
    '"timestamp":{{ int(time.time() * 1000) }},'
    '"fields":{'
    '"cpu_percent":{{ random.randint(0,100) }},'
    '"memory_percent":{{ random.randint(0,100) }},'
    '"disk_percent":{{ random.randint(0,100) }}'
    "}}"
)


def _get_template(log_type, render):
    """Get log template string for the given type."""
    tpl = LOG_TEMPLATES.get(log_type)
    if not tpl:
        raise ValueError(f"Unsupported log type: {log_type}")
    return tpl["render"] if render else tpl["no_render"]


def _no_render_fill(template, fields):
    """Fill a no_render template with field values."""
    return template.format(**fields)


def _random_choices():
    """Generate random field values for no_render mode."""
    ips = ["192.168.1.1", "192.168.1.2", "192.168.1.3"]
    methods = ["GET", "POST", "PUT"]
    paths = ["/", "/index.html", "/api/v1/users"]
    statuses = ["200", "404", "500"]
    levels = ["INFO", "WARN", "ERROR"]
    containers = ["web-app", "database", "redis"]
    return {
        "ip": random.choice(ips),
        "method": random.choice(methods),
        "path": random.choice(paths),
        "status": random.choice(statuses),
        "size": random.randint(100, 10000),
        "level": random.choice(levels),
        "thread": random.choice(["main", "http-nio-8080", "pool-1-thread-1"]),
        "hostname": random.choice(["localhost", "server-01", "server-02"]),
        "service": random.choice(["kernel", "sshd", "systemd"]),
        "container": random.choice(containers),
        "lvl": random.choice(["info", "warn", "error"]),
        "host": random.choice(["host-01", "host-02", "host-03"]),
        "eid": random.randint(1000, 9999),
        "src": random.choice(["System", "Application", "Security"]),
        "sev": random.choice(["I", "W", "E"]),
        "comp": random.choice(["COMMAND", "QUERY", "WRITE"]),
    }


def _gen_records(template_str, count, render):
    """Generate *count* records from a template string. Returns list of dicts."""
    from cliyard.engine.template import Template

    if render:
        tmpl = Template(template_str)
        raw = tmpl.batch_render(count, render=True)
        return [json.loads(r) for r in raw]

    # No render: use template as-is
    if "{{" not in template_str and "{%" not in template_str:
        return [json.loads(template_str) for _ in range(count)]

    # Log templates with {placeholder} syntax
    records = []
    for _ in range(count):
        date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        fields = _random_choices()
        fields["date"] = date
        fields["msg"] = f"Processing request ID {random.randint(10000,99999)}"
        records.append(json.loads(_no_render_fill(template_str, fields)))
    return records


def _send(client, repo, records, query_params=None):
    """Send records to the API."""
    params = {"repo": repo}
    if query_params:
        params.update(query_params)
    return client.request("POST", "/api/v1/data", data=records, query_params=params)


# ---------------------------------------------------------------------------
# Log type completion
# ---------------------------------------------------------------------------

def _log_type_completion(ctx, param, incomplete):
    return [t for t in LOG_TYPES if t.startswith(incomplete)]


# ---------------------------------------------------------------------------
# Generate mode
# ---------------------------------------------------------------------------

def _run_generate(client, repo, mock_type, data, file_path, number, batch, gzip, render, log_type):
    """Generate mock data and upload."""
    start = time.time()

    # Resolve template
    if file_path:
        with open(file_path) as f:
            template_str = f.read()
    elif data:
        template_str = data
    elif mock_type == "log":
        template_str = _get_template(log_type, render)
    elif mock_type == "metrics":
        template_str = METRICS_TEMPLATE_RENDER
    else:
        console.print("[red]Use --data or --file to specify data to upload[/red]")
        return

    if not template_str:
        console.print("[red]No template data to generate[/red]")
        return

    batch_size = batch
    total_data_length = 0
    batch_count = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"[cyan]Generating to '{repo}'...", total=number)

        for i in range(0, number, batch_size):
            current_batch = min(batch_size, number - i)
            records = _gen_records(template_str, current_batch, render)
            data_str = "\n".join(json.dumps(r, ensure_ascii=False) for r in records) if records else ""
            total_data_length += len(data_str.encode("utf-8"))
            try:
                client.request("POST", "/api/v1/data", data=records, query_params={"repo": repo})
                batch_count += 1
            except Exception as e:
                console.print(f"[red]Batch {batch_count + 1} failed: {e}[/red]")
            progress.update(task, advance=current_batch)

    elapsed = time.time() - start
    speed = number / elapsed if elapsed > 0 else 0
    console.print(f"[green]Uploaded {number} records in {batch_count} batches to '{repo}'[/green]")
    console.print(f"Duration: {elapsed:.2f}s  Speed: {speed:.0f} records/s")


# ---------------------------------------------------------------------------
# Insert mode
# ---------------------------------------------------------------------------

def _run_insert(client, repo, data, file_path, batch_size, field, sourcetype, skip_empty):
    """Read raw data from --data, --file, or stdin and upload."""
    host_ip = "127.0.0.1"
    try:
        import subprocess
        host_ip = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5).stdout.strip().split()[0]
    except Exception:
        pass

    timestamp = int(time.time() * 1000)
    origin = file_path or ("stdin" if data is None else "inline")

    total_lines = None
    if data is not None:
        total_lines = len([l for l in data.splitlines() if not skip_empty or l.strip()])
    elif file_path is not None:
        try:
            with open(file_path) as f:
                total_lines = sum(1 for _ in f if not skip_empty or _.strip())
        except Exception:
            pass

    def _read():
        if data is not None:
            for line in data.splitlines():
                line = line.strip("\n\r")
                if skip_empty and not line:
                    continue
                yield line
        elif file_path is not None:
            with open(file_path, encoding="utf-8") as f:
                for line in f:
                    line = line.rstrip("\n\r")
                    if skip_empty and not line:
                        continue
                    yield line
        else:
            for line in sys.stdin:
                line = line.rstrip("\n\r")
                if skip_empty and not line:
                    continue
                yield line

    batch = []
    total_sent = 0
    total_failed = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(f"[cyan]Uploading to '{repo}'...", total=total_lines)

        for raw_line in _read():
            record = {
                field: raw_line,
                "timestamp": timestamp,
                "host": host_ip,
                "sourcetype": sourcetype,
                "origin": origin,
            }
            batch.append(record)
            if len(batch) >= batch_size:
                try:
                    _send(client, repo, batch)
                    total_sent += len(batch)
                except Exception as e:
                    total_failed += len(batch)
                    console.print(f"[red]Batch failed: {e}[/red]")
                progress.update(task, advance=len(batch))
                batch.clear()

        if batch:
            try:
                _send(client, repo, batch)
                total_sent += len(batch)
            except Exception as e:
                total_failed += len(batch)
                console.print(f"[red]Final batch failed: {e}[/red]")
            progress.update(task, advance=len(batch))

    if total_failed:
        console.print(f"[yellow]Uploaded {total_sent}/{total_sent + total_failed} records to '{repo}' ({total_failed} failed)[/yellow]")
    else:
        console.print(f"[green]Uploaded {total_sent} records to '{repo}'[/green]")


# ---------------------------------------------------------------------------
# mock command
# ---------------------------------------------------------------------------

@register_command("mock")
def register_mock(cli, ctx):
    """Register the top-level `mock` command."""

    @click.command("mock")
    @click.option("--repo", default="default", help="目标仓库名称", show_default=True)
    @click.option("--type", "mock_type", default=None,
                  type=click.Choice(["data", "log", "metrics"]),
                  help="数据类型 (data=通用, log=日志, metrics=指标)")
    @click.option("--data", type=str, help="JSON模板或内联文本数据（每行一条记录）")
    @click.option("-f", "--file", "file_path", type=click.Path(exists=True, readable=True, dir_okay=False),
                  help="从文件读取数据（每行一条记录）或JSON模板")
    @click.option("-n", "--number", type=int, default=1, help="生成记录数（仅生成模式）")
    @click.option("--batch", type=int, default=2000, help="每批记录数", show_default=True)
    @click.option("--gzip", is_flag=True, help="启用gzip压缩上传")
    @click.option("--render", is_flag=True, help="启用Jinja2模板渲染（支持faker变量）")
    @click.option("--log-type", default="nginx", help="日志类型",
                  type=click.Choice(LOG_TYPES), shell_complete=_log_type_completion)
    @click.option("--field", default="raw", help="插入模式下每行值对应的JSON字段名", show_default=True)
    @click.option("--sourcetype", default="default", help="插入模式下所有记录的sourcetype值", show_default=True)
    @click.option("--no-skip-empty", is_flag=True, help="插入模式下不过滤空行")
    def mock(repo, mock_type, data, file_path, number, batch, gzip, render, log_type,
             field, sourcetype, no_skip_empty):
        """Upload data to a repository.

        Two modes:

        \b
        Generate mode (--type): Generate fake data using built-in templates.
          ketaops-cli mock --type log --repo logs -n 100
          ketaops-cli mock --type data --data '{"key":"val"}' -n 100 --render

        Insert mode (--data/--file/stdin): Upload existing data as-is.
          ketaops-cli mock --repo logs --data 'line1\\nline2'
          ketaops-cli mock -f /var/log/syslog --repo logs
          echo 'error msg' | ketaops-cli mock --repo logs
        """
        import os as _os
        _cmd = _os.path.basename(sys.argv[0]) if sys.argv else "ketaops-cli"

        # Determine mode
        is_generate = mock_type is not None
        is_insert = (data is not None or file_path is not None or not sys.stdin.isatty())

        if not is_generate and not is_insert:
            console.print("[red]Error: specify data source or --type[/red]")
            console.print(f"[dim]Examples:[/dim]")
            console.print(f"  [dim]  {_cmd} mock --type log -n 100 --repo logs[/dim]")
            console.print(f"  [dim]  {_cmd} mock --data 'hello' --repo logs[/dim]")
            console.print(f"  [dim]  {_cmd} mock -f /var/log/syslog --repo logs[/dim]")
            console.print(f"  [dim]  echo 'error' | {_cmd} mock --repo logs[/dim]")
            return

        from cliyard.client.http import HttpClient
        from cliyard.client.auth import run_auth_chain
        from cliyard.client.credentials import get_service_credentials

        client = HttpClient(ctx.base_url)
        if ctx.auth_spec:
            run_auth_chain(ctx.auth_spec, http_client=client, pre_filled=ctx.pre_filled_auth)

        if not ctx.pre_filled_auth and ctx.auth_spec and ctx.auth_spec.get("persist"):
            saved = get_service_credentials(ctx.auth_spec.get("id", "ketaops"))
            token = saved.get("token") if saved else None
            if token:
                client.default_headers["Authorization"] = f"Bearer {token}"

        if is_generate:
            _run_generate(client, repo, mock_type, data, file_path, number, batch, gzip, render, log_type)
        else:
            _run_insert(client, repo, data, file_path, batch, field, sourcetype, not no_skip_empty)

    cli.add_command(mock)
