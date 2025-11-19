-- Migration: 008_templates
-- Description: Add quick reply templates functionality for moderators
-- Created: 2025-11-19
-- Dependencies: 001_initial_schema

-- =============================================================================
-- Table: templates
-- Description: Quick reply templates for moderators
-- =============================================================================

CREATE TABLE templates (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    usage_count INT NOT NULL DEFAULT 0,
    UNIQUE(user_id, name)
);

-- =============================================================================
-- Indexes for Templates
-- =============================================================================

-- Index for listing user's templates
CREATE INDEX idx_templates_user_id ON templates(user_id);

-- Index for searching templates by name
CREATE INDEX idx_templates_user_name ON templates(user_id, name);

-- Index for ordering by usage count (most used templates first)
CREATE INDEX idx_templates_user_usage ON templates(user_id, usage_count DESC);

-- Index for ordering by creation date
CREATE INDEX idx_templates_created_at ON templates(created_at DESC);

-- =============================================================================
-- Comments for Documentation
-- =============================================================================

COMMENT ON TABLE templates IS
'Quick reply templates for moderators to speed up common responses';

COMMENT ON COLUMN templates.id IS
'Unique template identifier';

COMMENT ON COLUMN templates.user_id IS
'User who owns this template';

COMMENT ON COLUMN templates.name IS
'Template name (unique per user)';

COMMENT ON COLUMN templates.content IS
'Template content with optional variable substitution placeholders';

COMMENT ON COLUMN templates.usage_count IS
'Number of times this template has been used (for sorting by popularity)';

COMMENT ON COLUMN templates.created_at IS
'Timestamp when template was created';

COMMENT ON COLUMN templates.updated_at IS
'Timestamp when template was last modified';

COMMENT ON INDEX idx_templates_user_id IS
'Optimizes listing all templates for a specific user';

COMMENT ON INDEX idx_templates_user_name IS
'Optimizes template lookup by name for a specific user';

COMMENT ON INDEX idx_templates_user_usage IS
'Optimizes sorting templates by popularity (most used first)';

-- =============================================================================
-- Statistics and Maintenance
-- =============================================================================

-- Analyze table to update query planner statistics
ANALYZE templates;
