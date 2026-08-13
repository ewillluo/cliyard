"""Tests for YAML spec → command tree / flow tree + JSON Schema converter (plan T2).

Covers:
- ``build_command_tree`` on ``tests/fixtures/spec-dir`` → repos group + types
- labels resolution (list / str / missing) via an explicit tmp_path spec
- ``params_to_json_schema`` type mapping incl. multiple / required / default / x-location
- ``build_flow_schema`` flow params (query/body/header) mapping
- ``build_command_tree`` on ``examples/demo`` → user / pet groups + add_user flow
"""

from pathlib import Path

from cliyard.server.schema_bridge import (
    build_command_tree,
    build_flow_schema,
    params_to_json_schema,
)

SPEC_DIR = Path(__file__).parent / "fixtures" / "spec-dir"
DEMO_DIR = Path(__file__).parent.parent / "examples" / "demo"


# ---------------------------------------------------------------------------
# build_command_tree — fixtures/spec-dir
# ---------------------------------------------------------------------------


def test_command_tree_has_repos_group():
    tree = build_command_tree(SPEC_DIR)
    groups = {g["group"]: g for g in tree["groups"]}

    assert "repos" in groups
    repos = groups["repos"]
    assert repos["desc"] == "Repos"

    commands = {c["name"]: c for c in repos["commands"]}
    assert set(commands) == {"list", "create"}
    assert commands["list"]["method"] == "GET"
    assert commands["list"]["path"] == "repos"
    assert commands["list"]["desc"] == "list"
    assert commands["create"]["method"] == "POST"

    # service metadata propagated from _auth.yaml
    assert tree["service"]["name"] == "test-service"
    assert tree["service"]["description"] == "Test service for cliyard runtime pipeline"


def test_command_tree_labels_empty_when_missing():
    tree = build_command_tree(SPEC_DIR)
    repos = next(g for g in tree["groups"] if g["group"] == "repos")
    commands = {c["name"]: c for c in repos["commands"]}
    assert commands["list"]["labels"] == []
    assert commands["create"]["labels"] == []


def test_command_tree_types_required_default_xlocation():
    tree = build_command_tree(SPEC_DIR)
    repos = next(g for g in tree["groups"] if g["group"] == "repos")
    commands = {c["name"]: c for c in repos["commands"]}

    # list.page: query int with default
    list_schema = commands["list"]["schema"]
    assert list_schema["type"] == "object"
    assert list_schema["title"] == "list"
    assert list_schema["properties"]["page"] == {
        "type": "integer",
        "default": 1,
        "x-location": "query",
    }
    assert list_schema["required"] == []

    # create.name: body string required
    create_schema = commands["create"]["schema"]
    assert create_schema["properties"]["name"] == {
        "type": "string",
        "x-location": "body",
    }
    assert create_schema["required"] == ["name"]


# ---------------------------------------------------------------------------
# params_to_json_schema — pure function mapping
# ---------------------------------------------------------------------------


def test_params_to_json_schema_type_mapping():
    param_list = {
        "query": [
            {"name": "status", "type": "enum", "choices": ["a", "b"],
             "default": "a", "description": "状态"},
            {"name": "limit", "type": "int", "default": 20},
        ],
        "path": [
            {"name": "pet_id", "type": "string", "required": True},
        ],
        "body": [
            {"name": "price", "type": "float"},
            {"name": "avatar", "type": "file"},
            {"name": "meta", "type": "object"},
            {"name": "tags", "type": "string", "multiple": True},
        ],
        "header": [
            {"name": "X-Token", "type": "string", "required": True},
        ],
        "argument": [
            {"name": "force", "type": "bool"},
        ],
    }
    schema = params_to_json_schema(param_list, title="pet-create")

    assert schema["type"] == "object"
    assert schema["title"] == "pet-create"
    props = schema["properties"]

    # enum → string + enum choices; default/description preserved
    assert props["status"] == {
        "type": "string",
        "enum": ["a", "b"],
        "default": "a",
        "description": "状态",
        "x-location": "query",
    }
    # int/integer → integer
    assert props["limit"] == {"type": "integer", "default": 20, "x-location": "query"}
    # string path param
    assert props["pet_id"] == {"type": "string", "x-location": "path"}
    # float → number
    assert props["price"] == {"type": "number", "x-location": "body"}
    # file → string format binary
    assert props["avatar"] == {"type": "string", "format": "binary", "x-location": "body"}
    # json/object → object
    assert props["meta"] == {"type": "object", "x-location": "body"}
    # multiple → array wrapper with single-value items
    assert props["tags"] == {"type": "array", "items": {"type": "string"}, "x-location": "body"}
    # header location preserved
    assert props["X-Token"]["x-location"] == "header"
    # argument location preserved; bool → boolean
    assert props["force"] == {"type": "boolean", "x-location": "argument"}

    # required aggregated at top level (deduplicated)
    assert schema["required"] == ["pet_id", "X-Token"]


def test_params_to_json_schema_integer_alias():
    schema = params_to_json_schema({"query": [{"name": "n", "type": "integer"}]})
    assert schema["properties"]["n"]["type"] == "integer"


def test_params_to_json_schema_multiple_with_enum_items():
    schema = params_to_json_schema(
        {"body": [{"name": "tags", "type": "enum", "choices": ["x", "y"], "multiple": True}]}
    )
    assert schema["properties"]["tags"] == {
        "type": "array",
        "items": {"type": "string", "enum": ["x", "y"]},
        "x-location": "body",
    }


def test_params_to_json_schema_required_string_form():
    schema = params_to_json_schema(
        {"query": [{"name": "a", "type": "string", "required": "true"},
                   {"name": "b", "type": "string", "required": "false"}]}
    )
    assert schema["required"] == ["a"]


def test_params_to_json_schema_empty():
    schema = params_to_json_schema(None)
    assert schema == {"type": "object", "properties": {}, "required": []}
    assert params_to_json_schema({}) == {"type": "object", "properties": {}, "required": []}


# ---------------------------------------------------------------------------
# build_flow_schema
# ---------------------------------------------------------------------------


def test_build_flow_schema_empty():
    assert build_flow_schema(None) == {"type": "object", "properties": {}, "required": []}
    assert build_flow_schema({}) == {"type": "object", "properties": {}, "required": []}


def test_build_flow_schema_maps_locations():
    flow_params = {
        "query": [{"name": "name", "type": "string", "required": True,
                   "description": "用户名"}],
        "header": [{"name": "X-Env", "type": "string"}],
    }
    schema = build_flow_schema(flow_params, title="add-user")
    assert schema["title"] == "add-user"
    assert schema["properties"]["name"] == {
        "type": "string",
        "description": "用户名",
        "x-location": "query",
    }
    assert schema["properties"]["X-Env"]["x-location"] == "header"
    assert schema["required"] == ["name"]


# ---------------------------------------------------------------------------
# labels resolution (explicit spec)
# ---------------------------------------------------------------------------


def test_labels_parsing_list_str_and_missing(tmp_path):
    (tmp_path / "_auth.yaml").write_text(
        "name: t\nserver:\n  base_url: http://x\n", encoding="utf-8"
    )
    (tmp_path / "repos.yaml").write_text(
        "description: Repos\n"
        "path: repos\n"
        "methods:\n"
        "  list:\n"
        "    labels: [v2, 已调试]\n"
        "    http: {method: GET}\n"
        "  get:\n"
        "    labels: 已调试\n"
        "    http: {method: GET}\n"
        "  create:\n"
        "    http: {method: POST}\n",
        encoding="utf-8",
    )

    tree = build_command_tree(tmp_path)
    repos = next(g for g in tree["groups"] if g["group"] == "repos")
    commands = {c["name"]: c for c in repos["commands"]}

    assert commands["list"]["labels"] == ["v2", "已调试"]
    assert commands["get"]["labels"] == ["已调试"]
    assert commands["create"]["labels"] == []


# ---------------------------------------------------------------------------
# examples/demo
# ---------------------------------------------------------------------------


def test_demo_has_user_and_pet_groups():
    tree = build_command_tree(DEMO_DIR)
    groups = {g["group"] for g in tree["groups"]}
    assert {"user", "pet"} <= groups

    user = next(g for g in tree["groups"] if g["group"] == "user")
    user_cmds = {c["name"] for c in user["commands"]}
    assert {"list", "create", "avatar"} <= user_cmds


def test_demo_add_user_flow_params_schema():
    tree = build_command_tree(DEMO_DIR)
    flows = {f["name"]: f for f in tree["flows"]}

    assert "add_user" in flows
    flow = flows["add_user"]
    assert flow["command"] == "add-user"
    assert flow["description"] == "新增用户（查→判→创→验）"
    assert flow["step_count"] >= 1

    schema = flow["params_schema"]
    assert "name" in schema["properties"]
    assert "name" in schema["required"]
    assert schema["properties"]["name"]["x-location"] == "query"
    assert schema["properties"]["phone"]["x-location"] == "query"


def test_demo_flow_without_params_returns_empty_schema():
    tree = build_command_tree(DEMO_DIR)
    flows = {f["name"]: f for f in tree["flows"]}
    assert flows["retry_demo"]["params_schema"] == {
        "type": "object",
        "properties": {},
        "required": [],
    }
