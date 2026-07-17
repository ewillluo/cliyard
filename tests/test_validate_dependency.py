"""Tests for cliyard field dependency support."""

import pytest

from cliyard.validate.dependency import check_dependencies
from cliyard.validate.types import ValidationError


class TestCheckDependencies:
    """Test the check_dependencies function."""

    def test_no_depends_on_field(self):
        """Fields without depends_on are skipped."""
        spec = {"name": "host", "type": "string", "required": True}
        errors = check_dependencies({}, [spec])
        assert errors == []

    def test_condition_met_required_missing(self):
        """Error when condition met, required, and value missing."""
        spec = {
            "name": "db_password",
            "type": "string",
            "required": True,
            "depends_on": {"field": "auth_type", "eq": "password"},
        }
        errors = check_dependencies({"auth_type": "password"}, [spec])
        assert len(errors) == 1
        assert errors[0].field == "db_password"
        assert "required when auth_type=password" in errors[0].message

    def test_condition_met_required_present(self):
        """No error when condition met, required, and value provided."""
        spec = {
            "name": "db_password",
            "type": "string",
            "required": True,
            "depends_on": {"field": "auth_type", "eq": "password"},
        }
        errors = check_dependencies(
            {"auth_type": "password", "db_password": "secret"}, [spec]
        )
        assert errors == []

    def test_condition_not_met(self):
        """No error when condition not met (field ignored)."""
        spec = {
            "name": "db_password",
            "type": "string",
            "required": True,
            "depends_on": {"field": "auth_type", "eq": "password"},
        }
        errors = check_dependencies({"auth_type": "token"}, [spec])
        assert errors == []

    def test_condition_not_met_value_missing(self):
        """No error when condition not met even if required value missing."""
        spec = {
            "name": "db_password",
            "type": "string",
            "required": True,
            "depends_on": {"field": "auth_type", "eq": "password"},
        }
        errors = check_dependencies({"auth_type": "oauth"}, [spec])
        assert errors == []

    def test_multiple_fields_mixed(self):
        """Multiple fields with different dependency states."""
        specs = [
            {
                "name": "db_password",
                "type": "string",
                "required": True,
                "depends_on": {"field": "auth_type", "eq": "password"},
            },
            {
                "name": "api_key",
                "type": "string",
                "required": True,
                "depends_on": {"field": "auth_type", "eq": "api"},
            },
        ]
        # auth_type=password triggers db_password, not api_key
        errors = check_dependencies({"auth_type": "password"}, specs)
        assert len(errors) == 1
        assert errors[0].field == "db_password"

    def test_not_required_field_ignored(self):
        """Non-required fields with depends_on produce no errors."""
        spec = {
            "name": "optional_param",
            "type": "string",
            "required": False,
            "depends_on": {"field": "auth_type", "eq": "password"},
        }
        errors = check_dependencies({"auth_type": "password"}, [spec])
        assert errors == []

    def test_dep_field_not_in_params(self):
        """Condition not met when dep field not in params."""
        spec = {
            "name": "db_password",
            "type": "string",
            "required": True,
            "depends_on": {"field": "auth_type", "eq": "password"},
        }
        errors = check_dependencies({}, [spec])
        assert errors == []

    def test_numeric_eq_condition(self):
        """Eq condition works with numeric values."""
        spec = {
            "name": "port",
            "type": "int",
            "required": True,
            "depends_on": {"field": "mode", "eq": 8080},
        }
        errors = check_dependencies({"mode": 8080}, [spec])
        assert len(errors) == 1
        assert errors[0].field == "port"

    def test_empty_specs(self):
        """Empty field specs list returns no errors."""
        errors = check_dependencies({"auth_type": "password"}, [])
        assert errors == []

    def test_depends_on_missing_field_key(self):
        """depends_on without 'field' key is skipped."""
        spec = {
            "name": "db_password",
            "type": "string",
            "required": True,
            "depends_on": {"eq": "password"},
        }
        errors = check_dependencies({"auth_type": "password"}, [spec])
        assert errors == []

    def test_depends_on_missing_eq_key(self):
        """depends_on without 'eq' key is skipped."""
        spec = {
            "name": "db_password",
            "type": "string",
            "required": True,
            "depends_on": {"field": "auth_type"},
        }
        errors = check_dependencies({"auth_type": "password"}, [spec])
        assert errors == []
