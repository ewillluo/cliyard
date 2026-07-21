"""CLI entry point. Edit this file to customize commands."""
import sys
from pathlib import Path
try:
    from importlib.metadata import version, PackageNotFoundError
    _VER = version("test_cli")
except PackageNotFoundError:
    _VER = "0.0.0"
from click.exceptions import UsageError
from cliyard.runtime import create_cli

_SPEC_DIR = Path(__file__).parent / "specs"


def main():
    try:
        cli = create_cli(str(_SPEC_DIR), version=_VER)
        sys.exit(cli(standalone_mode=False))
    except UsageError as e:
        sys.exit(e.format_message())
