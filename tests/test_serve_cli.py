"""Tests for the ``cliyard serve`` command skeleton.

Covers command registration in ``cliyard --help``, argument/option
surface in ``serve --help``, and error handling for a missing or
nonexistent ``<spec-dir>``.
"""

from __future__ import annotations

import click.testing

from cliyard.cli.__main__ import cli


def _runner() -> click.testing.CliRunner:
    return click.testing.CliRunner()


def test_cli_help_lists_serve_command():
    """``cliyard --help`` should list the serve command."""
    result = _runner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "serve" in result.output


def test_serve_help_shows_all_options():
    """``serve --help`` should show spec-dir argument and all options."""
    result = _runner().invoke(cli, ["serve", "--help"])
    assert result.exit_code == 0
    assert "SPEC_DIR" in result.output
    assert "--host" in result.output
    assert "--port" in result.output
    assert "--open" in result.output
    assert "--reload" in result.output


def test_serve_missing_spec_dir_fails():
    """``cliyard serve`` without spec-dir should report MissingParameter."""
    result = _runner().invoke(cli, ["serve"])
    assert result.exit_code != 0
    assert "SPEC_DIR" in result.output


def test_serve_nonexistent_spec_dir_fails():
    """``cliyard serve /nonexistent`` should exit non-zero."""
    result = _runner().invoke(cli, ["serve", "/nonexistent/spec-dir"])
    assert result.exit_code != 0
    assert "does not exist" in result.output


def test_serve_existing_dir_prints_startup_params(tmp_path):
    """``serve <existing-dir>`` prints the placeholder startup line."""
    result = _runner().invoke(
        cli,
        ["serve", str(tmp_path), "--host", "0.0.0.0", "--port", "9000"],
    )
    assert result.exit_code == 0
    assert "Serve spec" in result.output
    assert "0.0.0.0" in result.output
    assert "9000" in result.output
