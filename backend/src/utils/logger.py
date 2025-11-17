"""
Centralized logging configuration and utilities.

This module provides application-wide logging:
- Configures Python logging with appropriate handlers and formatters
- Implements structured logging for better log parsing
- Supports multiple log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Provides file and console output handlers
- Implements log rotation for disk space management
- Includes contextual logging (request IDs, user IDs, etc.)
- Supports different log formats for development and production
- Integrates with monitoring systems (if configured)

Consistent logging across all modules enables effective debugging,
monitoring, and troubleshooting of the application.
"""

import logging
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler


class JSONFormatter(logging.Formatter):
    """
    Custom formatter that outputs log records as JSON.

    This formatter converts log records into structured JSON format,
    making them easier to parse and analyze with log aggregation tools.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record as a JSON string.

        Args:
            record: The log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields if present
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "platform"):
            log_data["platform"] = record.platform
        if hasattr(record, "channel_id"):
            log_data["channel_id"] = record.channel_id
        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id

        return json.dumps(log_data)


class ColoredConsoleFormatter(logging.Formatter):
    """
    Formatter that adds color codes for console output.

    Different log levels are displayed in different colors for better
    readability during development and debugging.
    """

    # ANSI color codes
    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record with color codes.

        Args:
            record: The log record to format

        Returns:
            Colored log string
        """
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            record.levelname = f"{self.COLORS[levelname]}{levelname}{self.RESET}"

        # Format the message
        formatted = super().format(record)

        # Reset levelname for subsequent handlers
        record.levelname = levelname

        return formatted


def setup_logger(
    name: str,
    level: str = "INFO",
    log_file: Optional[str] = None,
    json_format: bool = False,
    max_bytes: int = 10 * 1024 * 1024,  # 10MB
    backup_count: int = 5
) -> logging.Logger:
    """
    Set up a logger with console and optional file handlers.

    This function creates a logger instance configured with appropriate
    handlers and formatters. It supports both human-readable console output
    and structured JSON logging for production environments.

    Args:
        name: Logger name (typically __name__ of the calling module)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file. If None, only console logging is enabled
        json_format: If True, use JSON formatting for file logs
        max_bytes: Maximum size of log file before rotation (default: 10MB)
        backup_count: Number of backup files to keep (default: 5)

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger(__name__, level="DEBUG")
        >>> logger.info("Application started")
        >>> logger.error("An error occurred", extra={"user_id": 123})
    """
    # Create logger
    logger = logging.getLogger(name)

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Set log level
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    if level.upper() not in valid_levels:
        level = "INFO"
    logger.setLevel(getattr(logging, level.upper()))

    # Console handler with colored output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, level.upper()))

    # Use colored formatter for console
    console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_formatter = ColoredConsoleFormatter(
        console_format,
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler with rotation (optional)
    if log_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, level.upper()))

        # Use JSON formatter for file logs if requested
        if json_format:
            file_formatter = JSONFormatter()
        else:
            file_format = "%(asctime)s - %(name)s - %(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s"
            file_formatter = logging.Formatter(
                file_format,
                datefmt="%Y-%m-%d %H:%M:%S"
            )

        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to root logger
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get an existing logger or create a new one with default settings.

    This is a convenience function for getting loggers throughout the
    application. If a logger doesn't exist, it will be created with
    INFO level.

    Args:
        name: Logger name (typically __name__ of the calling module)

    Returns:
        Logger instance

    Example:
        >>> from utils.logger import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    # If logger already exists, return it
    if name in logging.Logger.manager.loggerDict:
        return logging.getLogger(name)

    # Otherwise create a new one with default settings
    return setup_logger(name)


# Example usage and testing
if __name__ == "__main__":
    # Test basic logging
    test_logger = setup_logger("test", level="DEBUG")
    test_logger.debug("This is a debug message")
    test_logger.info("This is an info message")
    test_logger.warning("This is a warning message")
    test_logger.error("This is an error message")
    test_logger.critical("This is a critical message")

    # Test with extra context
    test_logger.info("User action", extra={"user_id": 123, "platform": "discord"})

    # Test JSON logging to file
    json_logger = setup_logger(
        "test_json",
        level="INFO",
        log_file="/tmp/test.log",
        json_format=True
    )
    json_logger.info("JSON log entry", extra={"task_id": 456})

    print("\nLog file created at /tmp/test.log")
