-- Migration: 004_edit_indexes
-- Description: Add optimized indexes for edit permission checks and history queries
-- Created: 2025-11-18
-- Dependencies: 001_initial_schema (replies, tasks tables)

-- =============================================================================
-- Indexes for Edit Chain Lookup (replies.edit_of)
-- =============================================================================

-- Optimize recursive CTE for fetching edit history
-- Replaces basic idx_replies_edit_of with partial index for non-NULL values
DROP INDEX IF EXISTS idx_replies_edit_of;
CREATE INDEX IF NOT EXISTS idx_replies_edit_of
ON replies(edit_of)
WHERE edit_of IS NOT NULL;

-- =============================================================================
-- Indexes for Edit Time Validation (48-hour edit window)
-- =============================================================================

-- Quick lookup of reply posting time for edit permission checks
-- Used by: ReplyDAO.can_edit_reply() to enforce 48-hour edit limit
CREATE INDEX IF NOT EXISTS idx_replies_posted_at
ON replies(posted_at DESC)
WHERE posted_at IS NOT NULL;

-- Composite index for checking if reply was already posted
-- Helps with: SELECT ... WHERE posted_at IS NOT NULL AND task_id = ?
CREATE INDEX IF NOT EXISTS idx_replies_task_posted_at
ON replies(task_id, posted_at DESC)
WHERE posted_at IS NOT NULL;

-- =============================================================================
-- Indexes for User Permission Validation
-- =============================================================================

-- Composite index for task ownership verification during edit checks
-- Used by: ReplyDAO.can_edit_reply() to JOIN replies -> tasks -> assignee validation
CREATE INDEX IF NOT EXISTS idx_tasks_id_assignee_status
ON tasks(id, assignee_user_id, status);

-- =============================================================================
-- Index Maintenance Comments
-- =============================================================================

COMMENT ON INDEX idx_replies_edit_of IS
  'Optimizes recursive CTE for fetching reply edit history (WHERE edit_of IS NOT NULL)';

COMMENT ON INDEX idx_replies_posted_at IS
  'Optimizes edit time limit checks - ensures reply was posted and within 48-hour window';

COMMENT ON INDEX idx_replies_task_posted_at IS
  'Optimizes finding posted replies by task_id for showing edit button on cards';

COMMENT ON INDEX idx_tasks_id_assignee_status IS
  'Optimizes user ownership validation and task status checks during edit permission verification';
