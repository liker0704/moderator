-- Migration: 009_audit_enhancements
-- Description: Enhanced audit logging with IP tracking, user agent, and retention policy
-- Created: 2025-11-19
-- Changes:
--   - Add ip_address column for tracking request origin
--   - Add user_agent column for tracking API client information
--   - Add retention_days column for configurable retention
--   - Create index on created_at for efficient cleanup
--   - Add new audit event types for v1.0 features

-- =============================================================================
-- Audit Log Enhancements
-- =============================================================================

-- Add new columns to audit_log table
ALTER TABLE audit_log
    ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45),  -- IPv4 (15 chars) or IPv6 (45 chars)
    ADD COLUMN IF NOT EXISTS user_agent TEXT,
    ADD COLUMN IF NOT EXISTS retention_days INTEGER DEFAULT 90;

-- Add comment to explain the new columns
COMMENT ON COLUMN audit_log.ip_address IS 'IP address of the request origin (if available)';
COMMENT ON COLUMN audit_log.user_agent IS 'User agent string for API calls (if available)';
COMMENT ON COLUMN audit_log.retention_days IS 'Number of days to retain this log entry (default: 90)';

-- Create index on created_at for efficient cleanup queries
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON audit_log(created_at);

-- Create index on kind and created_at for common queries
CREATE INDEX IF NOT EXISTS idx_audit_log_kind_created ON audit_log(kind, created_at DESC);

-- Create index on ip_address for security analysis
CREATE INDEX IF NOT EXISTS idx_audit_log_ip_address ON audit_log(ip_address) WHERE ip_address IS NOT NULL;

-- =============================================================================
-- New Audit Event Types (v1.0)
-- =============================================================================

-- This migration doesn't create event type records, but documents the new types
-- that should be used in the application code:
--
-- Authentication & Authorization:
--   - 'auth.login': User login event
--   - 'auth.logout': User logout event
--   - 'auth.failed': Failed authentication attempt
--
-- Settings & Configuration:
--   - 'settings.updated': Settings changed
--   - 'allowlist.modified': Allowlist channel added/removed
--
-- Data Management:
--   - 'export.created': Data export requested
--   - 'template.created': Reply template created
--   - 'template.deleted': Reply template deleted
--   - 'template.updated': Reply template modified
--
-- Search & Access:
--   - 'search.executed': Search query performed
--   - 'data.accessed': Sensitive data accessed
--
-- System Events:
--   - 'token.rotated': Security token rotated
--   - 'secret.accessed': Docker secret accessed
--   - 'rate_limit.exceeded': Rate limit exceeded
--
-- Existing event types (for reference):
--   - 'user.created', 'user.updated'
--   - 'message.received', 'message.processed'
--   - 'reply.posted', 'reply.edited', 'reply.failed'
--   - 'discord.connected', 'discord.disconnected'
--   - 'error.occurred'
--   - 'llm.request', 'llm.response'

-- =============================================================================
-- Retention Policy Function
-- =============================================================================

-- Create a function to clean up old audit logs based on retention policy
CREATE OR REPLACE FUNCTION cleanup_old_audit_logs()
RETURNS TABLE(deleted_count INTEGER) AS $$
DECLARE
    rows_deleted INTEGER;
BEGIN
    -- Delete logs older than their retention period
    DELETE FROM audit_log
    WHERE created_at < NOW() - MAKE_INTERVAL(days => retention_days);

    GET DIAGNOSTICS rows_deleted = ROW_COUNT;

    RETURN QUERY SELECT rows_deleted;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION cleanup_old_audit_logs() IS
'Deletes audit logs older than their retention_days. Returns number of rows deleted.';

-- =============================================================================
-- Audit Statistics View
-- =============================================================================

-- Create a view for common audit statistics
CREATE OR REPLACE VIEW audit_statistics AS
SELECT
    kind,
    COUNT(*) as total_events,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT ip_address) as unique_ips,
    MIN(created_at) as first_event,
    MAX(created_at) as last_event,
    DATE_PART('day', MAX(created_at) - MIN(created_at)) as span_days
FROM audit_log
GROUP BY kind
ORDER BY total_events DESC;

COMMENT ON VIEW audit_statistics IS
'Summary statistics for audit events grouped by event type';

-- =============================================================================
-- Recent Failed Auth Attempts View
-- =============================================================================

-- Create a view for security monitoring of failed authentication
CREATE OR REPLACE VIEW recent_failed_auth AS
SELECT
    ip_address,
    user_agent,
    COUNT(*) as attempt_count,
    MAX(created_at) as last_attempt,
    ARRAY_AGG(DISTINCT user_id) as attempted_user_ids,
    payload_json
FROM audit_log
WHERE kind = 'auth.failed'
    AND created_at > NOW() - INTERVAL '24 hours'
GROUP BY ip_address, user_agent, payload_json
HAVING COUNT(*) >= 3  -- Only show IPs with 3+ failed attempts
ORDER BY attempt_count DESC, last_attempt DESC;

COMMENT ON VIEW recent_failed_auth IS
'Failed authentication attempts in the last 24 hours, grouped by IP address';

-- =============================================================================
-- Migration Complete
-- =============================================================================

-- Add migration record (if migrations table exists)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'migrations') THEN
        INSERT INTO migrations (version, description, applied_at)
        VALUES ('009', 'audit_enhancements', NOW())
        ON CONFLICT (version) DO NOTHING;
    END IF;
END $$;
