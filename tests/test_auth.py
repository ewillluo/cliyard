"""Tests for the auth chain engine."""

import os
from unittest.mock import MagicMock

import pytest

from cliyard.client.auth import run_auth_chain
from cliyard.engine.errors import AuthError


# ---------------------------------------------------------------------------
# Mock HTTP client
# ---------------------------------------------------------------------------


class MockHttpClient:
    """Test double for an HTTP client with .request() and .default_headers."""

    def __init__(self):
        self.default_headers: dict[str, str] = {}
        self._response = MagicMock()

    def request(self, method, url, data=None, query_params=None):
        self._last_request = {
            "method": method,
            "url": url,
            "data": data,
            "query_params": query_params,
        }
        return self._response

    def set_json_response(self, body: dict):
        """Configure the mock to return a JSON body."""
        self._response.json.return_value = body


# ---------------------------------------------------------------------------
# env step
# ---------------------------------------------------------------------------


def test_env_step_reads_variable(monkeypatch):
    """env step reads from environment and stores in auth_state."""
    monkeypatch.setenv("MY_TOKEN", "abc123")

    auth_spec = {
        "steps": [
            {"name": "token", "type": "env", "config": {"name": "MY_TOKEN"}},
        ]
    }

    result = run_auth_chain(auth_spec)
    assert result == {"token": "abc123"}


def test_env_step_missing_variable_raises():
    """env step raises AuthError when environment variable is not set."""
    # Ensure variable is NOT set
    os.environ.pop("MISSING_VAR", None)

    auth_spec = {
        "steps": [
            {"name": "token", "type": "env", "config": {"name": "MISSING_VAR"}},
        ]
    }

    with pytest.raises(AuthError, match="MISSING_VAR"):
        run_auth_chain(auth_spec)


def test_env_step_missing_config_name():
    """env step raises AuthError when config.name is empty."""
    auth_spec = {
        "steps": [
            {"name": "token", "type": "env", "config": {}},
        ]
    }

    with pytest.raises(AuthError, match="config.name"):
        run_auth_chain(auth_spec)


def test_env_step_multiple_variables(monkeypatch):
    """Multiple env steps produce independent entries in auth_state."""
    monkeypatch.setenv("USERNAME", "admin")
    monkeypatch.setenv("PASSWORD", "secret")

    auth_spec = {
        "steps": [
            {"name": "user", "type": "env", "config": {"name": "USERNAME"}},
            {"name": "pass", "type": "env", "config": {"name": "PASSWORD"}},
        ]
    }

    result = run_auth_chain(auth_spec)
    assert result == {"user": "admin", "pass": "secret"}


# ---------------------------------------------------------------------------
# login step
# ---------------------------------------------------------------------------


def test_login_step_extracts_token_via_jsonpath():
    """login step sends request and extracts token using JSONPath."""
    client = MockHttpClient()
    client.set_json_response({"data": {"token": "jwt-token-123"}})

    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "method": "POST",
                    "endpoint": "https://api.example.com/auth",
                    "body": {"username": "admin", "password": "secret"},
                    "extract": {"token": "$.data.token"},
                },
            },
        ]
    }

    result = run_auth_chain(auth_spec, http_client=client)
    assert result == {"session": "jwt-token-123"}


def test_login_step_requires_http_client():
    """login step raises AuthError when no http_client is provided."""
    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "endpoint": "https://api.example.com/auth",
                    "extract": {"token": "$.token"},
                },
            },
        ]
    }

    with pytest.raises(AuthError, match="requires an http_client"):
        run_auth_chain(auth_spec)


def test_login_step_missing_endpoint():
    """login step raises AuthError when config.endpoint is empty."""
    client = MockHttpClient()
    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "extract": {"token": "$.token"},
                },
            },
        ]
    }

    with pytest.raises(AuthError, match="endpoint"):
        run_auth_chain(auth_spec, http_client=client)


def test_login_step_missing_extract():
    """login step raises AuthError when config.extract is empty."""
    client = MockHttpClient()
    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "endpoint": "https://api.example.com/auth",
                },
            },
        ]
    }

    with pytest.raises(AuthError, match="extract"):
        run_auth_chain(auth_spec, http_client=client)


def test_login_step_missing_token_path():
    """login step raises AuthError when config.extract.token is empty."""
    client = MockHttpClient()
    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "endpoint": "https://api.example.com/auth",
                    "extract": {},
                },
            },
        ]
    }

    with pytest.raises(AuthError, match="extract.token"):
        run_auth_chain(auth_spec, http_client=client)


def test_login_step_jsonpath_no_match():
    """login step raises AuthError when JSONPath does not match."""
    client = MockHttpClient()
    client.set_json_response({"other": "value"})

    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "endpoint": "https://api.example.com/auth",
                    "extract": {"token": "$.token"},
                },
            },
        ]
    }

    with pytest.raises(AuthError, match="did not match"):
        run_auth_chain(auth_spec, http_client=client)


def test_login_step_uses_default_method_post():
    """login step defaults to POST when method is not specified."""
    client = MockHttpClient()
    client.set_json_response({"token": "abc"})

    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "endpoint": "https://api.example.com/auth",
                    "extract": {"token": "$.token"},
                },
            },
        ]
    }

    run_auth_chain(auth_spec, http_client=client)
    assert client._last_request["method"] == "POST"


def test_login_step_json_parse_error():
    """login step wraps JSON parse errors as AuthError."""
    client = MockHttpClient()
    client._response.json.side_effect = ValueError("not JSON")

    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "endpoint": "https://api.example.com/auth",
                    "extract": {"token": "$.token"},
                },
            },
        ]
    }

    with pytest.raises(AuthError, match="failed to parse"):
        run_auth_chain(auth_spec, http_client=client)


def test_login_step_passes_body_and_query():
    """login step forwards body and query params to the HTTP client."""
    client = MockHttpClient()
    client.set_json_response({"token": "abc"})

    auth_spec = {
        "steps": [
            {
                "name": "session",
                "type": "login",
                "config": {
                    "method": "GET",
                    "endpoint": "https://api.example.com/auth",
                    "body": {"key": "val"},
                    "query": {"lang": "en"},
                    "extract": {"token": "$.token"},
                },
            },
        ]
    }

    run_auth_chain(auth_spec, http_client=client)
    assert client._last_request["data"] == {"key": "val"}
    assert client._last_request["query_params"] == {"lang": "en"}


def test_login_step_extracts_nested_jsonpath():
    """login step extracts deeply nested values via JSONPath."""
    client = MockHttpClient()
    client.set_json_response(
        {"result": {"auth": {"access_token": "deep-token-456"}}}
    )

    auth_spec = {
        "steps": [
            {
                "name": "token",
                "type": "login",
                "config": {
                    "endpoint": "https://api.example.com/login",
                    "extract": {"token": "$.result.auth.access_token"},
                },
            },
        ]
    }

    result = run_auth_chain(auth_spec, http_client=client)
    assert result == {"token": "deep-token-456"}


# ---------------------------------------------------------------------------
# inject step
# ---------------------------------------------------------------------------


def test_inject_step_adds_to_default_headers():
    """inject step sets a header on the HTTP client from previous step."""
    client = MockHttpClient()

    auth_spec = {
        "steps": [
            {"name": "token", "type": "env", "config": {"name": "MY_TOKEN"}},
            {
                "name": "token",
                "type": "inject",
                "config": {
                    "into": "header",
                    "name": "Authorization",
                    "prefix": "Bearer ",
                },
            },
        ]
    }

    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("MY_TOKEN", "jwt-abc")
        run_auth_chain(auth_spec, http_client=client)

    assert client.default_headers["Authorization"] == "Bearer jwt-abc"


def test_inject_step_without_prefix():
    """inject step works without a prefix."""
    client = MockHttpClient()

    auth_spec = {
        "steps": [
            {"name": "api_key", "type": "env", "config": {"name": "MY_KEY"}},
            {
                "name": "api_key",
                "type": "inject",
                "config": {
                    "into": "header",
                    "name": "X-API-Key",
                },
            },
        ]
    }

    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("MY_KEY", "key123")
        run_auth_chain(auth_spec, http_client=client)

    assert client.default_headers["X-API-Key"] == "key123"


def test_inject_step_requires_http_client():
    """inject step raises AuthError when no http_client is provided."""
    auth_spec = {
        "steps": [
            {"name": "token", "type": "env", "config": {"name": "MY_TOKEN"}},
            {
                "name": "token",
                "type": "inject",
                "config": {"into": "header", "name": "X-Token"},
            },
        ]
    }

    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("MY_TOKEN", "abc")
        with pytest.raises(AuthError, match="requires an http_client"):
            run_auth_chain(auth_spec)


def test_inject_step_missing_config_name():
    """inject step raises AuthError when config.name is empty."""
    client = MockHttpClient()
    auth_spec = {
        "steps": [
            {"name": "token", "type": "env", "config": {"name": "MY_TOKEN"}},
            {
                "name": "token",
                "type": "inject",
                "config": {"into": "header"},
            },
        ]
    }

    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("MY_TOKEN", "abc")
        with pytest.raises(AuthError, match="config.name"):
            run_auth_chain(auth_spec, http_client=client)


def test_inject_step_missing_default_headers():
    """inject step raises AuthError when http_client lacks default_headers."""
    class BadClient:
        def request(self, **kwargs):
            pass

    client = BadClient()
    auth_spec = {
        "steps": [
            {"name": "token", "type": "env", "config": {"name": "MY_TOKEN"}},
            {
                "name": "token",
                "type": "inject",
                "config": {"into": "header", "name": "X-Token"},
            },
        ]
    }

    with pytest.MonkeyPatch().context() as mp:
        mp.setenv("MY_TOKEN", "abc")
        with pytest.raises(AuthError, match="default_headers"):
            run_auth_chain(auth_spec, http_client=client)


# ---------------------------------------------------------------------------
# Full chain: env → login → inject
# ---------------------------------------------------------------------------


def test_full_chain_env_login_inject(monkeypatch):
    """Complete auth flow: env var → login → inject header."""
    monkeypatch.setenv("PASSWORD", "secret")

    client = MockHttpClient()
    client.set_json_response({"auth_token": "jwt-final-token"})

    auth_spec = {
        "steps": [
            {
                "name": "password",
                "type": "env",
                "config": {"name": "PASSWORD"},
            },
            {
                "name": "session",
                "type": "login",
                "config": {
                    "endpoint": "https://api.example.com/auth",
                    "body": {"password": "{{ password }}"},
                    "extract": {"token": "$.auth_token"},
                },
            },
            {
                "name": "session",
                "type": "inject",
                "config": {
                    "into": "header",
                    "name": "Authorization",
                    "prefix": "Bearer ",
                },
            },
        ]
    }

    result = run_auth_chain(auth_spec, http_client=client)
    assert result == {"password": "secret", "session": "jwt-final-token"}
    assert client.default_headers["Authorization"] == "Bearer jwt-final-token"


# ---------------------------------------------------------------------------
# Unknown step type
# ---------------------------------------------------------------------------


def test_unknown_step_type_raises():
    """Unknown step type raises AuthError."""
    auth_spec = {
        "steps": [
            {"name": "x", "type": "magic", "config": {}},
        ]
    }

    with pytest.raises(AuthError, match="magic"):
        run_auth_chain(auth_spec)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_steps_returns_empty_dict():
    """run_auth_chain with no steps returns an empty dict."""
    result = run_auth_chain({"steps": []})
    assert result == {}


def test_auth_spec_without_steps_key():
    """run_auth_chain with no steps key returns an empty dict."""
    result = run_auth_chain({})
    assert result == {}
