"""Smoke test: verify schema types can be imported."""

import pytest


def test_import():
    from cliyard.schema.types import ServiceSpec

    assert ServiceSpec is not None


def test_import_all_types():
    from cliyard.schema.types import (
        AuthChain,
        AuthStep,
        FieldSpec,
        HttpConfig,
        MethodSpec,
        OutputSpec,
        ParamConfig,
        ParamSpec,
        ResourceSpec,
        ServerConfig,
        ServiceSpec,
    )

    # Verify all types are importable
    assert all(
        t is not None
        for t in [
            AuthChain,
            AuthStep,
            FieldSpec,
            HttpConfig,
            MethodSpec,
            OutputSpec,
            ParamConfig,
            ParamSpec,
            ResourceSpec,
            ServerConfig,
            ServiceSpec,
        ]
    )


def test_fixture_loads(minimal_service_yaml):
    """Verify minimal_service.yaml fixture loads correctly."""
    assert minimal_service_yaml["name"] == "test-service"
    assert minimal_service_yaml["server"]["base_url"] == "https://httpbin.org"


def test_fixture_typed(minimal_service_yaml):
    """Verify fixture dict matches ServiceSpec shape."""
    spec = minimal_service_yaml
    # Check required top-level keys exist
    assert "name" in spec
    assert "version" in spec
    assert "description" in spec
    assert "server" in spec
    assert "base_url" in spec["server"]


def test_resource_fixture(repos_resource_yaml):
    """Verify repos_resource.yaml fixture loads correctly."""
    assert repos_resource_yaml["description"] == "Repos"
    assert repos_resource_yaml["path"] == "repos"
    assert "list" in repos_resource_yaml["methods"]
    assert "create" in repos_resource_yaml["methods"]


def test_bad_fixture_loads(bad_service_yaml):
    """Verify bad_service.yaml loads but is incomplete."""
    assert bad_service_yaml["name"] == "bad-service"
    assert "server" not in bad_service_yaml
