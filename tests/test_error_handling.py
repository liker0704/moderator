"""
Comprehensive unit tests for the error handling system.

Tests cover:
- ErrorSeverity enum values and validation
- ErrorCode dataclass structure and attributes
- Loading error codes from JSON configuration
- Error message formatting with and without context
- Request ID generation format and uniqueness
- Error code retrieval by various methods
- All error codes are accessible and valid
"""

import json
import re
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

import pytest

from backend.src.utils.errors import (
    ErrorSeverity,
    ErrorCode,
    ErrorCodes,
    format_error_message,
    generate_request_id,
    get_error_codes
)


# =============================================================================
# ErrorSeverity Enum Tests
# =============================================================================

class TestErrorSeverity:
    """Test suite for ErrorSeverity enum."""

    def test_severity_levels_exist(self):
        """Test that all required severity levels are defined."""
        # Arrange & Act & Assert
        assert ErrorSeverity.INFO.value == "INFO"
        assert ErrorSeverity.WARNING.value == "WARNING"
        assert ErrorSeverity.ERROR.value == "ERROR"
        assert ErrorSeverity.CRITICAL.value == "CRITICAL"

    def test_severity_count(self):
        """Test that there are exactly 4 severity levels."""
        # Arrange & Act
        severity_levels = list(ErrorSeverity)

        # Assert
        assert len(severity_levels) == 4

    def test_severity_values_are_strings(self):
        """Test that all severity values are uppercase strings."""
        # Arrange & Act & Assert
        for severity in ErrorSeverity:
            assert isinstance(severity.value, str)
            assert severity.value.isupper()

    def test_severity_from_string(self):
        """Test creating severity from string value."""
        # Arrange & Act
        severity = ErrorSeverity["ERROR"]

        # Assert
        assert severity == ErrorSeverity.ERROR

    def test_invalid_severity_raises_error(self):
        """Test that invalid severity string raises KeyError."""
        # Arrange & Act & Assert
        with pytest.raises(KeyError):
            ErrorSeverity["INVALID"]


# =============================================================================
# ErrorCode Dataclass Tests
# =============================================================================

class TestErrorCode:
    """Test suite for ErrorCode dataclass."""

    def test_error_code_creation(self):
        """Test creating an ErrorCode instance with all fields."""
        # Arrange & Act
        error = ErrorCode(
            code="ERR-TEST-001",
            title="Test Error",
            description="This is a test error",
            severity=ErrorSeverity.ERROR,
            recovery_steps=["Step 1", "Step 2"],
            example="Example usage"
        )

        # Assert
        assert error.code == "ERR-TEST-001"
        assert error.title == "Test Error"
        assert error.description == "This is a test error"
        assert error.severity == ErrorSeverity.ERROR
        assert error.recovery_steps == ["Step 1", "Step 2"]
        assert error.example == "Example usage"

    def test_error_code_optional_example(self):
        """Test creating ErrorCode without optional example field."""
        # Arrange & Act
        error = ErrorCode(
            code="ERR-TEST-002",
            title="Test Error",
            description="Test description",
            severity=ErrorSeverity.WARNING,
            recovery_steps=[]
        )

        # Assert
        assert error.example is None

    def test_error_code_empty_recovery_steps(self):
        """Test ErrorCode with empty recovery steps list."""
        # Arrange & Act
        error = ErrorCode(
            code="ERR-TEST-003",
            title="Test",
            description="Test",
            severity=ErrorSeverity.INFO,
            recovery_steps=[]
        )

        # Assert
        assert error.recovery_steps == []
        assert len(error.recovery_steps) == 0

    def test_error_code_attributes_immutable(self):
        """Test that ErrorCode dataclass attributes can be modified (not frozen)."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-004",
            title="Original",
            description="Original",
            severity=ErrorSeverity.INFO,
            recovery_steps=[]
        )

        # Act - dataclass is not frozen by default, so this should work
        error.title = "Modified"

        # Assert
        assert error.title == "Modified"


# =============================================================================
# ErrorCodes Class Tests - Loading and Initialization
# =============================================================================

class TestErrorCodesLoading:
    """Test suite for ErrorCodes class loading and initialization."""

    def test_load_from_default_path(self):
        """Test loading error codes from default JSON path."""
        # Arrange & Act
        error_codes = ErrorCodes()

        # Assert
        assert error_codes is not None
        assert hasattr(error_codes, '_errors')
        assert len(error_codes._errors) > 0

    def test_load_all_error_codes(self):
        """Test that all 10 error codes are loaded correctly."""
        # Arrange
        expected_codes = [
            "ERR-USER-001",
            "ERR-USER-002",
            "ERR-DISCORD-001",
            "ERR-DISCORD-002",
            "ERR-CHANNEL-001",
            "ERR-CHANNEL-002",
            "ERR-DB-001",
            "ERR-REPLY-001",
            "ERR-SYSTEM-001",
            "ERR-SYSTEM-002"
        ]

        # Act
        error_codes = ErrorCodes()
        all_errors = error_codes.list_all()

        # Assert
        assert len(all_errors) == 10
        loaded_codes = [err.code for err in all_errors]
        for expected_code in expected_codes:
            assert expected_code in loaded_codes

    def test_load_from_custom_path(self):
        """Test loading error codes from custom JSON file path."""
        # Arrange
        custom_json = {
            "errors": {
                "ERR-CUSTOM-001": {
                    "title": "Custom Error",
                    "description": "Custom description",
                    "severity": "ERROR",
                    "recovery_steps": ["Step 1"],
                    "example": None
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(custom_json, f)
            temp_path = Path(f.name)

        try:
            # Act
            error_codes = ErrorCodes(config_path=temp_path)

            # Assert
            assert error_codes.get("ERR-CUSTOM-001") is not None
            assert error_codes.get("ERR-CUSTOM-001").title == "Custom Error"
        finally:
            # Cleanup
            temp_path.unlink()

    def test_load_invalid_json_raises_error(self):
        """Test that loading invalid JSON raises JSONDecodeError."""
        # Arrange
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write("{ invalid json }")
            temp_path = Path(f.name)

        try:
            # Act & Assert
            with pytest.raises(json.JSONDecodeError):
                ErrorCodes(config_path=temp_path)
        finally:
            # Cleanup
            temp_path.unlink()

    def test_load_nonexistent_file_raises_error(self):
        """Test that loading from non-existent file raises FileNotFoundError."""
        # Arrange
        nonexistent_path = Path("/tmp/nonexistent_error_codes.json")

        # Act & Assert
        with pytest.raises(FileNotFoundError):
            ErrorCodes(config_path=nonexistent_path)

    def test_error_severity_parsing(self):
        """Test that error severities are correctly parsed from JSON."""
        # Arrange & Act
        error_codes = ErrorCodes()

        # Assert
        assert error_codes.ERR_USER_001.severity == ErrorSeverity.ERROR
        assert error_codes.ERR_USER_002.severity == ErrorSeverity.WARNING
        assert error_codes.ERR_DISCORD_001.severity == ErrorSeverity.CRITICAL
        assert error_codes.ERR_DISCORD_002.severity == ErrorSeverity.CRITICAL
        assert error_codes.ERR_SYSTEM_001.severity == ErrorSeverity.INFO

    def test_recovery_steps_loaded(self):
        """Test that recovery steps are properly loaded from JSON."""
        # Arrange & Act
        error_codes = ErrorCodes()
        error = error_codes.ERR_USER_001

        # Assert
        assert isinstance(error.recovery_steps, list)
        assert len(error.recovery_steps) > 0
        assert "Verify the user ID or Telegram user ID is correct" in error.recovery_steps


# =============================================================================
# ErrorCodes Class Tests - Retrieval Methods
# =============================================================================

class TestErrorCodesRetrieval:
    """Test suite for ErrorCodes retrieval methods."""

    def test_getattr_with_underscores(self):
        """Test retrieving error code using attribute access with underscores."""
        # Arrange
        error_codes = ErrorCodes()

        # Act
        error = error_codes.ERR_USER_001

        # Assert
        assert error.code == "ERR-USER-001"
        assert error.title == "User Not Found"

    def test_getattr_with_hyphens_fallback(self):
        """Test that hyphenated names are accessible via getattr."""
        # Arrange
        error_codes = ErrorCodes()

        # Act - This should work due to the hyphen-to-underscore conversion
        error = error_codes.get("ERR-USER-001")

        # Assert
        assert error is not None
        assert error.code == "ERR-USER-001"

    def test_getattr_invalid_code_raises_error(self):
        """Test that accessing non-existent error code raises AttributeError."""
        # Arrange
        error_codes = ErrorCodes()

        # Act & Assert
        with pytest.raises(AttributeError):
            _ = error_codes.ERR_INVALID_999

    def test_get_method_with_hyphenated_code(self):
        """Test get() method with hyphenated error code."""
        # Arrange
        error_codes = ErrorCodes()

        # Act
        error = error_codes.get("ERR-USER-001")

        # Assert
        assert error is not None
        assert error.code == "ERR-USER-001"

    def test_get_method_with_underscored_code(self):
        """Test get() method with underscored error code."""
        # Arrange
        error_codes = ErrorCodes()

        # Act
        error = error_codes.get("ERR_USER_001")

        # Assert
        assert error is not None
        assert error.code == "ERR-USER-001"

    def test_get_method_invalid_code_returns_none(self):
        """Test get() method returns None for invalid code without default."""
        # Arrange
        error_codes = ErrorCodes()

        # Act
        error = error_codes.get("ERR-INVALID-999")

        # Assert
        assert error is None

    def test_get_method_with_default(self):
        """Test get() method returns default value for invalid code."""
        # Arrange
        error_codes = ErrorCodes()
        default_error = error_codes.ERR_SYSTEM_002

        # Act
        error = error_codes.get("ERR-INVALID-999", default=default_error)

        # Assert
        assert error is not None
        assert error.code == "ERR-SYSTEM-002"

    def test_list_all_returns_all_errors(self):
        """Test list_all() returns all error codes."""
        # Arrange
        error_codes = ErrorCodes()

        # Act
        all_errors = error_codes.list_all()

        # Assert
        assert len(all_errors) == 10
        assert all(isinstance(err, ErrorCode) for err in all_errors)

    def test_list_all_no_duplicates(self):
        """Test list_all() returns no duplicate error codes."""
        # Arrange
        error_codes = ErrorCodes()

        # Act
        all_errors = error_codes.list_all()
        codes = [err.code for err in all_errors]

        # Assert
        assert len(codes) == len(set(codes))  # No duplicates


# =============================================================================
# Error Message Formatting Tests
# =============================================================================

class TestFormatErrorMessage:
    """Test suite for format_error_message() function."""

    def test_format_basic_error_message(self):
        """Test formatting error message without context or request ID."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-001",
            title="Test Error",
            description="This is a test error",
            severity=ErrorSeverity.ERROR,
            recovery_steps=["Step 1", "Step 2"]
        )

        # Act
        message = format_error_message(error)

        # Assert
        assert "❌ ERR-TEST-001: Test Error" in message
        assert "Reason: This is a test error" in message
        assert "Recovery:" in message
        assert "1. Step 1" in message
        assert "2. Step 2" in message
        assert "[Request ID:" in message

    def test_format_error_message_with_context(self):
        """Test formatting error message with context dictionary."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-002",
            title="Test Error",
            description="Test description",
            severity=ErrorSeverity.ERROR,
            recovery_steps=[]
        )
        context = {
            "user_id": 12345,
            "channel_id": "987654321"
        }

        # Act
        message = format_error_message(error, context=context)

        # Assert
        assert "user_id: 12345" in message
        assert "channel_id: 987654321" in message

    def test_format_error_message_with_request_id(self):
        """Test formatting error message with custom request ID."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-003",
            title="Test",
            description="Test",
            severity=ErrorSeverity.ERROR,
            recovery_steps=[]
        )
        custom_req_id = "REQ-CUSTOM123"

        # Act
        message = format_error_message(error, request_id=custom_req_id)

        # Assert
        assert "[Request ID: REQ-CUSTOM123]" in message

    def test_format_error_message_with_example(self):
        """Test formatting error message with example field."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-004",
            title="Test",
            description="Test",
            severity=ErrorSeverity.ERROR,
            recovery_steps=["Step 1"],
            example="Example: /command arg1 arg2"
        )

        # Act
        message = format_error_message(error)

        # Assert
        assert "Example: /command arg1 arg2" in message

    def test_format_error_message_without_example(self):
        """Test formatting error message without example field."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-005",
            title="Test",
            description="Test",
            severity=ErrorSeverity.ERROR,
            recovery_steps=[]
        )

        # Act
        message = format_error_message(error)

        # Assert
        assert "Example:" not in message

    def test_format_error_message_empty_recovery_steps(self):
        """Test formatting error message with no recovery steps."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-006",
            title="Test",
            description="Test",
            severity=ErrorSeverity.ERROR,
            recovery_steps=[]
        )

        # Act
        message = format_error_message(error)

        # Assert
        # Recovery section should not appear if there are no steps
        assert "Recovery:" not in message

    def test_format_error_message_empty_context(self):
        """Test formatting error message with empty context dict."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-007",
            title="Test",
            description="Test",
            severity=ErrorSeverity.ERROR,
            recovery_steps=[]
        )

        # Act
        message = format_error_message(error, context={})

        # Assert
        # Message should be formatted normally without context values
        assert "❌ ERR-TEST-007" in message


# =============================================================================
# Request ID Generation Tests
# =============================================================================

class TestGenerateRequestId:
    """Test suite for generate_request_id() function."""

    def test_request_id_format(self):
        """Test that generated request ID has correct format."""
        # Arrange & Act
        req_id = generate_request_id()

        # Assert
        assert req_id.startswith("REQ-")
        assert len(req_id) == 12  # "REQ-" (4) + 8 hex chars
        # Check the pattern: REQ-[8 hex chars]
        pattern = r'^REQ-[0-9A-F]{8}$'
        assert re.match(pattern, req_id)

    def test_request_id_uniqueness(self):
        """Test that multiple request IDs are unique."""
        # Arrange & Act
        request_ids = [generate_request_id() for _ in range(100)]

        # Assert
        assert len(request_ids) == len(set(request_ids))  # All unique

    def test_request_id_uppercase(self):
        """Test that request ID hex portion is uppercase."""
        # Arrange & Act
        req_id = generate_request_id()
        hex_portion = req_id[4:]  # Skip "REQ-"

        # Assert
        assert hex_portion.isupper()
        assert hex_portion.isalnum()

    def test_request_id_multiple_calls(self):
        """Test that consecutive calls generate different IDs."""
        # Arrange & Act
        req_id_1 = generate_request_id()
        req_id_2 = generate_request_id()
        req_id_3 = generate_request_id()

        # Assert
        assert req_id_1 != req_id_2
        assert req_id_2 != req_id_3
        assert req_id_1 != req_id_3


# =============================================================================
# Singleton Instance Tests
# =============================================================================

class TestGetErrorCodes:
    """Test suite for get_error_codes() singleton function."""

    def test_get_error_codes_returns_instance(self):
        """Test that get_error_codes() returns ErrorCodes instance."""
        # Arrange & Act
        error_codes = get_error_codes()

        # Assert
        assert isinstance(error_codes, ErrorCodes)

    def test_get_error_codes_singleton_behavior(self):
        """Test that get_error_codes() returns the same instance on multiple calls."""
        # Arrange & Act
        instance1 = get_error_codes()
        instance2 = get_error_codes()

        # Assert
        assert instance1 is instance2

    def test_singleton_has_all_error_codes(self):
        """Test that singleton instance has all error codes loaded."""
        # Arrange & Act
        error_codes = get_error_codes()
        all_errors = error_codes.list_all()

        # Assert
        assert len(all_errors) == 10


# =============================================================================
# Integration Tests - Real Error Codes
# =============================================================================

class TestRealErrorCodes:
    """Test suite for verifying all real error codes are accessible."""

    def test_all_user_errors_accessible(self):
        """Test that all user-related errors are accessible."""
        # Arrange
        error_codes = ErrorCodes()

        # Act & Assert
        assert error_codes.ERR_USER_001.code == "ERR-USER-001"
        assert error_codes.ERR_USER_002.code == "ERR-USER-002"

    def test_all_discord_errors_accessible(self):
        """Test that all Discord-related errors are accessible."""
        # Arrange
        error_codes = ErrorCodes()

        # Act & Assert
        assert error_codes.ERR_DISCORD_001.code == "ERR-DISCORD-001"
        assert error_codes.ERR_DISCORD_002.code == "ERR-DISCORD-002"

    def test_all_channel_errors_accessible(self):
        """Test that all channel-related errors are accessible."""
        # Arrange
        error_codes = ErrorCodes()

        # Act & Assert
        assert error_codes.ERR_CHANNEL_001.code == "ERR-CHANNEL-001"
        assert error_codes.ERR_CHANNEL_002.code == "ERR-CHANNEL-002"

    def test_all_database_errors_accessible(self):
        """Test that database error is accessible."""
        # Arrange
        error_codes = ErrorCodes()

        # Act & Assert
        assert error_codes.ERR_DB_001.code == "ERR-DB-001"

    def test_all_reply_errors_accessible(self):
        """Test that reply error is accessible."""
        # Arrange
        error_codes = ErrorCodes()

        # Act & Assert
        assert error_codes.ERR_REPLY_001.code == "ERR-REPLY-001"

    def test_all_system_errors_accessible(self):
        """Test that all system errors are accessible."""
        # Arrange
        error_codes = ErrorCodes()

        # Act & Assert
        assert error_codes.ERR_SYSTEM_001.code == "ERR-SYSTEM-001"
        assert error_codes.ERR_SYSTEM_002.code == "ERR-SYSTEM-002"

    def test_error_titles_are_meaningful(self):
        """Test that all error codes have meaningful titles."""
        # Arrange
        error_codes = ErrorCodes()
        all_errors = error_codes.list_all()

        # Act & Assert
        for error in all_errors:
            assert error.title
            assert len(error.title) > 0
            assert error.title != "Unknown Error"

    def test_error_descriptions_are_present(self):
        """Test that all error codes have descriptions."""
        # Arrange
        error_codes = ErrorCodes()
        all_errors = error_codes.list_all()

        # Act & Assert
        for error in all_errors:
            assert error.description
            assert len(error.description) > 0

    def test_critical_errors_have_recovery_steps(self):
        """Test that critical errors have recovery steps defined."""
        # Arrange
        error_codes = ErrorCodes()
        all_errors = error_codes.list_all()

        # Act & Assert
        for error in all_errors:
            if error.severity == ErrorSeverity.CRITICAL:
                assert len(error.recovery_steps) > 0, \
                    f"Critical error {error.code} should have recovery steps"


# =============================================================================
# Edge Cases and Error Conditions
# =============================================================================

class TestEdgeCases:
    """Test suite for edge cases and error conditions."""

    def test_format_error_with_none_context(self):
        """Test formatting error with None context (should be treated as no context)."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-008",
            title="Test",
            description="Test",
            severity=ErrorSeverity.ERROR,
            recovery_steps=[]
        )

        # Act
        message = format_error_message(error, context=None)

        # Assert
        assert "❌ ERR-TEST-008" in message

    def test_error_code_with_special_characters_in_description(self):
        """Test error code with special characters in description."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-009",
            title="Test",
            description="Test with special chars: @#$%^&*()",
            severity=ErrorSeverity.ERROR,
            recovery_steps=[]
        )

        # Act
        message = format_error_message(error)

        # Assert
        assert "Test with special chars: @#$%^&*()" in message

    def test_error_code_with_multiline_description(self):
        """Test error code with multiline description."""
        # Arrange
        error = ErrorCode(
            code="ERR-TEST-010",
            title="Test",
            description="Line 1\nLine 2\nLine 3",
            severity=ErrorSeverity.ERROR,
            recovery_steps=[]
        )

        # Act
        message = format_error_message(error)

        # Assert
        assert "Line 1\nLine 2\nLine 3" in message

    def test_getattr_private_attribute_raises_error(self):
        """Test that accessing private attributes raises AttributeError."""
        # Arrange
        error_codes = ErrorCodes()

        # Act & Assert
        with pytest.raises(AttributeError):
            _ = error_codes._nonexistent_private_attr
