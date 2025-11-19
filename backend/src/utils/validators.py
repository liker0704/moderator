"""
Input Validation Utilities

This module provides comprehensive input validation functions to prevent
injection attacks, ensure data integrity, and enforce security best practices.

All validation functions follow a consistent pattern:
- Return the validated/sanitized value on success
- Raise ValueError with descriptive message on validation failure
- Include optional parameters for customizing validation rules

Security considerations:
- Validate all user input before processing
- Sanitize data before storage or display
- Use whitelist validation (allow known-good) over blacklist (block known-bad)
- Rate limit sensitive operations
- Log validation failures for security monitoring
"""

import re
import unicodedata
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict
import asyncio


class ValidationError(ValueError):
    """
    Custom exception for validation errors.

    Extends ValueError with additional context for better error reporting
    and security logging.
    """

    def __init__(self, message: str, field: Optional[str] = None, value: Any = None):
        """
        Initialize ValidationError.

        Args:
            message: Human-readable error message
            field: Name of the field that failed validation (optional)
            value: The invalid value (optional, should not include sensitive data)
        """
        self.field = field
        self.value = value
        super().__init__(message)


# =============================================================================
# Discord/Telegram ID Validation
# =============================================================================

def validate_discord_message_id(message_id: str) -> str:
    """
    Validate Discord message ID format.

    Discord message IDs are Snowflakes: 64-bit integers represented as strings.

    Args:
        message_id: Message ID to validate

    Returns:
        Validated message ID (as string)

    Raises:
        ValidationError: If message ID format is invalid

    Example:
        >>> validate_discord_message_id("1234567890123456789")
        '1234567890123456789'
        >>> validate_discord_message_id("invalid")
        ValidationError: Invalid Discord message ID format
    """
    if not message_id:
        raise ValidationError("Message ID cannot be empty", field="message_id")

    # Discord Snowflakes are numeric strings, typically 17-20 digits
    if not re.match(r'^\d{17,20}$', message_id):
        raise ValidationError(
            "Invalid Discord message ID format. Must be a 17-20 digit number.",
            field="message_id",
            value=message_id[:20]  # Truncate for safety
        )

    return message_id


def validate_discord_channel_id(channel_id: str) -> str:
    """
    Validate Discord channel ID format.

    Args:
        channel_id: Channel ID to validate

    Returns:
        Validated channel ID (as string)

    Raises:
        ValidationError: If channel ID format is invalid

    Example:
        >>> validate_discord_channel_id("987654321098765432")
        '987654321098765432'
    """
    if not channel_id:
        raise ValidationError("Channel ID cannot be empty", field="channel_id")

    if not re.match(r'^\d{17,20}$', channel_id):
        raise ValidationError(
            "Invalid Discord channel ID format. Must be a 17-20 digit number.",
            field="channel_id",
            value=channel_id[:20]
        )

    return channel_id


def validate_discord_server_id(server_id: str) -> str:
    """
    Validate Discord server (guild) ID format.

    Args:
        server_id: Server ID to validate

    Returns:
        Validated server ID (as string)

    Raises:
        ValidationError: If server ID format is invalid

    Example:
        >>> validate_discord_server_id("123456789012345678")
        '123456789012345678'
    """
    if not server_id:
        raise ValidationError("Server ID cannot be empty", field="server_id")

    if not re.match(r'^\d{17,20}$', server_id):
        raise ValidationError(
            "Invalid Discord server ID format. Must be a 17-20 digit number.",
            field="server_id",
            value=server_id[:20]
        )

    return server_id


def validate_telegram_message_id(message_id: int) -> int:
    """
    Validate Telegram message ID.

    Telegram message IDs are positive integers.

    Args:
        message_id: Message ID to validate

    Returns:
        Validated message ID

    Raises:
        ValidationError: If message ID is invalid

    Example:
        >>> validate_telegram_message_id(12345)
        12345
    """
    if not isinstance(message_id, int):
        raise ValidationError(
            "Telegram message ID must be an integer",
            field="message_id",
            value=type(message_id).__name__
        )

    if message_id <= 0:
        raise ValidationError(
            "Telegram message ID must be positive",
            field="message_id",
            value=message_id
        )

    return message_id


# =============================================================================
# Text Input Sanitization
# =============================================================================

def sanitize_text_input(
    text: str,
    max_length: Optional[int] = None,
    remove_control_chars: bool = True,
    normalize_unicode: bool = True,
    strip_whitespace: bool = True,
) -> str:
    """
    Sanitize text input by removing control characters and normalizing.

    Args:
        text: Input text to sanitize
        max_length: Maximum allowed length (optional)
        remove_control_chars: Remove control characters (default: True)
        normalize_unicode: Normalize Unicode to NFC form (default: True)
        strip_whitespace: Strip leading/trailing whitespace (default: True)

    Returns:
        Sanitized text

    Raises:
        ValidationError: If text exceeds max_length

    Example:
        >>> sanitize_text_input("Hello\\x00World", remove_control_chars=True)
        'HelloWorld'
        >>> sanitize_text_input("  Test  ", strip_whitespace=True)
        'Test'
    """
    if not isinstance(text, str):
        raise ValidationError(
            "Input must be a string",
            field="text",
            value=type(text).__name__
        )

    # Strip whitespace if requested
    if strip_whitespace:
        text = text.strip()

    # Normalize Unicode (prevent homograph attacks, normalize representations)
    if normalize_unicode:
        text = unicodedata.normalize('NFC', text)

    # Remove control characters (except newlines and tabs)
    if remove_control_chars:
        # Remove characters in categories: Cc (control), Cf (format), except \n, \r, \t
        text = ''.join(
            char for char in text
            if not unicodedata.category(char) in ('Cc', 'Cf')
            or char in ('\n', '\r', '\t')
        )

    # Check length
    if max_length is not None and len(text) > max_length:
        raise ValidationError(
            f"Text exceeds maximum length of {max_length} characters",
            field="text",
            value=f"{len(text)} characters"
        )

    return text


def validate_template_name(name: str) -> str:
    """
    Validate template name (alphanumeric + underscore + hyphen only).

    Template names must be safe for use in file systems and URLs.

    Args:
        name: Template name to validate

    Returns:
        Validated template name

    Raises:
        ValidationError: If name format is invalid

    Example:
        >>> validate_template_name("my_template_v1")
        'my_template_v1'
        >>> validate_template_name("invalid name!")
        ValidationError: Invalid template name format
    """
    if not name:
        raise ValidationError("Template name cannot be empty", field="name")

    # Only allow alphanumeric, underscore, and hyphen
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        raise ValidationError(
            "Template name must contain only letters, numbers, underscores, and hyphens",
            field="name",
            value=name[:50]
        )

    # Length check
    if len(name) < 1 or len(name) > 64:
        raise ValidationError(
            "Template name must be 1-64 characters long",
            field="name",
            value=f"{len(name)} characters"
        )

    return name


# =============================================================================
# SQL Injection Prevention
# =============================================================================

def validate_search_query(
    query: str,
    max_length: int = 500,
    allow_wildcards: bool = True,
) -> str:
    """
    Validate and sanitize search query to prevent SQL injection.

    Note: This provides basic validation, but always use parameterized queries
    for database operations.

    Args:
        query: Search query to validate
        max_length: Maximum query length (default: 500)
        allow_wildcards: Allow % and _ wildcards (default: True)

    Returns:
        Validated and sanitized query

    Raises:
        ValidationError: If query is invalid or suspicious

    Example:
        >>> validate_search_query("search term")
        'search term'
        >>> validate_search_query("'; DROP TABLE users; --")
        ValidationError: Query contains prohibited characters
    """
    if not query:
        raise ValidationError("Search query cannot be empty", field="query")

    # Sanitize basic input
    query = sanitize_text_input(query, max_length=max_length)

    # Check for suspicious SQL keywords (basic check, not exhaustive)
    # Note: This is defense in depth; parameterized queries are the primary defense
    sql_keywords = [
        r'\bDROP\b', r'\bDELETE\b', r'\bUPDATE\b', r'\bINSERT\b',
        r'\bEXEC\b', r'\bEXECUTE\b', r'\bUNION\b', r'\bSELECT\b.*\bFROM\b',
        r'--', r'/\*', r'\*/', r';.*--', r'xp_cmdshell'
    ]

    for pattern in sql_keywords:
        if re.search(pattern, query, re.IGNORECASE):
            raise ValidationError(
                "Query contains prohibited SQL keywords or patterns",
                field="query",
                value=query[:100]
            )

    # Check for null bytes (can bypass security checks)
    if '\x00' in query:
        raise ValidationError(
            "Query contains null bytes",
            field="query"
        )

    # If wildcards not allowed, reject them
    if not allow_wildcards and ('%' in query or '_' in query):
        raise ValidationError(
            "Wildcards (% and _) are not allowed in this query",
            field="query"
        )

    return query


# =============================================================================
# Rate Limiting
# =============================================================================

class RateLimiter:
    """
    Simple in-memory rate limiter for preventing abuse.

    Uses token bucket algorithm with per-identifier tracking.

    Note: For production, use Redis-based rate limiting for distributed systems.
    """

    def __init__(
        self,
        max_requests: int = 10,
        window_seconds: int = 60,
        cleanup_interval: int = 300,
    ):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum requests allowed per window (default: 10)
            window_seconds: Time window in seconds (default: 60)
            cleanup_interval: Cleanup old entries every N seconds (default: 300)
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.cleanup_interval = cleanup_interval

        # Storage: {identifier: [timestamp1, timestamp2, ...]}
        self._requests: Dict[str, List[datetime]] = defaultdict(list)
        self._last_cleanup = datetime.utcnow()

    def _cleanup(self):
        """Remove old request timestamps to prevent memory bloat."""
        now = datetime.utcnow()

        # Only cleanup periodically
        if (now - self._last_cleanup).total_seconds() < self.cleanup_interval:
            return

        cutoff = now - timedelta(seconds=self.window_seconds * 2)

        # Remove old timestamps
        for identifier in list(self._requests.keys()):
            self._requests[identifier] = [
                ts for ts in self._requests[identifier]
                if ts > cutoff
            ]

            # Remove identifier if no recent requests
            if not self._requests[identifier]:
                del self._requests[identifier]

        self._last_cleanup = now

    def check_rate_limit(
        self,
        identifier: str,
        raise_on_limit: bool = True,
    ) -> bool:
        """
        Check if request should be allowed under rate limit.

        Args:
            identifier: Unique identifier (e.g., user_id, ip_address)
            raise_on_limit: Raise ValidationError if limit exceeded (default: True)

        Returns:
            True if request is allowed, False if rate limited

        Raises:
            ValidationError: If rate limit exceeded and raise_on_limit=True

        Example:
            >>> limiter = RateLimiter(max_requests=5, window_seconds=60)
            >>> limiter.check_rate_limit("user_123")
            True
            >>> # After 5 requests...
            >>> limiter.check_rate_limit("user_123")
            ValidationError: Rate limit exceeded
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)

        # Cleanup periodically
        self._cleanup()

        # Get recent requests for this identifier
        recent_requests = [
            ts for ts in self._requests[identifier]
            if ts > cutoff
        ]

        # Check if limit exceeded
        if len(recent_requests) >= self.max_requests:
            if raise_on_limit:
                raise ValidationError(
                    f"Rate limit exceeded. Maximum {self.max_requests} requests "
                    f"per {self.window_seconds} seconds.",
                    field="rate_limit",
                    value=identifier
                )
            return False

        # Allow request and record timestamp
        self._requests[identifier].append(now)
        return True

    def get_remaining_requests(self, identifier: str) -> int:
        """
        Get number of remaining requests in current window.

        Args:
            identifier: Unique identifier

        Returns:
            Number of remaining requests allowed
        """
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.window_seconds)

        recent_requests = [
            ts for ts in self._requests[identifier]
            if ts > cutoff
        ]

        return max(0, self.max_requests - len(recent_requests))

    def reset(self, identifier: str):
        """
        Reset rate limit for a specific identifier.

        Args:
            identifier: Unique identifier to reset
        """
        if identifier in self._requests:
            del self._requests[identifier]


# Global rate limiters for different operations
# These can be configured based on sensitivity of the operation

# Search rate limiter: 20 searches per minute per user
search_rate_limiter = RateLimiter(max_requests=20, window_seconds=60)

# Export rate limiter: 3 exports per hour per user (resource-intensive)
export_rate_limiter = RateLimiter(max_requests=3, window_seconds=3600)

# API rate limiter: 100 requests per minute per IP
api_rate_limiter = RateLimiter(max_requests=100, window_seconds=60)

# Auth rate limiter: 5 attempts per 15 minutes per IP (prevent brute force)
auth_rate_limiter = RateLimiter(max_requests=5, window_seconds=900)


# =============================================================================
# Additional Validation Functions
# =============================================================================

def validate_email(email: str) -> str:
    """
    Basic email validation.

    Args:
        email: Email address to validate

    Returns:
        Validated email (lowercased)

    Raises:
        ValidationError: If email format is invalid
    """
    if not email:
        raise ValidationError("Email cannot be empty", field="email")

    # Basic regex for email validation (not RFC-compliant, but practical)
    email_regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'

    if not re.match(email_regex, email):
        raise ValidationError(
            "Invalid email format",
            field="email",
            value=email[:50]
        )

    return email.lower()


def validate_url(url: str, allowed_schemes: Optional[List[str]] = None) -> str:
    """
    Validate URL format and scheme.

    Args:
        url: URL to validate
        allowed_schemes: List of allowed schemes (default: ['http', 'https'])

    Returns:
        Validated URL

    Raises:
        ValidationError: If URL format or scheme is invalid
    """
    if not url:
        raise ValidationError("URL cannot be empty", field="url")

    if allowed_schemes is None:
        allowed_schemes = ['http', 'https']

    # Basic URL validation
    url_regex = r'^(https?|ftp)://[^\s/$.?#].[^\s]*$'

    if not re.match(url_regex, url, re.IGNORECASE):
        raise ValidationError(
            "Invalid URL format",
            field="url",
            value=url[:100]
        )

    # Check scheme
    scheme = url.split('://')[0].lower()
    if scheme not in allowed_schemes:
        raise ValidationError(
            f"URL scheme must be one of: {', '.join(allowed_schemes)}",
            field="url",
            value=scheme
        )

    return url


def validate_json_string(json_str: str, max_size: int = 10000) -> str:
    """
    Validate JSON string can be parsed and isn't too large.

    Args:
        json_str: JSON string to validate
        max_size: Maximum size in bytes (default: 10KB)

    Returns:
        Validated JSON string

    Raises:
        ValidationError: If JSON is invalid or too large
    """
    import json

    if not json_str:
        raise ValidationError("JSON string cannot be empty", field="json")

    # Check size
    if len(json_str.encode('utf-8')) > max_size:
        raise ValidationError(
            f"JSON exceeds maximum size of {max_size} bytes",
            field="json",
            value=f"{len(json_str.encode('utf-8'))} bytes"
        )

    # Try to parse
    try:
        json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValidationError(
            f"Invalid JSON: {str(e)}",
            field="json"
        )

    return json_str


def validate_integer_range(
    value: int,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
    field_name: str = "value",
) -> int:
    """
    Validate integer is within specified range.

    Args:
        value: Integer value to validate
        min_value: Minimum allowed value (optional)
        max_value: Maximum allowed value (optional)
        field_name: Name of field for error messages

    Returns:
        Validated integer

    Raises:
        ValidationError: If value is out of range
    """
    if not isinstance(value, int):
        raise ValidationError(
            f"{field_name} must be an integer",
            field=field_name,
            value=type(value).__name__
        )

    if min_value is not None and value < min_value:
        raise ValidationError(
            f"{field_name} must be at least {min_value}",
            field=field_name,
            value=value
        )

    if max_value is not None and value > max_value:
        raise ValidationError(
            f"{field_name} must be at most {max_value}",
            field=field_name,
            value=value
        )

    return value


# =============================================================================
# Export
# =============================================================================

__all__ = [
    'ValidationError',
    'validate_discord_message_id',
    'validate_discord_channel_id',
    'validate_discord_server_id',
    'validate_telegram_message_id',
    'sanitize_text_input',
    'validate_template_name',
    'validate_search_query',
    'RateLimiter',
    'search_rate_limiter',
    'export_rate_limiter',
    'api_rate_limiter',
    'auth_rate_limiter',
    'validate_email',
    'validate_url',
    'validate_json_string',
    'validate_integer_range',
]
