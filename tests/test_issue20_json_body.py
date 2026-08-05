"""Regression tests for issue #20 — body params cannot pass JSON objects.

Covers:
1. ``type: json`` (alias ``object``) maps in ``_map_param_type``.
2. ``validate_field`` parses a JSON string into a dict/object.
3. A JSON body param renders into ``request_body`` as a nested object
   (not a Python repr / not a quoted string).
4. Invalid JSON raises a clear ``ValidationError``.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

import click.testing
import pytest


# ---------------------------------------------------------------------------
# 1. json / object type accepted in type mapping
# ---------------------------------------------------------------------------


class TestJsonTypeMapping:
    @pytest.mark.parametrize("type_str", ["json", "object"])
    def test_map_param_type_accepts_json(self, type_str):
        from cliyard.engine.builder import _map_param_type

        assert _map_param_type(type_str) is str

    def test_map_param_type_still_rejects_unknown(self):
        from cliyard.engine.builder import _map_param_type

        with pytest.raises(ValueError):
            _map_param_type("madeup_unknown")


# ---------------------------------------------------------------------------
# 2. validate_field parses JSON strings
# ---------------------------------------------------------------------------


class TestJsonValidation:
    @pytest.mark.parametrize("type_str", ["json", "object"])
    def test_parses_object(self, type_str):
        from cliyard.validate import validate_field

        result = validate_field(
            {"name": "spec", "type": type_str},
            '{"modelRef": "x", "prompt": "y"}',
        )
        assert result == {"modelRef": "x", "prompt": "y"}
        assert isinstance(result, dict)

    @pytest.mark.parametrize("type_str", ["json", "object"])
    def test_parses_array(self, type_str):
        from cliyard.validate import validate_field

        result = validate_field(
            {"name": "tags", "type": type_str},
            '["a", "b"]',
        )
        assert result == ["a", "b"]

    @pytest.mark.parametrize("type_str", ["json", "object"])
    def test_passthrough_native_dict(self, type_str):
        from cliyard.validate import validate_field

        result = validate_field(
            {"name": "spec", "type": type_str},
            {"modelRef": "x"},
        )
        assert result == {"modelRef": "x"}

    @pytest.mark.parametrize("type_str", ["json", "object"])
    def test_invalid_json_raises(self, type_str):
        from cliyard.validate import validate_field

        with pytest.raises(Exception, match="JSON"):
            validate_field({"name": "spec", "type": type_str}, "not-json-{{")

    @pytest.mark.parametrize("type_str", ["json", "object"])
    def test_native_scalar_raises(self, type_str):
        from cliyard.validate import validate_field

        with pytest.raises(Exception):
            validate_field({"name": "spec", "type": type_str}, 42)


# ---------------------------------------------------------------------------
# 3. End-to-end: JSON body param renders as nested object in request_body
# ---------------------------------------------------------------------------


class TestJsonRequestBody:
    _SPEC = """\
path: agents
methods:
  create:
    http:
      method: POST
      path: agents
    params:
      body:
        - name: spec
          type: json
          required: true
    request_body: |
      apiVersion: orchestra.io/v1alpha1
      kind: agent
      metadata:
        name: "{{ name }}"
      spec: {{ spec | tojson }}
"""

    def _load(self, tmp_path):
        p = tmp_path / "agent.yaml"
        p.write_text(self._SPEC)
        import yaml

        return yaml.safe_load(p.read_text())["methods"]["create"]

    def test_body_is_object_not_string(self, tmp_path):
        from cliyard.engine.assembler import assemble_request

        spec = self._load(tmp_path)
        req = assemble_request(
            spec,
            {"spec": {"modelRef": "x", "prompt": "y"}, "name": "my-agent"},
            "http://example.com",
        )
        assert isinstance(req.body, dict)
        assert req.body["spec"] == {"modelRef": "x", "prompt": "y"}
        assert req.body["metadata"] == {"name": "my-agent"}

    def test_bind_and_validate_parses_cli_string(self, tmp_path):
        from cliyard.engine.binder import bind_and_validate

        spec = self._load(tmp_path)
        result = bind_and_validate(
            {"spec": '{"modelRef": "x", "prompt": "y"}', "name": "my-agent"},
            spec,
        )
        assert result.body["spec"] == {"modelRef": "x", "prompt": "y"}

    def test_body_plain_placeholder_renders_as_object(self, tmp_path):
        from cliyard.engine.assembler import assemble_request

        spec = self._load(tmp_path)
        spec["request_body"] = (
            "apiVersion: orchestra.io/v1alpha1\n"
            "kind: agent\n"
            "metadata:\n"
            '  name: "{{ name }}"\n'
            "spec: {{ spec }}\n"
        )
        req = assemble_request(
            spec,
            {"spec": {"modelRef": "x"}, "name": "my-agent"},
            "http://example.com",
        )
        assert isinstance(req.body, dict)
        assert req.body["spec"] == {"modelRef": "x"}

    def test_e2e_request_body_from_cli_string(self, tmp_path):
        from cliyard.engine.assembler import assemble_request
        from cliyard.engine.binder import bind_and_validate

        spec = self._load(tmp_path)
        validated = bind_and_validate(
            {"spec": '{"modelRef": "x"}', "name": "my-agent"},
            spec,
        )
        merged = {"body": validated.body, "path": validated.path}
        merged.update(validated.body)
        merged.update(validated.path)
        req = assemble_request(spec, merged, "http://example.com")
        assert req.body["spec"] == {"modelRef": "x"}


# ---------------------------------------------------------------------------
# 4. json type in query/header position serializes back to JSON string
# ---------------------------------------------------------------------------


class TestJsonQueryHeader:
    def test_query_json_param_serializes_as_json(self):
        from cliyard.engine.assembler import assemble_request

        spec = {
            "http": {"method": "GET", "path": "/repos"},
            "params": {
                "query": [{"name": "filter", "type": "json"}],
            },
        }
        req = assemble_request(
            spec,
            {"query": {"filter": {"kind": "agent"}}},
            "http://example.com",
        )
        assert req.query_params["filter"] == '{"kind": "agent"}'

    def test_query_plain_string_unchanged(self):
        from cliyard.engine.assembler import assemble_request

        spec = {
            "http": {"method": "GET", "path": "/repos"},
            "params": {
                "query": [{"name": "q", "type": "string"}],
            },
        }
        req = assemble_request(
            spec,
            {"query": {"q": "hello world"}},
            "http://example.com",
        )
        assert req.query_params["q"] == "hello world"

    def test_header_json_param_serializes_as_json(self):
        from cliyard.engine.assembler import assemble_request

        spec = {
            "http": {"method": "GET", "path": "/repos"},
            "params": {
                "header": [{"name": "meta", "type": "json"}],
            },
        }
        req = assemble_request(
            spec,
            {"header": {"meta": {"trace": "1"}}},
            "http://example.com",
        )
        assert req.headers["meta"] == '{"trace": "1"}'


# ---------------------------------------------------------------------------
# 5. json type in path position renders dict as JSON, not Python repr
# ---------------------------------------------------------------------------


class TestJsonPathParam:
    def test_path_dict_renders_as_json(self):
        from cliyard.engine.template import Template

        rendered = Template("items/{{ spec }}").render(spec={"kind": "agent"})
        assert rendered == 'items/{"kind": "agent"}'

    def test_path_list_renders_as_json(self):
        from cliyard.engine.template import Template

        rendered = Template("items/{{ spec }}").render(spec=["a", "b"])
        assert rendered == 'items/["a", "b"]'