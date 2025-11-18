"""
Centralized error handling system with error codes and formatted messages.

This module provides a comprehensive error handling framework:
- Standardized error codes with severity levels
- Formatted error messages with context and recovery steps
- Request ID generation for error tracking and debugging
- Structured error definitions loaded from JSON configuration
- Type-safe error handling with dataclasses and enums

The error system enables consistent error reporting across all modules,
making it easier to debug issues and provide helpful user feedback.
"""

import json
import uuid
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any


class ErrorSeverity(Enum):
    """
    Severity levels for error classification.

    These levels help categorize errors by their impact on system operation
    and determine appropriate handling and alerting strategies.

    Attributes:
        INFO: Informational messages, no action required (e.g., invalid usage)
        WARNING: Warning messages, operation continues (e.g., channel not in allowlist)
        ERROR: Error conditions, operation failed but system continues (e.g., failed to post reply)
        CRITICAL: Critical failures requiring immediate attention (e.g., database connection failed)
    """
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class ErrorCode:
    """
    Represents a single error code with all its metadata.

    This dataclass encapsulates all information about an error type,
    including its code, description, severity, and recovery guidance.

    Attributes:
        code: Unique error identifier (e.g., "ERR-USER-001")
        title: Short, human-readable error title
        description: Detailed explanation of what the error means
        severity: Error severity level (ErrorSeverity enum)
        recovery_steps: List of steps users can take to recover from the error
        example: Optional example or additional context for the error

    Example:
        >>> error = ErrorCode(
        ...     code="ERR-USER-001",
        ...     title="User Not Found",
        ...     description="The requested user does not exist",
        ...     severity=ErrorSeverity.ERROR,
        ...     recovery_steps=["Verify the user ID", "Try /start command"],
        ...     example="User with ID 123 not found"
        ... )
    """
    code: str
    title: str
    description: str
    severity: ErrorSeverity
    recovery_steps: List[str]
    example: Optional[str] = None


class ErrorCodes:
    """
    Registry of all application error codes.

    This class loads error definitions from a JSON configuration file and
    provides them as easily accessible attributes. It acts as a central
    repository for all error codes used throughout the application.

    The error codes are loaded once during initialization and cached for
    efficient access throughout the application lifecycle.

    Attributes:
        Error codes are dynamically loaded from error_codes.json and accessible
        as attributes with underscores replacing hyphens in the code names:
        - ERR_USER_001: User Not Found
        - ERR_USER_002: User Unauthorized
        - ERR_DISCORD_001: Discord Token Invalid
        - ERR_DISCORD_002: Discord Connection Failed
        - ERR_CHANNEL_001: Invalid Channel ID
        - ERR_CHANNEL_002: Channel Not in Allowlist
        - ERR_DB_001: Database Connection Failed
        - ERR_REPLY_001: Failed to Post Reply
        - ERR_SYSTEM_001: Invalid Usage
        - ERR_SYSTEM_002: Generic Error

    Example:
        >>> error_codes = ErrorCodes()
        >>> user_not_found = error_codes.ERR_USER_001
        >>> print(user_not_found.title)
        'User Not Found'
        >>> print(user_not_found.severity)
        ErrorSeverity.ERROR
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the error codes registry.

        Args:
            config_path: Optional path to error_codes.json. If None, uses the
                        default path relative to this module.

        Raises:
            FileNotFoundError: If the error codes configuration file is not found
            json.JSONDecodeError: If the configuration file is not valid JSON
        """
        if config_path is None:
            # Default to error_codes.json in the same directory as this module
            config_path = Path(__file__).parent / "error_codes.json"

        self._errors: Dict[str, ErrorCode] = {}
        self._load_errors(config_path)

    def _load_errors(self, config_path: Path) -> None:
        """
        Load error definitions from JSON configuration file.

        Args:
            config_path: Path to the error_codes.json file

        Raises:
            FileNotFoundError: If the configuration file is not found
            json.JSONDecodeError: If the file contains invalid JSON
        """
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)

        # Parse each error definition
        for code, error_data in config.get('errors', {}).items():
            # Convert severity string to enum
            severity_str = error_data.get('severity', 'ERROR')
            severity = ErrorSeverity[severity_str]

            # Create ErrorCode instance
            error_code = ErrorCode(
                code=code,
                title=error_data.get('title', 'Unknown Error'),
                description=error_data.get('description', ''),
                severity=severity,
                recovery_steps=error_data.get('recovery_steps', []),
                example=error_data.get('example')
            )

            # Store with both hyphenated and underscored keys
            self._errors[code] = error_code
            # Also store with underscores for attribute access
            attr_name = code.replace('-', '_')
            self._errors[attr_name] = error_code

    def __getattr__(self, name: str) -> ErrorCode:
        """
        Get an error code by attribute name.

        Args:
            name: Error code name (with underscores, e.g., ERR_USER_001)

        Returns:
            The corresponding ErrorCode instance

        Raises:
            AttributeError: If the error code is not found

        Example:
            >>> error_codes = ErrorCodes()
            >>> error = error_codes.ERR_USER_001
        """
        if name.startswith('_'):
            # Don't intercept private attributes
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

        if name in self._errors:
            return self._errors[name]

        # Try with hyphens
        hyphenated = name.replace('_', '-')
        if hyphenated in self._errors:
            return self._errors[hyphenated]

        raise AttributeError(f"Error code '{name}' not found in registry")

    def get(self, code: str, default: Optional[ErrorCode] = None) -> Optional[ErrorCode]:
        """
        Get an error code by its code string, with optional default.

        Args:
            code: Error code string (e.g., "ERR-USER-001" or "ERR_USER_001")
            default: Default value to return if code is not found

        Returns:
            The ErrorCode instance or default if not found

        Example:
            >>> error_codes = ErrorCodes()
            >>> error = error_codes.get("ERR-USER-001")
            >>> fallback = error_codes.get("INVALID", error_codes.ERR_SYSTEM_002)
        """
        # Try with original format
        if code in self._errors:
            return self._errors[code]

        # Try with underscores
        underscored = code.replace('-', '_')
        if underscored in self._errors:
            return self._errors[underscored]

        # Try with hyphens
        hyphenated = code.replace('_', '-')
        if hyphenated in self._errors:
            return self._errors[hyphenated]

        return default

    def list_all(self) -> List[ErrorCode]:
        """
        Get a list of all error codes in the registry.

        Returns:
            List of all ErrorCode instances

        Example:
            >>> error_codes = ErrorCodes()
            >>> all_errors = error_codes.list_all()
            >>> for error in all_errors:
            ...     print(f"{error.code}: {error.title}")
        """
        # Return only hyphenated versions (canonical form)
        return [
            error for code, error in self._errors.items()
            if '-' in code
        ]


def generate_request_id() -> str:
    """
    Generate a unique request ID for error tracking.

    Request IDs are used to correlate errors across logs, making it easier
    to trace issues through the system. They follow the format REQ-XXXXXXXX
    where X is a hex character.

    Returns:
        A unique request ID string in format "REQ-XXXXXXXX"

    Example:
        >>> req_id = generate_request_id()
        >>> print(req_id)
        'REQ-A1B2C3D4'
        >>> # Each call generates a new unique ID
        >>> req_id2 = generate_request_id()
        >>> assert req_id != req_id2
    """
    # Generate a UUID and take the first 8 characters of its hex representation
    unique_id = uuid.uuid4().hex[:8].upper()
    return f"REQ-{unique_id}"


def format_error_message(
    error_code: ErrorCode,
    context: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None
) -> str:
    """
    Format a comprehensive error message with all relevant information.

    This function creates user-friendly error messages that include:
    - Error code and title with visual indicator
    - Detailed description
    - Contextual information (if provided)
    - Step-by-step recovery instructions
    - Usage example (if available)
    - Unique request ID for tracking

    Args:
        error_code: The ErrorCode instance to format
        context: Optional dictionary of contextual information to include
                (e.g., {"user_id": 123, "channel_id": "456789"})
        request_id: Optional request ID. If None, a new one is generated

    Returns:
        Formatted error message string ready for display to users

    Example:
        >>> error_codes = ErrorCodes()
        >>> error = error_codes.ERR_USER_001
        >>> message = format_error_message(
        ...     error,
        ...     context={"telegram_id": 123456789},
        ...     request_id="REQ-ABC123"
        ... )
        >>> print(message)
        ❌ ERR-USER-001: User Not Found

        Reason: The requested user does not exist in the database...
        telegram_id: 123456789

        Recovery:
        1. Verify the user ID or Telegram user ID is correct
        2. Check if the user has completed /start command to register

        [Request ID: REQ-ABC123]
    """
    # Generate request ID if not provided
    if request_id is None:
        request_id = generate_request_id()

    # Build the message parts
    parts = []

    # Header with error code and title
    parts.append(f"❌ {error_code.code}: {error_code.title}")
    parts.append("")  # Empty line

    # Description
    parts.append(f"Reason: {error_code.description}")

    # Add context if provided
    if context:
        for key, value in context.items():
            parts.append(f"{key}: {value}")

    parts.append("")  # Empty line before recovery steps

    # Recovery steps
    if error_code.recovery_steps:
        parts.append("Recovery:")
        for i, step in enumerate(error_code.recovery_steps, 1):
            parts.append(f"{i}. {step}")
        parts.append("")  # Empty line after recovery steps

    # Example if available
    if error_code.example:
        parts.append(f"Example: {error_code.example}")
        parts.append("")  # Empty line after example

    # Request ID footer
    parts.append(f"[Request ID: {request_id}]")

    return "\n".join(parts)


# Singleton instance for application-wide use
_error_codes_instance: Optional[ErrorCodes] = None


def get_error_codes() -> ErrorCodes:
    """
    Get the singleton ErrorCodes instance.

    This function provides a convenient way to access error codes throughout
    the application without needing to pass around an ErrorCodes instance.
    The error codes are loaded once and cached for subsequent calls.

    Returns:
        The singleton ErrorCodes instance

    Example:
        >>> from utils.errors import get_error_codes, format_error_message
        >>> error_codes = get_error_codes()
        >>> error = error_codes.ERR_DISCORD_001
        >>> message = format_error_message(error)
    """
    global _error_codes_instance

    if _error_codes_instance is None:
        _error_codes_instance = ErrorCodes()

    return _error_codes_instance


# Example usage and testing
if __name__ == "__main__":
    # Initialize error codes
    print("=== Error Handling System Demo ===\n")

    error_codes = ErrorCodes()

    # Example 1: User not found error
    print("Example 1: User Not Found")
    print("-" * 50)
    error = error_codes.ERR_USER_001
    message = format_error_message(
        error,
        context={"telegram_id": 123456789, "attempted_action": "setup_discord"}
    )
    print(message)
    print("\n")

    # Example 2: Discord connection failed
    print("Example 2: Discord Connection Failed")
    print("-" * 50)
    error = error_codes.ERR_DISCORD_002
    message = format_error_message(
        error,
        context={"gateway_url": "wss://gateway.discord.gg", "error_code": "4004"}
    )
    print(message)
    print("\n")

    # Example 3: Channel not in allowlist
    print("Example 3: Channel Not in Allowlist")
    print("-" * 50)
    error = error_codes.ERR_CHANNEL_002
    message = format_error_message(
        error,
        context={"channel_id": "1234567890123456789", "server": "My Discord Server"}
    )
    print(message)
    print("\n")

    # Example 4: List all error codes
    print("Example 4: All Available Error Codes")
    print("-" * 50)
    all_errors = error_codes.list_all()
    for err in all_errors:
        severity_icon = {
            ErrorSeverity.INFO: "ℹ️",
            ErrorSeverity.WARNING: "⚠️",
            ErrorSeverity.ERROR: "❌",
            ErrorSeverity.CRITICAL: "🔴"
        }.get(err.severity, "")
        print(f"{severity_icon} {err.code}: {err.title} [{err.severity.value}]")
    print("\n")

    # Example 5: Generate request IDs
    print("Example 5: Request ID Generation")
    print("-" * 50)
    for i in range(5):
        req_id = generate_request_id()
        print(f"Request {i+1}: {req_id}")
    print("\n")

    # Example 6: Using get() method with fallback
    print("Example 6: Safe Error Retrieval")
    print("-" * 50)
    # Valid error code
    error = error_codes.get("ERR-USER-001")
    print(f"Found: {error.code if error else 'None'}")

    # Invalid error code with fallback
    error = error_codes.get("ERR-INVALID-999", error_codes.ERR_SYSTEM_002)
    print(f"Fallback: {error.code}")
    print("\n")

    # Example 7: Error severity filtering
    print("Example 7: Critical Errors Only")
    print("-" * 50)
    critical_errors = [
        err for err in error_codes.list_all()
        if err.severity == ErrorSeverity.CRITICAL
    ]
    for err in critical_errors:
        print(f"🔴 {err.code}: {err.title}")
