"""
Application configuration management.

This module handles:
- Environment variable loading and validation
- Configuration for Discord (bot token, guild IDs, channel IDs)
- Configuration for Telegram (bot token, user IDs)
- Database connection settings (PostgreSQL host, port, credentials)
- Encryption keys and security settings
- Application behavior settings (context window size, timeouts, etc.)

Configuration is loaded from environment variables with appropriate defaults
and validation to ensure the application starts with valid settings.
"""

import os
import sys
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection configuration."""

    host: str
    port: int
    name: str
    user: str
    password: str

    @property
    def connection_string(self) -> str:
        """Return PostgreSQL connection string."""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""

    bot_token: str
    moderator_user_id: int
    alert_chat_id: int


@dataclass
class DiscordConfig:
    """Discord configuration."""

    user_token: str
    super_properties: Optional[dict] = None

    def __post_init__(self):
        """Validate Discord configuration."""
        if not self.user_token:
            raise ValueError("DISCORD_USER_TOKEN is required")

        # Parse super properties if provided as JSON string
        if isinstance(self.super_properties, str):
            try:
                import json
                self.super_properties = json.loads(self.super_properties)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid DISCORD_SUPER_PROPERTIES JSON: {e}")


@dataclass
class LLMConfig:
    """LLM provider configuration (v0.2+)."""

    provider: str
    model: str
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    def __post_init__(self):
        """Validate LLM configuration."""
        if self.provider == "openai" and not self.openai_api_key:
            raise ValueError(
                "OPENAI_API_KEY is required when LLM_PROVIDER is set to 'openai'"
            )
        elif self.provider == "anthropic" and not self.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER is set to 'anthropic'"
            )

        if self.provider not in ["openai", "anthropic"]:
            raise ValueError(
                f"Invalid LLM_PROVIDER: {self.provider}. Must be 'openai' or 'anthropic'"
            )


@dataclass
class RedisConfig:
    """Redis configuration (v0.2+)."""

    host: str = "redis"
    port: int = 6379
    password: Optional[str] = None


@dataclass
class MetricsConfig:
    """Metrics configuration (v1.0+)."""

    enabled: bool = False
    port: int = 8000  # Same port as health check by default
    update_interval: int = 60  # Gauge update interval in seconds


@dataclass
class Config:
    """Main application configuration."""

    # Database
    database: DatabaseConfig

    # Telegram
    telegram: TelegramConfig

    # Security
    encryption_key: str

    # Discord (optional)
    discord: Optional[DiscordConfig] = None

    # LLM (optional, for v0.2+)
    llm: Optional[LLMConfig] = None

    # Redis (optional, for v0.2+)
    redis: Optional[RedisConfig] = None

    # Metrics (optional, for v1.0+)
    metrics: Optional[MetricsConfig] = None

    # Logging
    log_level: str = "INFO"

    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.log_level == "DEBUG"

    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.

        Raises:
            ValueError: If required environment variables are missing or invalid.

        Returns:
            Config: Fully validated configuration object.
        """
        # Collect missing required variables
        missing_vars = []

        # Database configuration (required)
        db_name = os.getenv("DB_NAME")
        db_user = os.getenv("DB_USER")
        db_password = os.getenv("DB_PASSWORD")
        db_host = os.getenv("DB_HOST", "db")
        db_port = os.getenv("DB_PORT", "5432")

        if not db_name:
            missing_vars.append("DB_NAME")
        if not db_user:
            missing_vars.append("DB_USER")
        if not db_password:
            missing_vars.append("DB_PASSWORD")

        # Telegram configuration (required)
        telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        moderator_tg_user_id = os.getenv("MODERATOR_TG_USER_ID")
        alert_chat_id = os.getenv("ALERT_CHAT_ID")

        if not telegram_bot_token:
            missing_vars.append("TELEGRAM_BOT_TOKEN")
        if not moderator_tg_user_id:
            missing_vars.append("MODERATOR_TG_USER_ID")
        if not alert_chat_id:
            missing_vars.append("ALERT_CHAT_ID")

        # Encryption key (required)
        encryption_key = os.getenv("ENCRYPTION_KEY")
        if not encryption_key:
            missing_vars.append("ENCRYPTION_KEY")

        # Check for missing required variables
        if missing_vars:
            error_msg = (
                f"\n{'='*60}\n"
                f"ERROR: Missing required environment variables!\n"
                f"{'='*60}\n\n"
                f"The following required environment variables are not set:\n"
            )
            for var in missing_vars:
                error_msg += f"  - {var}\n"

            error_msg += (
                f"\nPlease set these variables in your .env file or environment.\n"
                f"See .env.example for a template with all required variables.\n"
                f"{'='*60}\n"
            )
            raise ValueError(error_msg)

        # Validate and convert types
        try:
            db_port_int = int(db_port)
        except ValueError:
            raise ValueError(
                f"Invalid DB_PORT value: {db_port}. Must be a valid integer."
            )

        try:
            moderator_user_id_int = int(moderator_tg_user_id)
        except ValueError:
            raise ValueError(
                f"Invalid MODERATOR_TG_USER_ID value: {moderator_tg_user_id}. "
                f"Must be a valid integer (your Telegram user ID)."
            )

        try:
            alert_chat_id_int = int(alert_chat_id)
        except ValueError:
            raise ValueError(
                f"Invalid ALERT_CHAT_ID value: {alert_chat_id}. "
                f"Must be a valid integer (Telegram chat ID)."
            )

        # Create database config
        database = DatabaseConfig(
            host=db_host,
            port=db_port_int,
            name=db_name,
            user=db_user,
            password=db_password
        )

        # Create Telegram config
        telegram = TelegramConfig(
            bot_token=telegram_bot_token,
            moderator_user_id=moderator_user_id_int,
            alert_chat_id=alert_chat_id_int
        )

        # Discord configuration (optional)
        discord_config = None
        discord_user_token = os.getenv("DISCORD_USER_TOKEN")
        if discord_user_token:
            discord_super_props = os.getenv("DISCORD_SUPER_PROPERTIES")
            try:
                discord_config = DiscordConfig(
                    user_token=discord_user_token,
                    super_properties=discord_super_props
                )
            except ValueError as e:
                print(f"Warning: Discord configuration error: {e}", file=sys.stderr)
                print("Discord integration will be disabled.", file=sys.stderr)

        # LLM configuration (optional, for v0.2+)
        llm_config = None
        llm_provider = os.getenv("LLM_PROVIDER", "openai")
        if llm_provider:
            llm_model = os.getenv("LLM_MODEL", "gpt-4-turbo")
            openai_api_key = os.getenv("OPENAI_API_KEY")
            anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

            try:
                llm_config = LLMConfig(
                    provider=llm_provider,
                    model=llm_model,
                    openai_api_key=openai_api_key,
                    anthropic_api_key=anthropic_api_key
                )
            except ValueError as e:
                print(f"Warning: LLM configuration error: {e}", file=sys.stderr)
                print("LLM features will be disabled.", file=sys.stderr)

        # Redis configuration (optional, for v0.2+)
        redis_config = None
        redis_host = os.getenv("REDIS_HOST")
        if redis_host:
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_password = os.getenv("REDIS_PASSWORD")
            redis_config = RedisConfig(
                host=redis_host,
                port=redis_port,
                password=redis_password if redis_password else None
            )

        # Logging level
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        valid_log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if log_level not in valid_log_levels:
            print(
                f"Warning: Invalid LOG_LEVEL '{log_level}'. "
                f"Using 'INFO' instead. Valid options: {', '.join(valid_log_levels)}",
                file=sys.stderr
            )
            log_level = "INFO"

        # Metrics configuration (optional, for v1.0+)
        metrics_config = None
        metrics_enabled = os.getenv("METRICS_ENABLED", "false").lower() in ["true", "1", "yes"]
        if metrics_enabled:
            metrics_port = int(os.getenv("METRICS_PORT", os.getenv("HEALTH_CHECK_PORT", "8000")))
            metrics_update_interval = int(os.getenv("METRICS_UPDATE_INTERVAL", "60"))
            metrics_config = MetricsConfig(
                enabled=True,
                port=metrics_port,
                update_interval=metrics_update_interval
            )
            print(f"Metrics enabled on port {metrics_port}", file=sys.stderr)

        return cls(
            database=database,
            telegram=telegram,
            discord=discord_config,
            encryption_key=encryption_key,
            llm=llm_config,
            redis=redis_config,
            metrics=metrics_config,
            log_level=log_level
        )


# Global configuration instance
# This will be initialized when the module is imported
try:
    config = Config.from_env()
except ValueError as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)


def get_config() -> Config:
    """
    Get the global configuration instance.

    Returns:
        Config: The application configuration.
    """
    return config


# For convenience, export commonly used config sections
__all__ = [
    "Config",
    "DatabaseConfig",
    "TelegramConfig",
    "DiscordConfig",
    "LLMConfig",
    "RedisConfig",
    "MetricsConfig",
    "config",
    "get_config"
]
