# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [0.2.0] - v0.2 Iteration 6 - Infrastructure & Monitoring - 2025-11-18

### 🚀 Major Milestone: v0.2 Iteration 6 Completed

Advanced infrastructure features added: Redis job queue, Discord rate limiting, LLM cost monitoring, and automated reminder system.

---

### Iteration 6: Advanced Infrastructure (2025-11-18)

#### Phase 1: Redis Job Queue System
- **Job Queue Infrastructure** (`backend/src/job_queue/` new package)
  - `client.py` - Redis client wrapper with connection pooling (AsyncRedis singleton)
  - `worker.py` - ARQ worker configuration with startup/shutdown hooks
  - `tasks.py` - Job enqueue functions (discord_message, telegram_message, llm_generation, etc.)
  - `handlers.py` - Task handler stubs for background processing
  - Support for job priority, retries, and timeout configuration

- **Docker Infrastructure**
  - Added Redis 7 service to `docker-compose.yml` with persistence
  - Added ARQ worker service with health checks
  - Configured worker to use `src.job_queue.worker.WorkerSettings`

#### Phase 2: Discord Rate Limiting System
- **Rate Limiter Service** (`backend/src/services/rate_limiter.py` 508 lines)
  - `Bucket` class for route-specific rate limits (limit/remaining/reset tracking)
  - `GlobalRateLimit` class for 50 req/sec global limit (sliding window)
  - `RateLimiter` class with route normalization and bucket management
  - Automatic rate limit updates from Discord response headers
  - 429 error handling with exponential backoff
  - Singleton pattern for shared state across application

- **Discord Poster Integration** (`backend/src/discord/poster.py` updated)
  - Integrated `RateLimiter` into `DiscordPoster.post_message()`
  - Pre-request rate limit acquisition
  - Post-response header parsing and bucket updates
  - Retry logic with backoff on 429 responses

- **Tests** (`test_rate_limiter_standalone.py` 315 lines)
  - 20+ unit tests covering all rate limiter functionality
  - ✅ All tests passing

#### Phase 3: LLM Cost Monitoring System
- **Database Schema** (`migrations/003_llm_monitoring.sql` 126 lines)
  - `llm_requests` table (request tracking with token usage and costs)
  - `llm_usage_budgets` table (budget management with alert thresholds)
  - 3 views: `llm_usage_summary`, `llm_cost_by_model`, `llm_recent_errors`
  - Indexes for performance optimization

- **Monitoring Service** (`backend/src/services/llm_monitoring.py` 535 lines)
  - Token-based cost calculation for OpenAI and Anthropic models
  - Pricing tables: GPT-4, GPT-3.5-turbo, Claude-3 (Opus/Sonnet/Haiku)
  - `track_llm_request()` for automatic cost tracking
  - Budget management with configurable thresholds (daily/weekly/monthly)
  - `check_budget_alerts()` for overage notifications
  - Singleton pattern for shared service instance

- **LLM DAO** (`backend/src/database/dao/llm_dao.py` 562 lines)
  - `LLMMonitoringDAO` with 12 methods
  - Daily/weekly/monthly usage summaries
  - Budget status queries with current usage calculation
  - Error rate and model performance analytics
  - Top expensive requests tracking

- **LLM Client Integration** (`backend/src/services/llm.py` updated)
  - Automatic tracking in `OpenAIClient.generate_response()`
  - Automatic tracking in `AnthropicClient.generate_response()`
  - Duration measurement and error tracking
  - Token usage extraction from API responses

#### Phase 4: Reminder System
- **Reminder Service** (`backend/src/services/reminders.py` 440 lines)
  - `ReminderService` class with periodic task scanning
  - Reminder filtering logic (max 3 reminders per task, 30-min intervals)
  - DND mode integration (skip reminders during quiet hours)
  - User preference checking (respect reminders_enabled setting)
  - Markdown-formatted reminder messages with task details
  - Automatic reminder count tracking in database

- **Telegram Bot Enhancement** (`backend/src/telegram/bot.py` updated)
  - Added `parse_mode` parameter to `send_message()` for Markdown support
  - Backward-compatible with existing code

- **Tests** (`backend/tests/test_reminders.py` 363 lines)
  - 13 unit tests covering all reminder functionality
  - Tests for max reminders, task age, interval checking, DND mode
  - Text formatting tests (first/second/final reminders, truncation)
  - Telegram error handling tests

#### Dependencies Added
- `arq>=0.25.0` - Async Redis queue for background jobs
- `redis>=5.0.0` - Redis client with async support
- `pytest>=9.0.0` - Testing framework (dev dependency)
- `pytest-asyncio>=1.3.0` - Async test support (dev dependency)

#### Bug Fixes
- Fixed circular import issue caused by `queue` package name conflict with Python stdlib
- Renamed `backend/src/queue/` → `backend/src/job_queue/` to avoid name collision
- Updated docker-compose.yml worker command to reflect new package name

#### Test Results
- 41/58 tests passing (71% pass rate)
- 17 tests skipped (require full integration setup or API keys)
- All new rate limiter tests passing ✅
- Import tests passing ✅
- Encryption and DAO tests passing ✅

#### Documentation
- Created integration guides for all 4 phases
- Updated docker-compose.yml with Redis and worker services
- Added environment variable documentation for LLM providers
- Created test documentation for reminder system

---

## [0.1.0] - MVP v0.1 Complete - 2025-11-18

### 🎉 Major Milestone: MVP v0.1 Completed

Full end-to-end Discord-to-Telegram moderation workflow is now operational.

---

### Iteration 4: Discord-to-Telegram Integration (2025-11-18)

**Commit**: `a4305f2` - "Complete MVP v0.1: Implement full Discord-to-Telegram message flow"

#### Added
- **Discord MESSAGE_CREATE Processing** (`backend/src/discord/gateway.py` +207 lines)
  - Complete `_process_message()` implementation in DiscordGatewayManager
  - Allowlist filtering via `AllowlistDAO.is_channel_allowed()`
  - DND check with 'muted' task creation during DND hours
  - Message persistence via `MessageDAO.create_message()`
  - Attachment persistence via `AttachmentDAO.create_attachment()`
  - Moderator task creation via `TaskDAO.create_task()`
  - Callback mechanism (`on_new_task_callback`) for Telegram notifications
  - Automatic moderator user creation if doesn't exist
  - Discord ISO 8601 timestamp parsing with timezone support
  - Thread message support with `thread_id` tracking

- **Telegram Card Sender** (`backend/src/main.py` +80 lines)
  - `send_card_to_telegram()` method in ModeratorApplication
  - Message, attachments, and context loading from database
  - Card formatting using `format_card()` and `create_card_keyboard()`
  - Telegram notification sending via `telegram_bot.send_message()`
  - Callback wiring in DiscordGatewayManager initialization
  - Asyncpg connection pool management with proper cleanup

- **End-to-End Integration Tests** (`tests/test_integration.py` +390 lines, +4 tests)
  - `test_complete_discord_to_telegram_flow` - Full pipeline verification
  - `test_discord_message_allowlist_filtering` - Allowlist enforcement
  - `test_discord_message_dnd_filtering` - DND mode handling
  - `test_discord_thread_message_processing` - Thread support

#### Test Results
- 41/50 tests passing (82%)
- 9 tests skipped (acceptable for MVP)
- All new E2E functionality fully tested

---

### Iteration 3: Feature Completion (2025-11-17)

**Commit**: `ed87057` - "Complete MVP v0.1 - Iteration 3"

#### Added
- **Context Pagination** (`telegram/handlers.py` +118 lines)
  - `callback_more()` implementation for "Show More" button
  - Progressive loading: 10→20→30 messages
  - Offset tracking per task in FSM state
  - In-place message editing with updated context

- **Media Support** (`main.py`, `cards.py` enhancements)
  - Attachment loading via `AttachmentDAO`
  - Image (🖼) and file (📄) display in cards
  - Markdown links with `disable_web_page_preview=True`
  - Metadata parsing with fallbacks

- **DND Schedule System** (`services/dnd.py` complete rewrite, 150 lines)
  - JSON schedule format: `[{"start": "HH:MM", "end": "HH:MM", "days": [0-6]}]`
  - Overnight interval support (e.g., 22:00-08:00)
  - `/dnd schedule` command with presets ("weeknights", "always")
  - `is_in_dnd_schedule()` time range checking

- **Alert System** (`services/alerts.py` +180 lines)
  - Throttling mechanism to prevent spam
  - 4 alert types: ERROR, WARNING, INFO, CRITICAL
  - Discord Gateway error alerts
  - Database health monitoring with background task
  - `monitor_database_health()` in main.py

- **Integration Tests** (`tests/test_integration.py` created, 782 lines, 21 tests)
  - 12/21 passing (57%)
  - Tests for encryption, FSM, workflows, DND, alerts
  - Mock infrastructure in `conftest.py`

---

### Iteration 2: Database Integration & Reply Flow (2025-11-16)

**Commit**: `24fb9d0` - "Implement complete MVP v0.1 backend for Discord-Telegram moderator console"

#### Added
- **Complete Database DAO Layer** (8 DAO modules)
  - `MessageDAO` - Message CRUD operations
  - `TaskDAO` - Task management and status updates
  - `ReplyDAO` - Reply lifecycle (create, confirm, post, delete)
  - `UserDAO` - User management with DND settings
  - `DiscordDAO` - Discord connection management
  - `AllowlistDAO` - Channel allowlist operations
  - `AttachmentDAO` - Attachment metadata storage
  - `AuditDAO` - Audit logging

- **Telegram Handler Implementation** (`telegram/handlers.py` 857 lines)
  - All commands: `/start`, `/help`, `/setup_discord`, `/test_connection`, `/discord_status`, `/status`, `/dnd`, `/allow_channel`, `/unallow_channel`, `/settings`
  - Callback handlers: `reply_`, `more_`, `confirm_`, `retry_`, `toggle_dnd`, `cancel_reply`
  - FSM state machine for multi-step workflows
  - Reply confirmation workflow with database persistence

- **Telegram Card Formatting** (`telegram/cards.py` 180 lines)
  - `format_card()` - Markdown card generation
  - `create_card_keyboard()` - Inline keyboard with action buttons
  - `create_example_card()` - Demo card for testing
  - Context message formatting with author attribution

- **Business Logic Services**
  - `services/context.py` - Message context retrieval
  - `services/dnd.py` - DND mode management
  - `services/allowlist.py` - Channel allowlist logic
  - `services/alerts.py` - Alert notification system

- **Main Application** (`main.py` 507 lines)
  - `ModeratorApplication` orchestrator class
  - Component lifecycle management
  - Graceful shutdown handling
  - Database and asyncpg pool initialization

#### Test Coverage
- 25 unit tests created
- All DAO methods tested
- Encryption verified

---

### Iteration 1: Infrastructure & Database Schema (2025-11-15)

**Commit**: `49e953c` - "Add comprehensive technical specification documentation"

#### Added
- **Database Schema** (`backend/database/schema.sql` 350 lines)
  - 9 tables: users, discord_connections, settings, messages, attachments, tasks, replies, channels_allowlist, audit_log
  - Proper foreign keys and constraints
  - Indexes for performance
  - JSON columns for flexible data storage

- **Database Models** (`backend/database/models.py`)
  - SQLAlchemy ORM models for all tables
  - Dataclass models for type safety
  - Encryption integration for sensitive data

- **Encryption Service** (`backend/database/encryption.py`)
  - Fernet (AES-256) encryption for Discord tokens
  - Singleton pattern for key management
  - Environment-based key configuration

- **Configuration System** (`backend/config.py`)
  - Dataclass-based configuration
  - Environment variable loading
  - Validation and defaults

- **Project Structure**
  - Docker Compose setup
  - PostgreSQL 15 container
  - Backend Python 3.11+ environment
  - Logging configuration

- **Comprehensive Documentation** (12 docs)
  - REQUIREMENTS.md - Functional requirements
  - ARCHITECTURE.md - System design
  - DATABASE.md - Schema documentation
  - DISCORD_INTEGRATION.md - Discord Gateway spec
  - TELEGRAM_INTEGRATION.md - Telegram Bot spec
  - ROADMAP.md - Development timeline
  - TESTING.md - Test strategy
  - And 5 more supporting docs

#### Test Infrastructure
- pytest configuration (`tests/conftest.py`)
- Test fixtures for database, encryption, sample data
- Initial test structure

---

## Development Statistics

**Total Development Time**: 4 days (4 iterations)
**Total Commits**: 7 major commits
**Lines of Code Added**: ~6,000+ lines
**Files Created**: 50+ files
**Test Coverage**: 82% pass rate (41/50 tests)

### File Statistics by Iteration
- Iteration 1: ~1,500 lines (infrastructure + schema + docs)
- Iteration 2: ~2,000 lines (DAOs + handlers + services)
- Iteration 3: ~1,800 lines (features + tests)
- Iteration 4: ~700 lines (integration + tests)

---

## Technology Stack

**Backend:**
- Python 3.11+
- asyncio for concurrent operations
- aiohttp for HTTP/WebSocket clients
- asyncpg for async PostgreSQL operations
- SQLAlchemy for ORM
- Fernet (cryptography) for encryption
- websockets for Discord Gateway
- pytest for testing

**Infrastructure:**
- Docker & Docker Compose
- PostgreSQL 15
- Git for version control

**APIs:**
- Discord Gateway API (User account, WebSocket)
- Telegram Bot API (Long polling)

---

## Key Features Implemented

### Core Workflow
✅ Discord message monitoring via Gateway
✅ Telegram notification cards with context
✅ Reply posting to Discord and Telegram
✅ Mandatory confirmation before sending

### Safety & Control
✅ Encryption for sensitive tokens
✅ Error handling with retry mechanisms
✅ Audit logging for all actions

### Convenience
✅ DND mode with flexible scheduling
✅ Context pagination ("Show More")
✅ Channel allowlist management
✅ Thread message support

### Media & Attachments
✅ Image and file attachment support
✅ Metadata storage and display
✅ Clickable links in cards

### Monitoring
✅ Alert system with throttling
✅ Database health monitoring
✅ Comprehensive logging

---

## Next Steps (v0.2)

See ROADMAP.md for v0.2 features:
- LLM integration (OpenAI/Anthropic)
- Response suggestion generation
- Redis-based queue system
- Rate limiting improvements
- Reminder system for open tasks

---

## Breaking Changes

None (initial release)

---

## Contributors

- Claude (AI Assistant) - Full implementation
- liker0704 (Project Owner) - Requirements and oversight
