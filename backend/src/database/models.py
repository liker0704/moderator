"""
SQLAlchemy ORM models for the moderator system.

This module defines the complete database schema using SQLAlchemy 2.0 declarative style:

Models:
1. User - System users (moderators)
2. PlatformAccount - Platform-specific accounts (Discord, Telegram)
3. DiscordConnection - Discord Gateway connection information
4. ChannelsAllowlist - Allowed channels for message reception
5. Message - Messages from various platforms
6. Attachment - Message attachments (images, links, videos)
7. Task - Moderator tasks (incoming messages requiring response)
8. Reply - Moderator replies to tasks
9. Settings - User settings (DND, reminders, etc.)
10. AuditLog - System audit log for all actions

All models include proper relationships, indexes, and cascade settings as per schema.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

# Create declarative base
Base = declarative_base()


class User(Base):
    """
    System users table (moderators).

    Stores information about users of the moderation system.
    In MVP, there is only one moderator.
    """
    __tablename__ = "users"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    tg_user_id = Column(BigInteger, nullable=False, unique=True, index=True)
    username = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    platform_accounts = relationship(
        "PlatformAccount",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    discord_connections = relationship(
        "DiscordConnection",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    tasks = relationship(
        "Task",
        back_populates="assignee",
        cascade="all, delete-orphan"
    )
    settings = relationship(
        "Settings",
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False
    )
    audit_logs = relationship(
        "AuditLog",
        back_populates="user"
    )

    def __repr__(self):
        return f"<User(id={self.id}, tg_user_id={self.tg_user_id}, username={self.username})>"


class PlatformAccount(Base):
    """
    Platform-specific accounts (Discord, Telegram).

    Links users to their accounts on various platforms with encrypted metadata.
    """
    __tablename__ = "platform_accounts"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    platform = Column(String(50), nullable=False, index=True)  # 'discord' | 'telegram'
    external_id = Column(String(255), nullable=False)  # Discord user ID or Telegram ID
    meta_encrypted = Column(Text, nullable=True)  # Encrypted metadata (JSON)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint("platform", "external_id", name="uq_platform_external_id"),
    )

    # Relationships
    user = relationship("User", back_populates="platform_accounts")

    def __repr__(self):
        return f"<PlatformAccount(id={self.id}, platform={self.platform}, external_id={self.external_id})>"


class DiscordConnection(Base):
    """
    Discord Gateway connection information.

    Stores encrypted user tokens and connection status for Discord Gateway integration.
    """
    __tablename__ = "discord_connection"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_token_encrypted = Column(Text, nullable=False)  # Encrypted Discord User Token
    super_properties = Column(Text, nullable=True)  # JSON with super properties
    session_id = Column(String(255), nullable=True)
    last_connected_at = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="disconnected", index=True)  # 'connected' | 'disconnected' | 'error'
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="discord_connections")

    def __repr__(self):
        return f"<DiscordConnection(id={self.id}, user_id={self.user_id}, status={self.status})>"


class ChannelsAllowlist(Base):
    """
    Allowed channels for message reception.

    Defines which channels are monitored for incoming messages with optional thread filters.
    """
    __tablename__ = "channels_allowlist"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, index=True)  # 'discord' | 'telegram'
    server_id = Column(String(255), nullable=True)  # Discord guild ID (NULL for Telegram)
    channel_id = Column(String(255), nullable=False, index=True)
    thread_filter_json = Column(Text, nullable=True)  # JSON with thread filters
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Constraints
    __table_args__ = (
        UniqueConstraint("platform", "server_id", "channel_id", name="uq_platform_server_channel"),
    )

    def __repr__(self):
        return f"<ChannelsAllowlist(id={self.id}, platform={self.platform}, channel_id={self.channel_id}, enabled={self.enabled})>"


class Message(Base):
    """
    Messages from various platforms.

    Stores messages received from Discord, Telegram, and other platforms with metadata.
    """
    __tablename__ = "messages"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    platform = Column(String(50), nullable=False, index=True)
    ext_message_id = Column(String(255), nullable=False)  # External platform message ID
    server_id = Column(String(255), nullable=True)  # Discord guild ID
    channel_id = Column(String(255), nullable=False, index=True)
    thread_id = Column(String(255), nullable=True)  # Thread ID (optional)
    author_id = Column(String(255), nullable=False, index=True)
    author_name = Column(String(255), nullable=True)
    content = Column(Text, nullable=True)
    has_image = Column(Boolean, nullable=False, default=False)
    context_ref = Column(BigInteger, nullable=True, index=True)  # Reference to parent message for context
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    platform_created_at = Column(DateTime, nullable=True)  # Timestamp from the platform

    # Constraints
    __table_args__ = (
        UniqueConstraint("platform", "ext_message_id", name="uq_platform_ext_message_id"),
    )

    # Relationships
    attachments = relationship(
        "Attachment",
        back_populates="message",
        cascade="all, delete-orphan"
    )
    tasks = relationship(
        "Task",
        back_populates="source_message",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Message(id={self.id}, platform={self.platform}, ext_message_id={self.ext_message_id}, author_name={self.author_name})>"


class Attachment(Base):
    """
    Message attachments (images, links, videos, files).

    Stores references to files and media attached to messages.
    """
    __tablename__ = "attachments"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(50), nullable=False, index=True)  # 'image' | 'link' | 'video' | 'file'
    ref = Column(Text, nullable=False)  # URL or file path
    meta = Column(Text, nullable=True)  # JSON metadata (size, type, dimensions, etc.)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    message = relationship("Message", back_populates="attachments")

    def __repr__(self):
        return f"<Attachment(id={self.id}, message_id={self.message_id}, kind={self.kind})>"


class Task(Base):
    """
    Moderator tasks (incoming messages requiring response).

    Represents messages that need moderator attention and response.
    """
    __tablename__ = "tasks"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    source_message_id = Column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="open", index=True)  # 'open' | 'answered' | 'muted' | 'error'
    assignee_user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tg_card_message_id = Column(BigInteger, nullable=True)  # Telegram card message ID
    error_message = Column(Text, nullable=True)  # Error message if status = 'error'
    reminder_count = Column(Integer, nullable=False, default=0)  # Number of reminders sent
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    answered_at = Column(DateTime, nullable=True)  # Timestamp of response

    # Relationships
    source_message = relationship("Message", back_populates="tasks")
    assignee = relationship("User", back_populates="tasks")
    replies = relationship(
        "Reply",
        back_populates="task",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Task(id={self.id}, status={self.status}, assignee_user_id={self.assignee_user_id})>"


class Reply(Base):
    """
    Moderator replies to tasks.

    Stores responses generated by moderators or LLMs, with confirmation and edit tracking.
    """
    __tablename__ = "replies"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    generated_by = Column(String(50), nullable=False, default="human", index=True)  # 'human' | 'llm'
    llm_confidence = Column(Float, nullable=True)  # LLM confidence (0.0 - 1.0), if generated_by = 'llm'
    confirmed = Column(Boolean, nullable=False, default=False, index=True)
    posted_at = Column(DateTime, nullable=True)  # Timestamp of successful posting
    platform_ref = Column(Text, nullable=True)  # JSON with posting info: {"platform": "discord", "message_id": "123"}
    edit_of = Column(BigInteger, ForeignKey("replies.id"), nullable=True, index=True)  # Reference to original reply (if this is an edit)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    task = relationship("Task", back_populates="replies")
    original_reply = relationship("Reply", remote_side=[id], backref="edits")

    def __repr__(self):
        return f"<Reply(id={self.id}, task_id={self.task_id}, generated_by={self.generated_by}, confirmed={self.confirmed})>"


class Settings(Base):
    """
    User settings (DND mode, reminders, etc.).

    Stores per-user configuration for moderation behavior.
    """
    __tablename__ = "settings"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    dnd_enabled = Column(Boolean, nullable=False, default=False)
    dnd_schedule_json = Column(Text, nullable=True)  # JSON with DND schedule
    reminders_enabled = Column(Boolean, nullable=False, default=False)  # v0.2+
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self):
        return f"<Settings(id={self.id}, user_id={self.user_id}, dnd_enabled={self.dnd_enabled})>"


class AuditLog(Base):
    """
    System audit log for all actions.

    Records all significant events in the system for security and debugging.
    """
    __tablename__ = "audit_log"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    kind = Column(String(100), nullable=False, index=True)  # Event type
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    payload_json = Column(Text, nullable=False)  # JSON with event details
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)

    # Relationships
    user = relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog(id={self.id}, kind={self.kind}, user_id={self.user_id})>"


class AIResponseVariant(Base):
    """
    AI-generated response variants.

    Stores AI-generated response options for tasks with metadata about
    the generation process (provider, model, confidence, tone).
    """
    __tablename__ = "ai_response_variants"

    # Columns
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    task_id = Column(BigInteger, ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    variant_text = Column(Text, nullable=False)
    confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    provider = Column(String(50), nullable=True)  # 'openai' or 'anthropic'
    model = Column(String(100), nullable=True)  # 'gpt-4-turbo', 'claude-3-opus', etc.
    tone = Column(String(50), nullable=True)  # NULL, 'soft', 'formal'
    selected = Column(Boolean, nullable=False, default=False, index=True)  # Was this variant selected?
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    task = relationship("Task", backref="ai_variants")

    def __repr__(self):
        return f"<AIResponseVariant(id={self.id}, task_id={self.task_id}, provider={self.provider}, selected={self.selected})>"


# Composite indexes for query optimization
Index("idx_tasks_assignee_status", Task.assignee_user_id, Task.status)
Index("idx_messages_channel_created", Message.channel_id, Message.created_at.desc())
Index("idx_messages_author_created", Message.author_id, Message.created_at.desc())
Index("idx_ai_variants_task_selected", AIResponseVariant.task_id, AIResponseVariant.selected)
