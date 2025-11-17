-- Migration: 001_initial_schema
-- Description: Initial database schema for the moderator project
-- Created: 2025-11-17
-- Tables: users, platform_accounts, discord_connection, channels_allowlist, messages,
--         attachments, tasks, replies, settings, audit_log

-- =============================================================================
-- Table: users
-- Description: Information about system users (MVP: only one moderator)
-- =============================================================================

CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tg_user_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_tg_user_id ON users(tg_user_id);

-- =============================================================================
-- Table: platform_accounts
-- Description: User accounts on different platforms (Discord, Telegram)
-- =============================================================================

CREATE TABLE platform_accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL, -- 'discord' | 'telegram'
    external_id VARCHAR(255) NOT NULL, -- Discord user ID or Telegram ID
    meta_encrypted TEXT, -- encrypted metadata
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(platform, external_id)
);

CREATE INDEX idx_platform_accounts_user_id ON platform_accounts(user_id);
CREATE INDEX idx_platform_accounts_platform ON platform_accounts(platform);

-- =============================================================================
-- Table: discord_connection
-- Description: Discord Gateway connection information
-- =============================================================================

CREATE TABLE discord_connection (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_token_encrypted TEXT NOT NULL, -- encrypted User Token
    super_properties TEXT, -- JSON with super properties
    session_id VARCHAR(255),
    last_connected_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'disconnected', -- 'connected' | 'disconnected' | 'error'
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_discord_connection_user_id ON discord_connection(user_id);
CREATE INDEX idx_discord_connection_status ON discord_connection(status);

-- =============================================================================
-- Table: channels_allowlist
-- Description: List of allowed channels for receiving messages
-- =============================================================================

CREATE TABLE channels_allowlist (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL, -- 'discord' | 'telegram'
    server_id VARCHAR(255), -- Discord guild ID (NULL for Telegram)
    channel_id VARCHAR(255) NOT NULL,
    thread_filter_json TEXT, -- JSON with thread filters (optional)
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(platform, server_id, channel_id)
);

CREATE INDEX idx_channels_allowlist_platform ON channels_allowlist(platform);
CREATE INDEX idx_channels_allowlist_enabled ON channels_allowlist(enabled);
CREATE INDEX idx_channels_allowlist_channel_id ON channels_allowlist(channel_id);

-- =============================================================================
-- Table: messages
-- Description: Storage for messages from different platforms
-- =============================================================================

CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    ext_message_id VARCHAR(255) NOT NULL, -- Message ID on the platform
    server_id VARCHAR(255), -- Discord guild ID
    channel_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255), -- Thread ID (optional)
    author_id VARCHAR(255) NOT NULL,
    author_name VARCHAR(255),
    content TEXT,
    has_image BOOLEAN DEFAULT false,
    context_ref BIGINT, -- reference to "parent" message for context
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    platform_created_at TIMESTAMP, -- creation time on the platform
    UNIQUE(platform, ext_message_id)
);

CREATE INDEX idx_messages_platform ON messages(platform);
CREATE INDEX idx_messages_channel_id ON messages(channel_id);
CREATE INDEX idx_messages_author_id ON messages(author_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_context_ref ON messages(context_ref);

-- =============================================================================
-- Table: attachments
-- Description: Message attachments (images, links)
-- =============================================================================

CREATE TABLE attachments (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    kind VARCHAR(50) NOT NULL, -- 'image' | 'link' | 'video' | 'file'
    ref TEXT NOT NULL, -- URL or file path
    meta TEXT, -- JSON with metadata (size, type, etc.)
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_attachments_message_id ON attachments(message_id);
CREATE INDEX idx_attachments_kind ON attachments(kind);

-- =============================================================================
-- Table: tasks
-- Description: Tasks for the moderator (incoming messages requiring response)
-- =============================================================================

CREATE TABLE tasks (
    id BIGSERIAL PRIMARY KEY,
    source_message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'open', -- 'open' | 'answered' | 'muted' | 'error'
    assignee_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tg_card_message_id BIGINT, -- Telegram card message ID
    error_message TEXT, -- error message (if status = 'error')
    reminder_count INT DEFAULT 0, -- number of reminders sent
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    answered_at TIMESTAMP -- response time
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assignee_user_id ON tasks(assignee_user_id);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_source_message_id ON tasks(source_message_id);

-- =============================================================================
-- Table: replies
-- Description: Moderator responses to tasks
-- =============================================================================

CREATE TABLE replies (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    generated_by VARCHAR(50) NOT NULL DEFAULT 'human', -- 'human' | 'llm'
    llm_confidence FLOAT, -- LLM confidence (0.0 - 1.0), if generated_by = 'llm'
    confirmed BOOLEAN NOT NULL DEFAULT false,
    posted_at TIMESTAMP, -- successful posting time
    platform_ref TEXT, -- JSON with posting information: {"platform": "discord", "message_id": "123"}
    edit_of BIGINT REFERENCES replies(id), -- reference to original reply (if this is an edit)
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_replies_task_id ON replies(task_id);
CREATE INDEX idx_replies_generated_by ON replies(generated_by);
CREATE INDEX idx_replies_confirmed ON replies(confirmed);
CREATE INDEX idx_replies_edit_of ON replies(edit_of);

-- =============================================================================
-- Table: settings
-- Description: Moderator settings
-- =============================================================================

CREATE TABLE settings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    dnd_enabled BOOLEAN NOT NULL DEFAULT false,
    dnd_schedule_json TEXT, -- JSON with DND schedule
    reminders_enabled BOOLEAN NOT NULL DEFAULT false, -- v0.2+
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_settings_user_id ON settings(user_id);

-- =============================================================================
-- Table: audit_log
-- Description: Audit log of all system actions
-- =============================================================================

CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    kind VARCHAR(100) NOT NULL, -- event type
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    payload_json TEXT NOT NULL, -- JSON with event details
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_kind ON audit_log(kind);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);

-- =============================================================================
-- Composite indexes for performance optimization
-- =============================================================================

-- Fast lookup of moderator's open tasks
CREATE INDEX idx_tasks_assignee_status ON tasks(assignee_user_id, status);

-- Fast lookup of messages by channel and date
CREATE INDEX idx_messages_channel_created ON messages(channel_id, created_at DESC);

-- Fast lookup by author and date
CREATE INDEX idx_messages_author_created ON messages(author_id, created_at DESC);
