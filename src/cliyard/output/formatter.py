"""Output formatters — JSON and Rich table rendering."""

from __future__ import annotations

import io
import csv
import io
import json
from typing import Any


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

def format_as_json(data: dict | list | Any, *, indent: int = 2) -> str:
    """Serialise *data* as a human-readable JSON string.

    Args:
        data: Any JSON-serialisable object (dict, list, or scalar).
        indent: Number of spaces for indentation (default 2).

    Returns:
        Formatted JSON string with ``ensure_ascii=False`` so CJK characters
        render directly.
    """
    return json.dumps(data, indent=indent, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Rich table formatter
# ---------------------------------------------------------------------------

def format_as_table(data: dict, fields: list[dict] | None = None) -> str:
    """Render *data* as a Rich table.

    Args:
        data: Result dict from :func:`parse_response`
            (``{"items": [...], "total": N, "fields": [...]}``).
        fields: Optional override list of field definitions.
            Each entry: ``{"name": "column_key", "alias": "Display Name"}``.
            If *None*, falls back to ``data["fields"]``.
            If both are empty, all keys from the first item are used.

    Returns:
        A string containing the rendered table (including ANSI codes for
        terminal display).
    """
    from rich.console import Console
    from rich.table import Table

    items: list[dict] = data.get("items", [])
    if fields is None:
        fields = data.get("fields", [])

    # Auto-detect fields from first item when none are provided.
    if not fields and items:
        fields = [{"name": k, "alias": k} for k in items[0]]

    table = Table(show_lines=False, expand=False)

    for field in fields:
        table.add_column(field.get("alias") or field["name"])

    for item in items:
        row = [str(item.get(f["name"], "")) for f in fields]
        table.add_row(*row)

    buf = io.StringIO()
    console = Console(file=buf, width=120, force_terminal=False)
    console.print(table)
    return buf.getvalue()


def format_as_csv(data: dict, fields: list[dict]) -> str:
    """Format data as CSV string.

    Args:
        data: Response dict with ``items`` key containing a list of records.
        fields: Field definitions with ``name`` and ``alias`` keys.

    Returns:
        CSV string with header row and data rows.
    """
    items = data.get("items", [])
    if not items:
        return ""

    field_names = [f.get("alias", f["name"]) for f in fields] if fields else list(items[0].keys())
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(field_names)
    for item in items:
        row = [str(item.get(f["name"], "")) for f in fields] if fields else [str(item.get(k, "")) for k in items[0].keys()]
        writer.writerow(row)
    return output.getvalue()
