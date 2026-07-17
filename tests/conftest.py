"""Shared fixtures for cliyard tests."""

from pathlib import Path

import pytest
import yaml

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def minimal_service_path():
    """Path to minimal_service.yaml fixture."""
    return FIXTURES_DIR / "minimal_service.yaml"


@pytest.fixture
def repos_resource_path():
    """Path to repos_resource.yaml fixture."""
    return FIXTURES_DIR / "repos_resource.yaml"


@pytest.fixture
def bad_service_path():
    """Path to bad_service.yaml fixture."""
    return FIXTURES_DIR / "bad_service.yaml"


@pytest.fixture
def minimal_service_yaml(minimal_service_path):
    """Loaded minimal service YAML dict."""
    return yaml.safe_load(minimal_service_path.read_text())


@pytest.fixture
def repos_resource_yaml(repos_resource_path):
    """Loaded repos resource YAML dict."""
    return yaml.safe_load(repos_resource_path.read_text())


@pytest.fixture
def bad_service_yaml(bad_service_path):
    """Loaded bad service YAML dict."""
    return yaml.safe_load(bad_service_path.read_text())
