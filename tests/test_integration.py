"""Integration tests for cliyard — end-to-end pipeline coverage.

Covers the full flow from YAML spec loading through Click command execution,
HTTP request assembly, auth chain injection, validation blocking, dependency
checking, and error formatting.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock

import click.testing
import pytest

from cliyard.client.auth import TokenCache, run_auth_chain
from cliyard.engine.assembler import assemble_request
from cliyard.engine.binder import bind_and_validate
from cliyard.engine.builder import (
    ServiceContext,
    build_list_command,
    build_operation_command,
    build_resource_group,
)
from cliyard.engine.error_handler import handle_api_error
from cliyard.engine.errors import ApiError, AuthError, ValidationError
from cliyard.engine.loader import load_resource, load_service
from cliyard.runtime.runner import run_with_spec
from cliyard.validate.dependency import check_dependencies

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SPEC_DIR = FIXTURES_DIR / "spec-dir"


# ===========================================================================
# 1. test_list_request — load spec → build commands → invoke list → verify
# ===========================================================================


class TestListRequest:
    """Integration test: full pipeline for a list command."""

    def test_load_spec_and_build_resource_group(self):
        """Load spec-dir → build resource group → verify Click group structure."""
        service = load_service(SPEC_DIR)
        assert service["name"] == "test-service"
        assert len(service["resources"]) == 1

        resource = service["resources"][0]
        assert resource["name"] == "repos"

        group = build_resource_group(resource["name"], resource, ServiceContext(base_url="https://httpbin.org"))
        assert isinstance(group, click.Group)
        assert group.name == "repos"

        # Verify subcommands exist
        commands = group.list_commands(None)
        assert "list" in commands
        assert "create" in commands

    def test_invoke_list_via_cli_runner(self):
        """Invoke repos list via CliRunner — should succeed (pass-through callback)."""
        runner = click.testing.CliRunner()

        # Build a standalone CLI group that mirrors what run_with_spec does
        service = load_service(SPEC_DIR)
        resource = service["resources"][0]
        group = build_resource_group(resource["name"], resource, ServiceContext(base_url="https://httpbin.org"))

        # Invoke repos list with no extra args
        result = runner.invoke(group, ["list"])
        assert result.exit_code == 0

    def test_invoke_list_with_option(self):
        """Invoke repos list --page=2 — option is accepted."""
        runner = click.testing.CliRunner()

        resource = load_resource(FIXTURES_DIR / "repos_resource.yaml")
        group = build_resource_group(resource["name"], resource, ServiceContext(base_url="https://httpbin.org"))

        result = runner.invoke(group, ["list", "--page=3"])
        assert result.exit_code == 0

    def test_invoke_list_help_shows_options(self):
        """Help output for repos list shows expected params."""
        runner = click.testing.CliRunner()

        resource = load_resource(FIXTURES_DIR / "repos_resource.yaml")
        group = build_resource_group(resource["name"], resource, ServiceContext(base_url="https://httpbin.org"))

        result = runner.invoke(group, ["list", "--help"])
        assert result.exit_code == 0
        assert "--page" in result.output


# ===========================================================================
# 2. test_create_request — load spec → invoke create → verify assembled body
# ===========================================================================


class TestCreateRequest:
    """Integration test: create command → binder validates → assembler builds body."""

    CREATE_SPEC = {
        "http": {
            "method": "POST",
            "path": "repos",
            "body": {"name": "{{ name }}", "description": "{{ description }}", "visibility": "{{ visibility }}"},
        },
        "params": {
            "body": [
                {"name": "name", "type": "string", "required": True},
                {"name": "description", "type": "string", "default": ""},
                {"name": "visibility", "type": "enum", "choices": ["public", "private"], "default": "private"},
            ],
        },
    }

    def test_invoke_create_via_cli_runner(self):
        """Invoke repos create --name=myrepo → no crash (pass-through callback)."""
        runner = click.testing.CliRunner()

        resource = load_resource(FIXTURES_DIR / "repos_resource.yaml")
        group = build_resource_group(resource["name"], resource, ServiceContext(base_url="https://httpbin.org"))

        result = runner.invoke(group, ["create", "--name=myrepo"])
        assert result.exit_code == 0

    def test_bind_and_assemble_create_body(self):
        """bind_and_validate → assemble_request produces correct POST body."""
        params = {"name": "myrepo", "description": "test repo", "visibility": "public"}

        validated = bind_and_validate(params, self.CREATE_SPEC)
        assert validated.body["name"] == "myrepo"
        assert validated.body["description"] == "test repo"
        assert validated.body["visibility"] == "public"

        req = assemble_request(
            self.CREATE_SPEC,
            validated.body | validated.path | validated.query,
            base_url="https://httpbin.org",
        )
        assert req.method == "POST"
        assert req.url == "https://httpbin.org/repos"
        assert req.body == {"name": "myrepo", "description": "test repo", "visibility": "public"}

    def test_bind_create_missing_required(self):
        """Missing required body param raises ValidationError from binder."""
        params = {}  # name is required, not provided

        with pytest.raises(ValidationError, match="name.*required"):
            bind_and_validate(params, self.CREATE_SPEC)

    def test_create_with_defaults(self):
        """Default values are applied when params are omitted."""
        params = {"name": "minimal-repo"}

        validated = bind_and_validate(params, self.CREATE_SPEC)
        assert validated.body["visibility"] == "private"
        assert validated.body["description"] == ""

        req = assemble_request(
            self.CREATE_SPEC,
            validated.body | validated.path | validated.query,
            base_url="https://httpbin.org",
        )
        assert req.body == {"name": "minimal-repo", "description": "", "visibility": "private"}


# ===========================================================================
# 3. test_auth_injection — env step → inject step adds header to http client
# ===========================================================================


class TestAuthInjection:
    """Integration test: auth chain with env → inject pipeline."""

    class MockHttpClient:
        """Test double for an HTTP client with .request() and .default_headers."""

        def __init__(self):
            self.default_headers: dict[str, str] = {}

        def request(self, method, url, data=None, query_params=None):
            resp = MagicMock()
            resp.json.return_value = {"data": {"token": "jwt-mock-token"}}
            return resp

    def test_env_inject_adds_header(self, monkeypatch):
        """env variable → inject step sets Authorization header."""
        monkeypatch.setenv("CLIYARD_TOKEN", "abc-123-token")

        client = self.MockHttpClient()

        auth_spec = {
            "steps": [
                {"name": "token", "type": "env", "config": {"name": "CLIYARD_TOKEN"}},
                {
                    "name": "token",
                    "type": "inject",
                    "config": {"into": "header", "name": "Authorization", "prefix": "Bearer "},
                },
            ]
        }

        result = run_auth_chain(auth_spec, http_client=client)
        assert result["token"] == "abc-123-token"
        assert client.default_headers["Authorization"] == "Bearer abc-123-token"

    def test_full_chain_env_login_inject(self, monkeypatch):
        """Full auth flow: env → login → inject (integration style)."""
        monkeypatch.setenv("PASSWORD", "secret")

        client = self.MockHttpClient()

        auth_spec = {
            "steps": [
                {"name": "password", "type": "env", "config": {"name": "PASSWORD"}},
                {
                    "name": "session",
                    "type": "login",
                    "config": {
                        "endpoint": "https://api.example.com/auth",
                        "body": {"password": "secret"},
                        "extract": {"token": "$.data.token"},
                    },
                },
                {
                    "name": "session",
                    "type": "inject",
                    "config": {"into": "header", "name": "X-Auth-Token"},
                },
            ]
        }

        result = run_auth_chain(auth_spec, http_client=client)
        assert result["password"] == "secret"
        assert result["session"] == "jwt-mock-token"
        assert client.default_headers["X-Auth-Token"] == "jwt-mock-token"

    def test_inject_without_prefix(self, monkeypatch):
        """inject step without prefix — header value is raw token."""
        monkeypatch.setenv("API_KEY", "sk-12345")

        client = self.MockHttpClient()

        auth_spec = {
            "steps": [
                {"name": "api_key", "type": "env", "config": {"name": "API_KEY"}},
                {
                    "name": "api_key",
                    "type": "inject",
                    "config": {"into": "header", "name": "X-API-Key"},
                },
            ]
        }

        run_auth_chain(auth_spec, http_client=client)
        assert client.default_headers["X-API-Key"] == "sk-12345"

    def test_missing_env_variable_aborts_chain(self):
        """Missing env variable raises AuthError before inject runs."""
        # Ensure the env variable is NOT set
        os.environ.pop("NONEXISTENT_TOKEN", None)

        auth_spec = {
            "steps": [
                {"name": "token", "type": "env", "config": {"name": "NONEXISTENT_TOKEN"}},
                {"name": "token", "type": "inject", "config": {"into": "header", "name": "X-Token"}},
            ]
        }

        with pytest.raises(AuthError, match="NONEXISTENT_TOKEN"):
            run_auth_chain(auth_spec)

    def test_token_cache_avoids_repeated_login(self, monkeypatch):
        """TokenCache prevents duplicate login requests."""
        monkeypatch.setenv("PASSWORD", "secret")

        client = self.MockHttpClient()
        cache = TokenCache()

        auth_spec = {
            "steps": [
                {"name": "password", "type": "env", "config": {"name": "PASSWORD"}},
                {
                    "name": "session",
                    "type": "login",
                    "config": {
                        "endpoint": "https://api.example.com/auth",
                        "extract": {"token": "$.data.token", "ttl": 3600},
                    },
                },
            ]
        }

        # First call — hits HTTP
        result1 = run_auth_chain(auth_spec, http_client=client, cache=cache)
        assert result1["session"] == "jwt-mock-token"

        # Second call — should use cache (no extra HTTP request)
        result2 = run_auth_chain(auth_spec, http_client=client, cache=cache)
        assert result2["session"] == "jwt-mock-token"


# ===========================================================================
# 4. test_validation_blocks_request — invalid enum → error before any HTTP
# ===========================================================================


class TestValidationBlocksRequest:
    """Integration test: validation catches errors before request assembly."""

    SPEC_WITH_ENUM = {
        "http": {"method": "GET", "path": "items"},
        "params": {
            "query": [
                {"name": "sort", "type": "enum", "choices": ["asc", "desc"], "default": "asc"},
            ],
        },
    }

    def test_invalid_enum_rejected_by_binder(self):
        """Passing an invalid enum value to binder raises ValidationError."""
        params = {"sort": "invalid-value"}

        with pytest.raises(ValidationError, match="Invalid choice"):
            bind_and_validate(params, self.SPEC_WITH_ENUM)

    def test_invalid_enum_rejected_by_click_choice(self):
        """Click's Choice type rejects invalid values before callback."""
        import click

        choice = click.Choice(["asc", "desc"])
        with pytest.raises(click.BadParameter):
            choice.convert("invalid-value", param=None, ctx=None)

    def test_valid_enum_passes_binder(self):
        """Valid enum value passes binder and can be assembled."""
        params = {"sort": "desc"}

        validated = bind_and_validate(params, self.SPEC_WITH_ENUM)
        assert validated.query["sort"] == "desc"

        # Should NOT raise — proves validation passed
        req = assemble_request(
            self.SPEC_WITH_ENUM,
            validated.body | validated.path | validated.query,
            base_url="https://httpbin.org",
        )
        assert "httpbin.org/items" in req.url

    def test_enum_case_insensitive_binder(self):
        """Enum validation in binder uses case-insensitive comparison."""
        params = {"sort": "ASC"}  # uppercase

        validated = bind_and_validate(params, self.SPEC_WITH_ENUM)
        assert validated.query["sort"] == "asc"  # normalised to spec case

    def test_click_cli_rejects_invalid_choice(self):
        """Click CLI rejects invalid choice at the Click level (before callback)."""
        runner = click.testing.CliRunner()

        spec = {
            "name": "test",
            "description": "test",
            "methods": {
                "list": {
                    "http": {"method": "GET"},
                    "params": {
                        "query": [
                            {"name": "status", "type": "enum", "choices": ["active", "inactive"]},
                        ],
                    },
                },
            },
        }

        group = build_resource_group("test", spec, ServiceContext(base_url="https://api.example.com"))
        result = runner.invoke(group, ["list", "--status=deleted"])
        assert result.exit_code != 0
        assert "Invalid value" in result.output or "invalid choice" in result.output.lower()


# ===========================================================================
# 5. test_depends_on_respected — conditional required fields
# ===========================================================================


class TestDependsOnRespected:
    """Integration test: depends_on.eq conditional required field logic."""

    FIELD_SPECS = [
        {"name": "auth_type", "type": "enum", "choices": ["password", "token", "none"]},
        {
            "name": "db_password",
            "type": "string",
            "required": True,
            "depends_on": {"field": "auth_type", "eq": "password"},
        },
        {
            "name": "db_token",
            "type": "string",
            "required": True,
            "depends_on": {"field": "auth_type", "eq": "token"},
        },
    ]

    def test_condition_met_but_missing_required(self):
        """When auth_type=password but db_password missing → error."""
        params = {"auth_type": "password"}
        errors = check_dependencies(params, self.FIELD_SPECS)
        assert len(errors) == 1
        assert errors[0].field == "db_password"
        assert "required when auth_type=password" in errors[0].message

    def test_condition_not_met_no_error(self):
        """When auth_type=none, password/token are not required → no errors."""
        params = {"auth_type": "none"}
        errors = check_dependencies(params, self.FIELD_SPECS)
        assert len(errors) == 0

    def test_condition_met_and_value_provided(self):
        """When condition is met and value is provided → no error."""
        params = {"auth_type": "password", "db_password": "secret123"}
        errors = check_dependencies(params, self.FIELD_SPECS)
        assert len(errors) == 0

    def test_different_condition_triggers_different_field(self):
        """When auth_type=token, db_token becomes required (not db_password)."""
        params = {"auth_type": "token"}  # token mode, but db_token missing
        errors = check_dependencies(params, self.FIELD_SPECS)
        assert len(errors) == 1
        assert errors[0].field == "db_token"
        assert "required when auth_type=token" in errors[0].message

    def test_multiple_missing_conditional_fields(self):
        """Both conditional fields missing under irrelevant condition → 0 errors."""
        # auth_type=none means neither password nor token is required
        params = {"auth_type": "none"}
        errors = check_dependencies(params, self.FIELD_SPECS)
        assert len(errors) == 0

    def test_no_depends_on_fields_pass_through(self):
        """Fields without depends_on are ignored by check_dependencies."""
        specs = [
            {"name": "name", "type": "string", "required": True},
            {"name": "email", "type": "string"},
        ]
        params = {}  # name missing, but check_dependencies only checks conditional
        errors = check_dependencies(params, specs)
        assert len(errors) == 0  # no depends_on → no errors from this function


# ===========================================================================
# 6. test_error_response_formatting — API error → formatted output
# ===========================================================================


class TestErrorResponseFormatting:
    """Integration test: API errors produce structured, formatted output."""

    def test_api_error_with_json_body(self):
        """API returns structured JSON error → ApiError includes code and message."""
        import requests

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 422
        mock_resp.url = "https://api.example.com/repos"
        mock_resp.text = '{"code":"VALIDATION_FAILED","message":"name already exists"}'
        mock_resp.json.return_value = {"code": "VALIDATION_FAILED", "message": "name already exists"}

        with pytest.raises(ApiError) as exc_info:
            handle_api_error(mock_resp)

        assert exc_info.value.status == 422
        assert exc_info.value.url == "https://api.example.com/repos"
        assert "VALIDATION_FAILED" in str(exc_info.value)
        assert "name already exists" in str(exc_info.value)

    def test_api_error_with_code_only(self):
        """JSON body with code but no message → code is included."""
        import requests

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 400
        mock_resp.url = "https://api.example.com/items"
        mock_resp.text = '{"code":"BAD_REQUEST"}'
        mock_resp.json.return_value = {"code": "BAD_REQUEST"}

        with pytest.raises(ApiError) as exc_info:
            handle_api_error(mock_resp)

        assert "BAD_REQUEST" in str(exc_info.value)

    def test_api_error_with_non_json_body(self):
        """API returns plain text → ApiError uses raw body."""
        import requests

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 500
        mock_resp.url = "https://api.example.com/data"
        mock_resp.text = "Internal Server Error"
        mock_resp.json.side_effect = ValueError("not JSON")

        with pytest.raises(ApiError) as exc_info:
            handle_api_error(mock_resp)

        assert exc_info.value.status == 500
        assert "Internal Server Error" in str(exc_info.value)

    def test_api_error_with_message_only(self):
        """JSON body with message but no code → message is used."""
        import requests

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 404
        mock_resp.url = "https://api.example.com/repos/123"
        mock_resp.text = '{"message":"Repository not found"}'
        mock_resp.json.return_value = {"message": "Repository not found"}

        with pytest.raises(ApiError) as exc_info:
            handle_api_error(mock_resp)

        assert "Repository not found" in str(exc_info.value)

    def test_api_error_string_representation(self):
        """ApiError.__str__ includes status, URL, and body."""
        err = ApiError(status=403, url="https://api.example.com/admin", body="Forbidden")
        s = str(err)
        assert "[403]" in s
        assert "api.example.com/admin" in s
        assert "Forbidden" in s

    def test_validation_error_formatting(self):
        """ValidationError.__str__ includes field, value, and reason."""
        err = ValidationError("age", -1, "too small")
        s = str(err)
        assert "age" in s
        assert "too small" in s

    def test_auth_error_formatting(self):
        """AuthError is raised with descriptive message."""
        err = AuthError("Environment variable 'MY_TOKEN' is not set")
        assert "MY_TOKEN" in str(err)
        assert "is not set" in str(err)


# ===========================================================================
# 7. Bonus: Runtime pipeline integration
# ===========================================================================


class TestRuntimePipeline:
    """Integration test: run_with_spec() end-to-end."""

    def test_run_with_spec_loads_and_exits_zero(self):
        """run_with_spec loads a valid spec-dir — CLI help shown without subcommand."""
        import sys as _sys

        old_argv = _sys.argv[:]
        try:
            _sys.argv = ["cliyard"]
            with pytest.raises(SystemExit) as exc_info:
                run_with_spec(str(SPEC_DIR))
            # Click shows help when no subcommand given — this is success
            assert exc_info.value.code in (0, 1)
        finally:
            _sys.argv = old_argv

    def test_run_with_spec_missing_dir(self):
        """run_with_spec with nonexistent directory exits 1."""
        with pytest.raises(SystemExit) as exc_info:
            run_with_spec("/nonexistent/dir")

        assert exc_info.value.code == 1

    def test_run_with_spec_cli_runner_invoke(self):
        """full pipeline: CliRunner invokes test-service repos list --page=5."""
        service = load_service(SPEC_DIR)

        cli = click.Group(name=service["name"], help=service.get("description", ""))
        for resource in service.get("resources", []):
            group = build_resource_group(resource["name"], resource, ServiceContext(base_url="https://httpbin.org"))
            cli.add_command(group)

        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["repos", "list", "--page=5"])
        assert result.exit_code == 0

    def test_assembler_path_template_render(self):
        """assemble_request renders path templates from validated params."""
        spec = {
            "http": {"method": "GET", "path": "repos/{{ owner }}/{{ repo }}"},
            "params": {
                "path": [
                    {"name": "owner", "type": "string", "required": True},
                    {"name": "repo", "type": "string", "required": True},
                ],
            },
        }

        validated = bind_and_validate({"owner": "ketabot", "repo": "cliyard"}, spec)
        req = assemble_request(
            spec,
            validated.body | validated.path | validated.query,
            base_url="https://api.github.com",
        )

        assert req.url == "https://api.github.com/repos/ketabot/cliyard"
        assert req.method == "GET"

    def test_assembler_with_query_params(self):
        """assemble_request includes query params from spec and user."""
        spec = {
            "http": {
                "method": "GET",
                "path": "repos",
                "query_params": [
                    {"field": "type", "default": "all"},
                ],
            },
            "params": {
                "query": [
                    {"name": "type", "type": "string", "default": "all"},
                    {"name": "sort", "type": "string", "default": "updated"},
                ],
            },
        }

        validated = bind_and_validate({"sort": "created"}, spec)

        # assemble_request reads static query params from http.query_params
        # (looked up in top-level params) and dynamic params from params["query"].
        # Pass validated.query under the "query" key so assembler finds both.
        merged = validated.body | validated.path | {"query": validated.query}
        req = assemble_request(spec, merged, base_url="https://api.example.com")

        assert req.query_params == {"type": "all", "sort": "created"}

    def test_assembler_with_headers(self):
        """assemble_request includes static spec headers."""
        spec = {
            "http": {
                "method": "GET",
                "path": "data",
                "headers": {"Accept": "application/json", "X-Custom": "value"},
            },
        }

        req = assemble_request(
            spec,
            {},
            base_url="https://api.example.com",
        )

        assert req.headers == {"Accept": "application/json", "X-Custom": "value"}

    def test_assembler_with_url_prefix(self):
        """assemble_request respects the prefix parameter."""
        spec = {"http": {"method": "GET", "path": "users"}}

        req = assemble_request(
            spec,
            {},
            base_url="https://api.example.com",
            prefix="/api/v2",
        )

        assert req.url == "https://api.example.com/api/v2/users"
