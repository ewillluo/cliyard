"""Tests for service-scoped credentials isolation.

Each cliyard-based CLI must only see its own profiles/current pointer,
so multi-CLI machines don't leak tokens or cross-contaminate base_url.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import click.testing
import pytest
import yaml

from cliyard.client.credentials import (
    clear_service_credentials,
    delete_profile,
    get_current_profile,
    get_profile,
    get_service_credentials,
    list_profiles,
    list_services,
    save_profile,
    save_service_credentials,
    switch_profile,
)

FIXTURES_DIR = "tests/fixtures/spec-dir"


@pytest.fixture(autouse=True)
def _isolate(tmp_path, monkeypatch):
    """Point credentials storage at a temp dir per test."""
    monkeypatch.setattr("cliyard.client.credentials.CLIYARD_DIR", str(tmp_path))
    monkeypatch.setattr(
        "cliyard.client.credentials.CREDENTIALS_PATH",
        str(tmp_path / "credentials.yaml"),
    )
    yield


# ---------------------------------------------------------------------------
# Service-scoped profile CRUD
# ---------------------------------------------------------------------------


class TestServiceIsolation:
    def test_profiles_isolated_per_service(self):
        save_profile("prod", {"endpoint": "https://j.example.com", "token": "J"}, service="jcli")
        save_profile("prod", {"endpoint": "https://k.example.com", "token": "K"}, service="ketacli")

        assert get_current_profile(service="jcli")["endpoint"] == "https://j.example.com"
        assert get_current_profile(service="ketacli")["endpoint"] == "https://k.example.com"

        j_profiles = list_profiles("jcli")
        assert j_profiles == {"prod": {"endpoint": "https://j.example.com", "token": "J"}}
        assert "ketacli" not in list_services()["jcli"]
        assert get_profile("prod", service="ketacli")["token"] == "K"
        assert get_profile("prod", service="jcli")["token"] == "J"

    def test_default_service_namespace(self):
        save_profile("dev", {"token": "T"})
        assert get_profile("dev") == {"token": "T"}
        assert get_profile("dev", service="other") is None

    def test_switch_and_delete_scoped(self):
        save_profile("a", {"token": "A"}, service="s1")
        save_profile("b", {"token": "B"}, service="s1")
        save_profile("a", {"token": "X"}, service="s2")

        assert switch_profile("a", service="s1") is True
        assert get_current_profile(service="s1")["_name"] == "a"

        delete_profile("a", service="s2")
        assert "a" in list_profiles("s1")
        assert "a" not in list_profiles("s2")
        assert get_current_profile(service="s2") is None

    def test_service_credentials_helpers_scoped(self):
        save_service_credentials("jcli", {"token": "JT"})
        save_service_credentials("ketacli", {"token": "KT"})
        assert get_service_credentials("jcli") == {"token": "JT"}
        assert get_service_credentials("ketacli") == {"token": "KT"}

    def test_clear_service_scoped(self):
        save_service_credentials("s1", {"token": "1"})
        save_service_credentials("s2", {"token": "2"})
        clear_service_credentials("s1")
        assert get_service_credentials("s1") is None
        assert get_service_credentials("s2") == {"token": "2"}
        assert set(list_services()) == {"s2"}


# ---------------------------------------------------------------------------
# No-arg backward compat (pre-migration single-global-current semantics)
# ---------------------------------------------------------------------------


class TestNoArgBackwardCompat:
    def test_noarg_current_profile_returns_selected(self):
        save_profile("gpt-new2", {"endpoint": "https://k.example.com", "token": "K"}, service="ketaops")
        save_profile("jenkins", {"endpoint": "https://j.example.com", "token": "J"}, service="jcli", set_current=False)

        cur = get_current_profile()
        assert cur is not None
        assert cur["_name"] == "gpt-new2"
        assert cur["endpoint"] == "https://k.example.com"

    def test_noarg_current_profile_prefers_default(self):
        save_profile("a", {"token": "A"}, service="default")
        save_profile("b", {"token": "B"}, service="other")
        assert get_current_profile()["_name"] == "a"

    def test_noarg_current_none_when_no_current_anywhere(self):
        save_profile("x", {"token": "X"}, service="s1", set_current=False)
        save_profile("y", {"token": "Y"}, service="s2", set_current=False)
        assert get_current_profile() is None

    def test_noarg_list_profiles_single_service(self):
        save_profile("prod", {"token": "P"}, service="ketaops")
        assert list_profiles() == {"prod": {"token": "P"}}
        assert get_profile("prod") == {"token": "P"}


# ---------------------------------------------------------------------------
# Legacy flat-format compatibility
# ---------------------------------------------------------------------------


class TestLegacyCompatibility:
    def test_legacy_file_readable_as_requesting_service(self, tmp_path):
        legacy = {
            "profiles": {"prod": {"endpoint": "https://old.example.com", "token": "T"}},
            "current": "prod",
        }
        (tmp_path / "credentials.yaml").write_text(yaml.safe_dump(legacy))

        cur = get_current_profile(service="mycli")
        assert cur is not None
        assert cur["endpoint"] == "https://old.example.com"
        assert cur["_name"] == "prod"

    def test_legacy_file_migrated_on_write(self, tmp_path):
        legacy = {
            "profiles": {"prod": {"endpoint": "https://old.example.com", "token": "T"}},
            "current": "prod",
        }
        p = tmp_path / "credentials.yaml"
        p.write_text(yaml.safe_dump(legacy))

        save_profile("dev", {"token": "D"}, service="mycli")

        raw = yaml.safe_load(p.read_text())
        assert "services" in raw
        block = raw["services"]["mycli"]
        assert "prod" in block["profiles"]
        assert block["profiles"]["prod"]["endpoint"] == "https://old.example.com"
        assert "dev" in block["profiles"]
        assert block["current"] == "dev"

    def test_legacy_delete_keeps_file(self, tmp_path):
        legacy = {
            "profiles": {"prod": {"token": "T"}, "dev": {"token": "D"}},
            "current": "prod",
        }
        (tmp_path / "credentials.yaml").write_text(yaml.safe_dump(legacy))

        delete_profile("prod")
        assert get_profile("prod") is None
        assert get_profile("dev") == {"token": "D"}


# ---------------------------------------------------------------------------
# Generated CLI behavior
# ---------------------------------------------------------------------------


@pytest.fixture
def http_mock(monkeypatch):
    """Record every request URL sent by HttpClient."""
    calls: list[str] = []

    def _mock_request(self_obj, method, url, data=None, query_params=None, headers=None, timeout=None, files=None):
        calls.append(url)
        resp = MagicMock()
        resp.json.return_value = {}
        resp.status_code = 200
        resp.text = ""
        return resp

    monkeypatch.setattr("cliyard.client.http.HttpClient.request", _mock_request)
    return calls


class TestGeneratedCli:
    def test_auth_status_only_shows_own_service(self):
        from cliyard.runtime import create_cli

        save_profile("prod", {"endpoint": "https://k.example.com", "token": "KETA_TOKEN"}, service="ketacli")
        save_profile("jenkins", {"endpoint": "https://j.example.com", "token": "JEN_TOKEN"}, service="test-service")

        cli = create_cli(FIXTURES_DIR)
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "jenkins" in result.output
        assert "JEN" in result.output
        assert "ketacli" not in result.output
        assert "KETA_TOKEN" not in result.output

    def test_auth_status_empty_when_no_own_profiles(self):
        from cliyard.runtime import create_cli

        save_profile("prod", {"endpoint": "https://k.example.com", "token": "K"}, service="ketacli")

        cli = create_cli(FIXTURES_DIR)
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["auth", "status"])

        assert result.exit_code == 0
        assert "No environments configured." in result.output
        assert "ketacli" not in result.output

    def test_auth_add_and_status_roundtrip(self):
        from cliyard.runtime import create_cli

        cli = create_cli(FIXTURES_DIR)
        runner = click.testing.CliRunner()
        result = runner.invoke(
            cli,
            ["auth", "add", "-n", "myenv", "-t", "MYTOKEN", "-e", "https://my.example.com"],
        )
        assert result.exit_code == 0

        assert get_current_profile(service="test-service")["_name"] == "myenv"
        assert get_profile("myenv", service="ketacli") is None

    def test_base_url_not_contaminated_across_services(self, http_mock):
        from cliyard.runtime import create_cli

        save_profile("prod", {"endpoint": "https://keta-prod.example.com"}, service="ketacli")

        cli = create_cli(FIXTURES_DIR)
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["repos", "list"])

        assert result.exit_code == 0
        assert http_mock == ["https://httpbin.org/repos"]
