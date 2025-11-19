"""
Database package for PostgreSQL connection and models.

This package provides:
- SQLAlchemy ORM models for all database tables
- Database connection management with pooling
- Encryption utilities for sensitive data
- Session management and transaction handling

Usage:
    from database import init_db, session_scope, User, Task

    # Initialize database
    init_db()

    # Use session scope for transactions
    with session_scope() as session:
        user = session.query(User).first()
        print(user.username)
"""

# Import models
from .models import (
    AuditLog,
    Attachment,
    Base,
    ChannelsAllowlist,
    DiscordConnection,
    Message,
    PlatformAccount,
    Reply,
    Settings,
    Task,
    User,
)

# Import connection functions
from .connection import (
    DatabaseConnection,
    close_db,
    get_db,
    get_session,
    init_db,
    session_scope,
)

# Import encryption functions
from .encryption import (
    EncryptionError,
    EncryptionService,
    decrypt,
    decrypt_token,
    encrypt,
    encrypt_token,
    generate_encryption_key,
    get_encryption_service,
    init_encryption,
)

__all__ = [
    # Models
    "Base",
    "User",
    "PlatformAccount",
    "DiscordConnection",
    "ChannelsAllowlist",
    "Message",
    "Attachment",
    "Task",
    "Reply",
    "Settings",
    "AuditLog",
    # Connection
    "DatabaseConnection",
    "init_db",
    "get_db",
    "get_session",
    "session_scope",
    "close_db",
    # Encryption
    "EncryptionService",
    "EncryptionError",
    "init_encryption",
    "get_encryption_service",
    "encrypt",
    "decrypt",
    "encrypt_token",
    "decrypt_token",
    "generate_encryption_key",
]
