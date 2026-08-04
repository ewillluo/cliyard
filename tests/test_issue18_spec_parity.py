"""Regression tests for issue #18 — 5 spec-parity defects.

Covers:
1. ``server.base_url`` renders ``{{ env("VAR") }}`` templates.
2. ``type: integer`` is accepted as an alias for ``int``.
3. ``request_body`` supports Jinja ``{% if %}`` conditionals via block scalar.
4. header params apply ``field`` mapping; hyphenated param names bind correctly.
5. ``cliyard gen`` copies ``resources/`` subdir; empty lists output valid JSON.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import click.testing
import pytest
import yaml


def _write_spec_dir(tmp_path: Path) -> Path:
    """Create a minimal spec dir with _auth.yaml + a resource."""
    spec_dir = tmp_path / "specs"
    spec_dir.mkdir()
    (spec_dir / "_auth.yaml").write_text(
        "name: test\nserver:\n  base_url: http://example.com\n"
    )
    (spec_dir / "repos.yaml").write_text(
        "path: repos\nmethods:\n  list:\n    http:\n      method: GET\n"
        "    output:\n      items_path: $.items\n"
    )
    return spec_dir


# ---------------------------------------------------------------------------
# 1. server.base_url env() template rendering
# ---------------------------------------------------------------------------


class TestBaseUrlEnvTemplate:
    def test_dict_server_renders_env_template(self, tmp_path, monkeypatch):
        monkeypatch.setenv("ORCHESTRA_URL", "https://orchestra.example.com")
        spec_dir = _write_spec_dir(tmp_path)
        (spec_dir / "_auth.yaml").write_text(
            "name: test\nserver:\n  base_url: '{{ env(\"ORCHESTRA_URL\") }}'\n"
        )
        from cliyard.engine.loader import load_service

        service = load_service(spec_dir)
        assert service["server"]["base_url"] == "https://orchestra.example.com"

    def test_list_server_renders_env_template(self, tmp_path, monkeypatch):
        monkeypatch.setenv("GATEWAY_URL", "https://gw.example.com")
        spec_dir = tmp_path / "specs"
        spec_dir.mkdir()
        (spec_dir / "_auth.yaml").write_text(
            "name: test\nserver:\n"
            "  - name: gw\n    base_url: '{{ env(\"GATEWAY_URL\") }}'\n"
        )
        from cliyard.engine.loader import load_service

        service = load_service(spec_dir)
        assert service["servers"]["gw"]["base_url"] == "https://gw.example.com"

    def test_literal_base_url_unchanged(self, tmp_path):
        spec_dir = _write_spec_dir(tmp_path)
        from cliyard.engine.loader import load_service

        service = load_service(spec_dir)
        assert service["server"]["base_url"] == "http://example.com"


# ---------------------------------------------------------------------------
# 2. integer type alias
# ---------------------------------------------------------------------------


class TestIntegerTypeAlias:
    def test_map_param_type_accepts_integer(self):
        from cliyard.engine.builder import _map_param_type

        assert _map_param_type("integer") is int

    def test_validate_field_accepts_integer(self):
        from cliyard.validate import validate_field

        assert validate_field({"name": "n", "type": "integer"}, "42") == 42
        with pytest.raises(Exception):
            validate_field({"name": "n", "type": "integer"}, "abc")

    def test_integer_option_in_click_command(self, tmp_path):
        from cliyard.engine.builder import ServiceContext, build_operation_command

        spec = {
            "name": "jobs",
            "path": "jobs",
            "methods": {
                "create": {
                    "http": {"method": "POST"},
                    "params": {
                        "body": [{"name": "count", "type": "integer", "required": True}],
                    },
                },
            },
        }
        cmd = build_operation_command("create", spec["methods"]["create"],
                                      spec, ServiceContext(base_url="http://x"))
        from cliyard.engine.binder import bind_and_validate

        result = bind_and_validate({"count": "5"}, spec["methods"]["create"])
        assert result.body["count"] == 5


# ---------------------------------------------------------------------------
# 3. request_body Jinja conditionals via block scalar
# ---------------------------------------------------------------------------


class TestRequestBodyConditional:
    _SPEC = """\
path: orders
methods:
  create:
    http:
      method: POST
      path: orders
    params:
      query:
        - name: trace
          type: bool
    request_body: |
      {% if query.trace %}
      trace: "1"
      {% endif %}
      name: "{{ name }}"
"""

    def _load(self, tmp_path):
        p = tmp_path / "order.yaml"
        p.write_text(self._SPEC)
        return yaml.safe_load(p.read_text())["methods"]["create"]

    def test_conditional_body_with_trace(self, tmp_path):
        from cliyard.engine.assembler import assemble_request

        spec = self._load(tmp_path)
        req = assemble_request(spec, {"name": "abc", "query": {"trace": True}},
                               "http://example.com")
        assert req.body == {"trace": "1", "name": "abc"}

    def test_conditional_body_without_trace(self, tmp_path):
        from cliyard.engine.assembler import assemble_request

        spec = self._load(tmp_path)
        req = assemble_request(spec, {"name": "abc", "query": {}},
                               "http://example.com")
        assert req.body == {"name": "abc"}

    def test_plain_dict_request_body_unchanged(self):
        from cliyard.engine.assembler import assemble_request

        spec = {
            "http": {"method": "POST", "path": "/orders"},
            "request_body": {"name": "{{ name }}", "status": "placed"},
        }
        req = assemble_request(spec, {"name": "abc"}, "http://example.com")
        assert req.body == {"name": "abc", "status": "placed"}


# ---------------------------------------------------------------------------
# 4. header field mapping + hyphenated param names
# ---------------------------------------------------------------------------


class TestHeaderFieldMapping:
    def test_header_applies_field_mapping(self):
        from cliyard.engine.assembler import assemble_request

        spec = {
            "http": {"method": "GET", "path": "/repos"},
            "params": {
                "header": [{"name": "tenant", "field": "X-Tenant-Id", "type": "string"}],
            },
        }
        req = assemble_request(spec, {"header": {"tenant": "acme"}},
                               "http://example.com")
        assert req.headers == {"X-Tenant-Id": "acme"}

    def test_hyphenated_param_name_binds_value(self):
        from cliyard.engine.binder import bind_and_validate

        spec = {
            "params": {
                "header": [{"name": "x-namespace", "field": "X-Namespace",
                            "type": "string", "default": "default-ns"}],
            },
        }
        result = bind_and_validate({"x_namespace": "my-ns"}, spec)
        assert result.header == {"x-namespace": "my-ns"}

    def test_hyphenated_param_defaults_when_missing(self):
        from cliyard.engine.binder import bind_and_validate

        spec = {
            "params": {
                "header": [{"name": "x-namespace", "field": "X-Namespace",
                            "type": "string", "default": "default-ns"}],
            },
        }
        result = bind_and_validate({}, spec)
        assert result.header == {"x-namespace": "default-ns"}


# ---------------------------------------------------------------------------
# 5. gen copies resources/ + empty list outputs valid JSON
# ---------------------------------------------------------------------------


class TestGenCopiesSubdirs:
    def _run_gen(self, tmp_path):
        from cliyard.cli.__main__ import cli

        spec_dir = _write_spec_dir(tmp_path)
        (spec_dir / "resources").mkdir()
        (spec_dir / "resources" / "users.yaml").write_text(
            "path: users\nmethods:\n  list:\n    http:\n      method: GET\n"
        )
        (spec_dir / "flows").mkdir()
        (spec_dir / "flows" / "_flows.yaml").write_text(
            "flows: {}\n"
        )
        out = tmp_path / "out"
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["gen", "--name", "mycli",
                                     "--defs-path", str(spec_dir),
                                     "--output", str(out)])
        assert result.exit_code == 0, result.output
        return out / "src" / "mycli" / "specs"

    def test_copies_resources_and_flows_subdirs(self, tmp_path):
        specs_out = self._run_gen(tmp_path)
        assert (specs_out / "repos.yaml").exists()
        assert (specs_out / "resources" / "users.yaml").exists()
        assert (specs_out / "flows" / "_flows.yaml").exists()


class TestEmptyListJsonOutput:
    def _empty_response(self, *args, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"items": [], "total": 0}
        resp.status_code = 200
        resp.text = ""
        return resp

    def _invoke(self, fmt, monkeypatch):
        from cliyard.client.http import HttpClient
        from cliyard.engine.builder import ServiceContext, build_list_command

        monkeypatch.setattr(HttpClient, "request", self._empty_response)
        spec = {
            "name": "jobs", "path": "jobs",
            "methods": {"list": {"http": {"method": "GET"},
                                 "output": {"items_path": "$.items"}}},
        }
        cmd = build_list_command(spec, ServiceContext(base_url="http://t"))
        return click.testing.CliRunner().invoke(cmd, ["--format", fmt])

    def test_empty_json_is_valid_json(self, monkeypatch):
        result = self._invoke("json", monkeypatch)
        assert result.exit_code == 0
        payload = json.loads(result.output)
        assert payload["items"] == []
        assert payload["total"] == 0

    def test_empty_yaml_is_valid(self, monkeypatch):
        result = self._invoke("yaml", monkeypatch)
        assert result.exit_code == 0
        payload = yaml.safe_load(result.output)
        assert payload["items"] == []
        assert payload["total"] == 0

    def test_empty_table_keeps_no_results_message(self, monkeypatch):
        result = self._invoke("table", monkeypatch)
        assert result.exit_code == 0
        assert "No results found." in result.output


# ---------------------------------------------------------------------------
# Review follow-ups: missing-env warning, gen all subdirs, body parse warning
# ---------------------------------------------------------------------------


class TestBaseUrlEnvMissingWarns:
    def test_missing_env_keeps_literal_and_warns(self, tmp_path):
        spec_dir = _write_spec_dir(tmp_path)
        (spec_dir / "_auth.yaml").write_text(
            "name: test\nserver:\n  base_url: '{{ env(\"UNSET_VAR_XYZ\") }}'\n"
        )
        from cliyard.engine.loader import load_service

        with pytest.warns(UserWarning, match="rendered empty"):
            service = load_service(spec_dir)
        assert service["server"]["base_url"] == '{{ env("UNSET_VAR_XYZ") }}'

    def test_render_exception_keeps_literal_and_warns(self, tmp_path, monkeypatch):
        monkeypatch.delenv("UNSET_VAR_XYZ", raising=False)
        spec_dir = _write_spec_dir(tmp_path)
        (spec_dir / "_auth.yaml").write_text(
            "name: test\nserver:\n  base_url: '{{ env(\"UNSET_VAR_XYZ\") }'\n"
        )
        from cliyard.engine.loader import load_service

        with pytest.warns(UserWarning, match="failed to render"):
            service = load_service(spec_dir)
        assert service["server"]["base_url"] == '{{ env("UNSET_VAR_XYZ") }'


class TestGenCopiesAllSubdirs:
    def test_copies_custom_subdirs(self, tmp_path):
        from cliyard.cli.__main__ import cli

        spec_dir = _write_spec_dir(tmp_path)
        custom = spec_dir / "custom"
        custom.mkdir()
        (custom / "extra.yaml").write_text(
            "path: extra\nmethods:\n  list:\n    http:\n      method: GET\n"
        )
        out = tmp_path / "out"
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["gen", "--name", "mycli",
                                     "--defs-path", str(spec_dir),
                                     "--output", str(out)])
        assert result.exit_code == 0, result.output
        specs_out = out / "src" / "mycli" / "specs"
        assert (specs_out / "repos.yaml").exists()
        assert (specs_out / "custom" / "extra.yaml").exists()

    def test_plugins_still_copied_as_tree(self, tmp_path):
        from cliyard.cli.__main__ import cli

        spec_dir = _write_spec_dir(tmp_path)
        plugins = spec_dir / "plugins"
        plugins.mkdir()
        (plugins / "hooks.py").write_text("# plugin\n")
        (plugins / "data.yaml").write_text("x: 1\n")
        out = tmp_path / "out"
        runner = click.testing.CliRunner()
        result = runner.invoke(cli, ["gen", "--name", "mycli",
                                     "--defs-path", str(spec_dir),
                                     "--output", str(out)])
        assert result.exit_code == 0, result.output
        specs_out = out / "src" / "mycli" / "specs"
        assert (specs_out / "plugins" / "hooks.py").exists()
        assert (specs_out / "plugins" / "data.yaml").exists()


class TestRequestBodyParseWarns:
    def test_invalid_yaml_body_warns_and_stays_literal(self):
        from cliyard.engine.assembler import _parse_rendered_body

        with pytest.warns(UserWarning, match="invalid YAML"):
            body = _parse_rendered_body("name: [unclosed")
        assert body == "name: [unclosed"

    def test_non_mapping_body_warns_and_stays_literal(self):
        from cliyard.engine.assembler import _parse_rendered_body

        with pytest.warns(UserWarning, match="expected a mapping"):
            body = _parse_rendered_body("- a\n- b")
        assert body == "- a\n- b"

    def test_valid_mapping_body_unchanged(self):
        from cliyard.engine.assembler import _parse_rendered_body

        body = _parse_rendered_body("name: hello\nage: 3")
        assert body == {"name": "hello", "age": 3}
