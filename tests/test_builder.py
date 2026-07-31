import json

import click.testing
import yaml
from unittest.mock import MagicMock

from cliyard.engine.builder import ServiceContext, build_list_command, execute_pipeline

LONG_URL = "http://jenkins.ketaops.cc/job/issue%20%E7%BB%9F%E8%AE%A1%E6%95%B4%E7%90%86/"


def _mock_http_request(self_obj, method, url, data=None, query_params=None, headers=None, timeout=None, files=None):
    resp = MagicMock()
    resp.json.return_value = {
        "items": [{"name": "issue 统计整理", "url": LONG_URL, "color": "blue"}],
        "total": 1,
    }
    resp.status_code = 200
    resp.text = ""
    return resp


def _run_format(monkeypatch, fmt):
    monkeypatch.setenv("COLUMNS", "40")
    monkeypatch.setattr("cliyard.client.http.HttpClient.request", _mock_http_request)
    spec = {
        "name": "jobs",
        "path": "jobs",
        "methods": {"list": {"http": {"method": "GET"}, "output": {"items_path": "$.items"}}},
    }
    cmd = build_list_command(spec, ServiceContext(base_url="http://test.local"))
    return click.testing.CliRunner().invoke(cmd, ["--format", fmt])


def test_json_output_not_wrapped_in_narrow_terminal(monkeypatch):
    result = _run_format(monkeypatch, "json")
    assert result.exit_code == 0
    assert LONG_URL in result.output
    assert json.loads(result.output)["items"][0]["url"] == LONG_URL


def test_yaml_output_not_wrapped_in_narrow_terminal(monkeypatch):
    result = _run_format(monkeypatch, "yaml")
    assert result.exit_code == 0
    assert LONG_URL in result.output
    assert yaml.safe_load(result.output)["items"][0]["url"] == LONG_URL


def test_csv_output_not_wrapped_in_narrow_terminal(monkeypatch):
    result = _run_format(monkeypatch, "csv")
    assert result.exit_code == 0
    assert LONG_URL in result.output
    assert result.output.splitlines()[0] == "name,url,color"


class _FakeResponse:
    def __init__(self, text="", json_payload=None):
        self.text = text
        self.status_code = 200
        self.headers = {"Content-Type": "text/xml"}
        self._json = json_payload

    def json(self):
        if self._json is not None:
            return self._json
        raise ValueError("Expecting value: line 1 column 1 (char 0)")


class _FakeHttpClient:
    def __init__(self, response):
        self._response = response
        self.default_headers = {}

    def request(self, **kwargs):
        return self._response


def _run_pipeline(response):
    client = _FakeHttpClient(response)
    return execute_pipeline(
        {},
        {"http": {"method": "GET", "path": "/job/x/config.xml"}},
        {"path": "jobs"},
        ServiceContext(base_url="http://test.local"),
        http_client=client,
    )


def test_xml_response_returns_raw_text():
    assert _run_pipeline(_FakeResponse(text="<project/>")) == "<project/>"


def test_empty_response_returns_empty_dict():
    assert _run_pipeline(_FakeResponse(text="")) == {}


def test_whitespace_only_response_returns_empty_dict():
    assert _run_pipeline(_FakeResponse(text="   \n  ")) == {}


def test_json_response_still_parsed():
    assert _run_pipeline(_FakeResponse(json_payload={"ok": True})) == {"ok": True}


def test_raw_text_with_items_path_does_not_attempt_parse():
    client = _FakeHttpClient(_FakeResponse(text="<project/>"))
    result = execute_pipeline(
        {},
        {"http": {"method": "GET", "path": "/job/x/config.xml"}, "output": {"items_path": "$.items"}},
        {"path": "jobs"},
        ServiceContext(base_url="http://test.local"),
        http_client=client,
    )
    assert result == "<project/>"
