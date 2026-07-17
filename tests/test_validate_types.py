"""Tests for cliyard field type validators."""

import pytest

from cliyard.validate import ValidationError, validate_field


class TestValidateField:
    """Test the main validate_field dispatch function."""

    def test_unknown_type(self):
        """Unknown type raises ValidationError."""
        spec = {"name": "x", "type": "unknown"}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "value")
        assert "Unknown type" in str(exc_info.value)

    def test_default_type_is_string(self):
        """Missing type defaults to string."""
        spec = {"name": "x"}
        assert validate_field(spec, "hello") == "hello"


class TestValidateString:
    """Test string field validation."""

    def test_valid_string(self):
        """Valid string passes."""
        spec = {"name": "name", "type": "string"}
        assert validate_field(spec, "hello") == "hello"

    def test_converts_to_string(self):
        """Non-string values are converted."""
        spec = {"name": "name", "type": "string"}
        assert validate_field(spec, 42) == "42"

    def test_min_length(self):
        """String shorter than min_length raises."""
        spec = {"name": "name", "type": "string", "min_length": 3}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "ab")
        assert "too short" in str(exc_info.value)

    def test_min_length_pass(self):
        """String meeting min_length passes."""
        spec = {"name": "name", "type": "string", "min_length": 3}
        assert validate_field(spec, "abc") == "abc"

    def test_max_length(self):
        """String longer than max_length raises."""
        spec = {"name": "name", "type": "string", "max_length": 3}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "abcd")
        assert "too long" in str(exc_info.value)

    def test_max_length_pass(self):
        """String within max_length passes."""
        spec = {"name": "name", "type": "string", "max_length": 3}
        assert validate_field(spec, "ab") == "ab"

    def test_pattern_match(self):
        """String matching pattern passes."""
        spec = {"name": "email", "type": "string", "pattern": r"^[a-z]+@[a-z]+\.[a-z]+$"}
        assert validate_field(spec, "test@example.com") == "test@example.com"

    def test_pattern_no_match(self):
        """String not matching pattern raises."""
        spec = {"name": "email", "type": "string", "pattern": r"^[a-z]+@[a-z]+\.[a-z]+$"}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "invalid-email")
        assert "pattern" in str(exc_info.value)

    def test_min_and_max_length(self):
        """Both min_length and max_length enforced."""
        spec = {"name": "name", "type": "string", "min_length": 2, "max_length": 5}
        assert validate_field(spec, "abc") == "abc"
        with pytest.raises(ValidationError):
            validate_field(spec, "a")
        with pytest.raises(ValidationError):
            validate_field(spec, "abcdef")


class TestValidateInt:
    """Test integer field validation."""

    def test_valid_int(self):
        """Valid integer passes."""
        spec = {"name": "age", "type": "int"}
        assert validate_field(spec, 42) == 42

    def test_converts_string(self):
        """String integer is converted."""
        spec = {"name": "age", "type": "int"}
        assert validate_field(spec, "42") == 42

    def test_converts_float_with_integer_value(self):
        """Float with integer value is converted."""
        spec = {"name": "age", "type": "int"}
        assert validate_field(spec, 42.0) == 42

    def test_rejects_non_integer_float(self):
        """Float with decimal part raises."""
        spec = {"name": "age", "type": "int"}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, 42.5)
        assert "not an integer" in str(exc_info.value)

    def test_invalid_string(self):
        """Non-convertible string raises."""
        spec = {"name": "age", "type": "int"}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "abc")
        assert "Cannot convert" in str(exc_info.value)

    def test_min_value(self):
        """Value below min raises."""
        spec = {"name": "age", "type": "int", "min": 0}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, -1)
        assert "too small" in str(exc_info.value)

    def test_min_value_pass(self):
        """Value at min passes."""
        spec = {"name": "age", "type": "int", "min": 0}
        assert validate_field(spec, 0) == 0

    def test_max_value(self):
        """Value above max raises."""
        spec = {"name": "age", "type": "int", "max": 100}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, 101)
        assert "too large" in str(exc_info.value)

    def test_max_value_pass(self):
        """Value at max passes."""
        spec = {"name": "age", "type": "int", "max": 100}
        assert validate_field(spec, 100) == 100

    def test_min_and_max(self):
        """Both min and max enforced."""
        spec = {"name": "age", "type": "int", "min": 0, "max": 100}
        assert validate_field(spec, 50) == 50
        with pytest.raises(ValidationError):
            validate_field(spec, -1)
        with pytest.raises(ValidationError):
            validate_field(spec, 101)


class TestValidateFloat:
    """Test float field validation."""

    def test_valid_float(self):
        """Valid float passes."""
        spec = {"name": "price", "type": "float"}
        assert validate_field(spec, 3.14) == 3.14

    def test_converts_int(self):
        """Integer is converted to float."""
        spec = {"name": "price", "type": "float"}
        assert validate_field(spec, 42) == 42.0

    def test_converts_string(self):
        """String float is converted."""
        spec = {"name": "price", "type": "float"}
        assert validate_field(spec, "3.14") == 3.14

    def test_invalid_string(self):
        """Non-convertible string raises."""
        spec = {"name": "price", "type": "float"}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "abc")
        assert "Cannot convert" in str(exc_info.value)

    def test_min_value(self):
        """Value below min raises."""
        spec = {"name": "price", "type": "float", "min": 0.0}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, -0.1)
        assert "too small" in str(exc_info.value)

    def test_min_value_pass(self):
        """Value at min passes."""
        spec = {"name": "price", "type": "float", "min": 0.0}
        assert validate_field(spec, 0.0) == 0.0

    def test_max_value(self):
        """Value above max raises."""
        spec = {"name": "price", "type": "float", "max": 100.0}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, 100.1)
        assert "too large" in str(exc_info.value)

    def test_max_value_pass(self):
        """Value at max passes."""
        spec = {"name": "price", "type": "float", "max": 100.0}
        assert validate_field(spec, 100.0) == 100.0


class TestValidateBool:
    """Test boolean field validation."""

    def test_native_true(self):
        """Native True passes."""
        spec = {"name": "flag", "type": "bool"}
        assert validate_field(spec, True) is True

    def test_native_false(self):
        """Native False passes."""
        spec = {"name": "flag", "type": "bool"}
        assert validate_field(spec, False) is False

    def test_string_true(self):
        """String 'true' is converted."""
        spec = {"name": "flag", "type": "bool"}
        assert validate_field(spec, "true") is True
        assert validate_field(spec, "True") is True
        assert validate_field(spec, "TRUE") is True

    def test_string_false(self):
        """String 'false' is converted."""
        spec = {"name": "flag", "type": "bool"}
        assert validate_field(spec, "false") is False
        assert validate_field(spec, "False") is False
        assert validate_field(spec, "FALSE") is False

    def test_string_one_zero(self):
        """String '1'/'0' are converted."""
        spec = {"name": "flag", "type": "bool"}
        assert validate_field(spec, "1") is True
        assert validate_field(spec, "0") is False

    def test_string_yes_no(self):
        """String 'yes'/'no' are converted."""
        spec = {"name": "flag", "type": "bool"}
        assert validate_field(spec, "yes") is True
        assert validate_field(spec, "no") is False

    def test_int_one_zero(self):
        """Integer 1/0 are converted."""
        spec = {"name": "flag", "type": "bool"}
        assert validate_field(spec, 1) is True
        assert validate_field(spec, 0) is False

    def test_invalid_string(self):
        """Non-boolean string raises."""
        spec = {"name": "flag", "type": "bool"}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "maybe")
        assert "Cannot convert" in str(exc_info.value)


class TestValidateEnum:
    """Test enum field validation."""

    def test_valid_enum(self):
        """Value in choices passes."""
        spec = {"name": "status", "type": "enum", "choices": ["active", "inactive"]}
        assert validate_field(spec, "active") == "active"

    def test_case_insensitive(self):
        """Case-insensitive match returns original case."""
        spec = {"name": "status", "type": "enum", "choices": ["active", "inactive"]}
        assert validate_field(spec, "ACTIVE") == "active"

    def test_invalid_choice(self):
        """Value not in choices raises."""
        spec = {"name": "status", "type": "enum", "choices": ["active", "inactive"]}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "deleted")
        assert "Invalid choice" in str(exc_info.value)

    def test_converts_to_string(self):
        """Non-string values are converted."""
        spec = {"name": "status", "type": "enum", "choices": ["1", "2", "3"]}
        assert validate_field(spec, 1) == "1"

    def test_empty_choices_raises(self):
        """Empty choices list raises."""
        spec = {"name": "status", "type": "enum", "choices": []}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "active")
        assert "requires 'choices'" in str(exc_info.value)

    def test_missing_choices_raises(self):
        """Missing choices key raises."""
        spec = {"name": "status", "type": "enum"}
        with pytest.raises(ValidationError) as exc_info:
            validate_field(spec, "active")
        assert "requires 'choices'" in str(exc_info.value)


class TestValidationError:
    """Test ValidationError exception."""

    def test_attributes(self):
        """ValidationError has field and message."""
        exc = ValidationError("age", "too small")
        assert exc.field == "age"
        assert exc.message == "too small"
        assert "age" in str(exc)
        assert "too small" in str(exc)
