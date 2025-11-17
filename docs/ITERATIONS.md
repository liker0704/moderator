# Development Iterations Plan: Moderator Project

**Last Updated:** 2025-11-17
**Language:** Python
**Scope:** All versions (MVP v0.1 → v0.2 → v1.0)
**Total Timeline:** ~11-12 weeks (flexible based on complexity)

---

## Table of Contents

1. [Overview](#overview)
2. [Iteration Structure](#iteration-structure)
3. [Phase 1: MVP v0.1](#phase-1-mvp-v01) (4-5 weeks)
4. [Phase 2: v0.2 - LLM Integration](#phase-2-v02---llm-integration) (2-3 weeks)
5. [Phase 3: v1.0 - Production Ready](#phase-3-v10---production-ready) (3-4 weeks)
6. [Dependencies Map](#dependencies-map)
7. [Risk Management](#risk-management)

---

## Overview

This document breaks down the Moderator project development into **11 iterations** across **3 phases**. Each iteration is:

- **Self-contained**: Produces working, testable functionality
- **Incremental**: Builds on previous iterations
- **Time-boxed**: Has clear duration estimates
- **Testable**: Includes specific testing requirements

### Iteration Components

Each iteration includes:

- ✅ **Task Checklist**: Granular implementation tasks
- 🎯 **Definition of Done**: Clear acceptance criteria
- 🧪 **Testing Plan**: Unit, integration, and manual tests
- 📊 **Component Dependencies**: Visual diagrams (Mermaid)
- ⚠️ **Risks**: Known issues and mitigation strategies

---

## Iteration Structure

### Phase Breakdown

```
PHASE 1: MVP v0.1 (Foundation)
├── Iteration 0: Infrastructure & Foundation (5-7 days)
├── Iteration 1: Discord Integration (7-10 days)
├── Iteration 2: Telegram Bot Core (5-7 days)
├── Iteration 3: Message Processing & Response Flow (7-10 days)
├── Iteration 4: DND & Advanced Features (5-7 days)
└── Iteration 5: Testing & MVP Release (3-5 days)

PHASE 2: v0.2 (AI Enhancement)
├── Iteration 6: LLM Integration (7-10 days)
├── Iteration 7: Queue System & Rate Limiting (5-7 days)
└── Iteration 8: Advanced v0.2 Features (3-5 дней)

PHASE 3: v1.0 (Production)
├── Iteration 9: Multi-server & Advanced UI (7-10 days)
├── Iteration 10: Search & Analytics (5-7 days)
└── Iteration 11: Final Polish & v1.0 Release (5-7 days)
```

---

## PHASE 1: MVP v0.1

**Goal:** Build a working moderation console that aggregates Discord and Telegram messages into a single Telegram bot interface.

**Duration:** 4-5 weeks (6 iterations)

**Core Features:**
- Discord message ingestion via User Token
- Telegram DM ingestion
- Unified message cards with context
- Response workflow with confirmation
- DND mode with scheduling
- Basic error handling and alerts

---

## Iteration 0: Infrastructure & Foundation

**Duration:** 5-7 days
**Goal:** Set up project infrastructure, database, Docker environment, and core utilities

### ✅ Task Checklist

#### Project Structure Setup
- [ ] Create project directory structure:
  ```
  moderator/
  ├── backend/
  │   ├── __init__.py
  │   ├── config.py
  │   ├── database/
  │   │   ├── __init__.py
  │   │   ├── models.py
  │   │   ├── migrations/
  │   │   └── connection.py
  │   ├── services/
  │   │   ├── __init__.py
  │   │   ├── discord_service.py
  │   │   ├── telegram_service.py
  │   │   └── encryption_service.py
  │   ├── utils/
  │   │   ├── __init__.py
  │   │   ├── logger.py
  │   │   └── validators.py
  │   └── main.py
  ├── tests/
  │   ├── __init__.py
  │   ├── unit/
  │   └── integration/
  ├── docker-compose.yml
  ├── Dockerfile
  ├── requirements.txt
  ├── .env.example
  ├── .gitignore
  └── README.md
  ```

#### Docker & Environment Setup
- [ ] Create `Dockerfile` for Python backend (in `backend/`)
- [ ] Create `Dockerfile` for Node.js Discord service (in `discord-service/`)
- [ ] Create `docker-compose.yml` with all services:
  - PostgreSQL database
  - Python backend
  - Node.js Discord service
- [ ] Create `.env.example` with all required variables:
  - `DATABASE_URL` - PostgreSQL connection string
  - `DISCORD_USER_TOKEN` - Discord user token (for Node.js service)
  - `TELEGRAM_BOT_TOKEN` - Telegram bot API token
  - `ADMIN_TELEGRAM_ID` - Admin Telegram user ID
  - `ENCRYPTION_KEY` - Key for encrypting sensitive data
  - `SERVICE_SECRET` - Shared secret between Node.js and Python (generate with `openssl rand -hex 32`)
  - `DISCORD_SERVICE_URL` - Node.js service URL (e.g., http://discord-service:3000)
  - `PYTHON_SERVICE_URL` - Python service URL (e.g., http://backend:8000)
  - `LOG_LEVEL` - Logging level (DEBUG/INFO/WARNING/ERROR)
- [ ] Add `.gitignore` (exclude `.env`, `__pycache__`, `.pytest_cache`, `node_modules`, etc.)
- [ ] Example `docker-compose.yml`:
  ```yaml
  version: '3.8'

  services:
    postgres:
      image: postgres:15-alpine
      container_name: moderator-db
      environment:
        POSTGRES_DB: moderator
        POSTGRES_USER: moderator
        POSTGRES_PASSWORD: ${DB_PASSWORD}
      volumes:
        - postgres_data:/var/lib/postgresql/data
      networks:
        - moderator-network
      healthcheck:
        test: ["CMD-SHELL", "pg_isready -U moderator"]
        interval: 10s
        timeout: 5s
        retries: 5

    discord-service:
      build: ./discord-service
      container_name: moderator-discord
      environment:
        - DISCORD_USER_TOKEN=${DISCORD_USER_TOKEN}
        - PYTHON_SERVICE_URL=http://backend:8000
        - SERVICE_SECRET=${SERVICE_SECRET}
        - NODE_ENV=production
        - LOG_LEVEL=info
      ports:
        - "3000:3000"
      networks:
        - moderator-network
      restart: unless-stopped
      depends_on:
        backend:
          condition: service_healthy
      healthcheck:
        test: ["CMD", "node", "-e", "require('http').get('http://localhost:3000/api/health')"]
        interval: 30s
        timeout: 10s
        retries: 3
        start_period: 40s

    backend:
      build: ./backend
      container_name: moderator-backend
      environment:
        - DATABASE_URL=postgresql://moderator:${DB_PASSWORD}@postgres:5432/moderator
        - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
        - ADMIN_TELEGRAM_ID=${ADMIN_TELEGRAM_ID}
        - ENCRYPTION_KEY=${ENCRYPTION_KEY}
        - SERVICE_SECRET=${SERVICE_SECRET}
        - DISCORD_SERVICE_URL=http://discord-service:3000
        - LOG_LEVEL=info
      ports:
        - "8000:8000"
      networks:
        - moderator-network
      restart: unless-stopped
      depends_on:
        postgres:
          condition: service_healthy
      healthcheck:
        test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
        interval: 30s
        timeout: 10s
        retries: 3
        start_period: 40s

  volumes:
    postgres_data:

  networks:
    moderator-network:
      driver: bridge
  ```

#### Database Setup
- [ ] Create SQLAlchemy models based on `DATABASE.md` schema:
  - `User` model
  - `PlatformAccount` model
  - `DiscordConnection` model
  - `ChannelsAllowlist` model
  - `Message` model
  - `Attachment` model
  - `Task` model
  - `Reply` model
  - `Settings` model
  - `AuditLog` model
- [ ] Set up Alembic for migrations
- [ ] Create initial migration script
- [ ] Add database connection pooling (SQLAlchemy engine)
- [ ] Create `database/connection.py` with session management

#### Core Utilities
- [ ] Implement `encryption_service.py`:
  - AES-256 encryption for Discord tokens
  - Key derivation from `ENCRYPTION_KEY`
  - Encrypt/decrypt functions
- [ ] Implement `logger.py`:
  - Structured logging (JSON format)
  - Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
  - File rotation (max 100MB, keep 5 files)
  - Console output for development
- [ ] Implement `validators.py`:
  - Discord token validation
  - Telegram token validation
  - Channel ID format validation

#### Configuration Management
- [ ] Create `config.py` with Pydantic settings:
  - Load from `.env` file
  - Validate all required variables
  - Provide sensible defaults
  - Type checking

#### Requirements & Dependencies
- [ ] Create `requirements.txt`:
  - `fastapi` / `flask` (web framework)
  - `sqlalchemy` (ORM)
  - `alembic` (migrations)
  - `psycopg2-binary` (PostgreSQL driver)
  - `cryptography` (encryption)
  - `pydantic` (config validation)
  - `python-dotenv` (env loading)
  - `pytest` (testing)
  - `pytest-asyncio` (async tests)

### 🎯 Definition of Done

- [x] Project structure follows documented architecture
- [x] Docker Compose brings up backend + PostgreSQL successfully
- [x] Database migrations run without errors
- [x] All 10 database tables created correctly
- [x] Encryption service encrypts/decrypts test data successfully
- [x] Logger writes to both console and file
- [x] Config loads from `.env` and validates all fields
- [x] `.env.example` is complete and documented
- [x] Can connect to PostgreSQL and execute queries
- [x] All dependencies install without conflicts

### 🧪 Testing Plan

#### Unit Tests
- [ ] `test_encryption_service.py`:
  - Test encrypt/decrypt roundtrip
  - Test different key formats
  - Test error handling for invalid keys
- [ ] `test_logger.py`:
  - Test log level filtering
  - Test file rotation
  - Test JSON format output
- [ ] `test_validators.py`:
  - Test Discord token validation (valid/invalid)
  - Test Telegram token validation
  - Test channel ID formats
- [ ] `test_config.py`:
  - Test loading from `.env`
  - Test missing required variables
  - Test default values

#### Integration Tests
- [ ] `test_database_connection.py`:
  - Test database connection pooling
  - Test session creation/cleanup
  - Test transaction rollback
- [ ] `test_models.py`:
  - Test creating records in each table
  - Test foreign key relationships
  - Test cascade deletes

#### Manual Testing
- [ ] Run `docker-compose up` - services start successfully
- [ ] Run `alembic upgrade head` - migrations apply cleanly
- [ ] Connect to PostgreSQL - all tables exist
- [ ] Encrypt/decrypt a test Discord token
- [ ] Check log files are created

### 📊 Component Dependencies

```mermaid
graph TB
    A[Docker Compose] --> B[PostgreSQL Container]
    A --> C[Backend Container]
    C --> D[Config Service]
    D --> E[.env File]
    C --> F[Database Service]
    F --> B
    F --> G[SQLAlchemy Models]
    C --> H[Encryption Service]
    H --> I[Encryption Key]
    C --> J[Logger]
    J --> K[Log Files]
    C --> L[Validators]
```

### ⚠️ Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| PostgreSQL version incompatibility | Low | Medium | Use PostgreSQL 15+ in Docker, pin version |
| Encryption key loss | Medium | Critical | Document key backup in deployment guide |
| Database migration conflicts | Low | Medium | Test migrations in clean DB before commit |
| Dependency conflicts | Low | Low | Pin all versions in requirements.txt |

### 📝 Notes

- **DO NOT** commit `.env` file to Git
- **DO** encrypt Discord tokens before storing in DB
- **DO** test database connection before proceeding to next iteration
- Keep `requirements.txt` sorted alphabetically for easier maintenance
- Use meaningful migration names: `YYYYMMDD_HHMM_description.py`

---

## Iteration 1: Discord Integration (Hybrid Architecture)

**Duration:** 7-10 days
**Goal:** Implement Discord Gateway connection using Node.js microservice, integrate with Python backend

**Dependencies:** Iteration 0 (Infrastructure must be complete)

**Architecture:** Node.js Discord Service + Python Main Service

### ✅ Task Checklist

#### Node.js Discord Service Setup
- [ ] Initialize Node.js project in `discord-service/`:
  - Create `package.json` with dependencies:
    - `discord-user-bots` (Discord client)
    - `express` (REST API server)
    - `axios` (HTTP client for Python callback)
    - `dotenv` (environment variables)
  - TypeScript setup (optional but recommended)
  - ESLint + Prettier configuration
- [ ] Create Dockerfile for Node.js service:
  - Base: `node:18-alpine`
  - Install dependencies
  - Expose port 3000
  - Health check endpoint
- [ ] Add to docker-compose.yml:
  - `discord-service` container
  - Environment: `DISCORD_USER_TOKEN`, `PYTHON_SERVICE_URL`
  - Network: shared with `backend`
  - Depends on: `backend`

#### Discord Gateway Client (Node.js)
- [ ] Implement Gateway connection in `src/gateway.js`:
  - Use discord-user-bots Client
  - Connect with User Token
  - Handle ready event (log connection success)
  - Maintain heartbeat automatically
  - Store session info in memory
- [ ] Implement event handlers:
  - `messageCreate` event listener
  - `messageUpdate` event listener (optional for MVP)
  - Parse message payload (author, content, channel, etc.)
  - Extract server/channel/thread metadata
- [ ] Implement reconnection logic:
  - Auto-reconnect on disconnect (built-in with library)
  - Exponential backoff for failures
  - Alert Python service on repeated failures
  - Track connection state

#### REST API Server (Node.js)
- [ ] Create Express.js API in `src/api.js`:
  - `POST /api/discord/send` - Send message to Discord channel
    - Body: `{channel_id, content, reply_to_id?}`
    - Returns: `{success, message_id, error?}`
  - `GET /api/discord/channels` - List accessible channels
    - Returns: `{channels: [{id, name, server_id, server_name}]}`
  - `GET /api/discord/history/:channel_id` - Fetch message history
    - Query: `limit=10`, `before=message_id`
    - Returns: `{messages: [...]}`
  - `GET /api/health` - Service health check
    - Returns: `{status, connected, uptime}`
  - `GET /api/allowlist` - Get allowlist from Python DB
    - Cached in memory, refresh every 5 minutes
- [ ] Add authentication:
  - Shared secret between Node.js and Python
  - Header: `X-Service-Secret: ${SECRET}`
  - Reject requests without valid secret

#### Event Forwarding to Python
- [ ] Implement webhook caller in `src/webhook.js`:
  - On `messageCreate`: POST to `${PYTHON_SERVICE_URL}/webhook/discord/message`
  - Payload: normalized message data (see below)
  - Retry logic: 3 attempts with backoff
  - Log failures to console
- [ ] Message normalization:
  - Transform Discord message to standard format:
    ```json
    {
      "platform": "discord",
      "message_id": "123...",
      "channel_id": "456...",
      "server_id": "789...",
      "server_name": "My Server",
      "channel_name": "#general",
      "thread_id": null,
      "thread_name": null,
      "author": {
        "id": "111...",
        "username": "user",
        "discriminator": "1234"
      },
      "content": "message text",
      "timestamp": "2025-11-17T10:30:00Z",
      "attachments": [
        {"url": "https://...", "type": "image/png", "filename": "test.png"}
      ],
      "is_edit": false
    }
    ```
- [ ] Implement allowlist filtering in Node.js:
  - Fetch allowlist from Python API on startup
  - Cache in memory
  - Filter messages before forwarding
  - Log dropped messages

#### Python Integration Layer
- [ ] Create Discord HTTP client in `backend/services/discord_client.py`:
  - HTTP client to Node.js service
  - Method: `send_message(channel_id, content, reply_to=None)`
  - Method: `get_channels()` - list channels
  - Method: `get_message_history(channel_id, limit=10)`
  - Method: `get_health()` - check Node.js service status
  - Include auth header with shared secret
  - Timeout: 10 seconds
  - Retry logic: 2 attempts
- [ ] Create webhook endpoint in `backend/webhooks/discord_webhook.py`:
  - FastAPI/Flask endpoint: `POST /webhook/discord/message`
  - Validate auth header (shared secret)
  - Parse incoming normalized message
  - Pass to message processing pipeline
  - Return 200 OK (acknowledge receipt)
- [ ] Update `backend/config.py`:
  - Add `DISCORD_SERVICE_URL` (e.g., http://discord-service:3000)
  - Add `DISCORD_SERVICE_SECRET` (shared secret)

#### Python Allowlist Management
- [ ] Implement allowlist API for Node.js in `backend/api/allowlist.py`:
  - `GET /api/allowlist` - return list of allowed channel IDs
  - Require auth header
  - Query `channels_allowlist` table
  - Return JSON: `{channel_ids: ["123", "456", ...]}`
- [ ] Add allowlist management functions (Python):
  - `add_channel_to_allowlist(channel_id, server_id)`
  - `remove_channel_from_allowlist(channel_id)`
  - `get_all_allowed_channels()`
  - Notify Node.js service on changes (optional: webhook or poll)

#### Message Storage (Python)
- [ ] Implement message persistence in webhook handler:
  - Create `Message` record in database
  - Create `PlatformAccount` for sender if not exists
  - Create `Attachment` records for images/files
  - Link to existing or new `Task` record
  - Set task status to `open`
- [ ] Implement 90-day retention cleanup:
  - Background task (runs daily)
  - Delete messages older than 90 days
  - Cascade delete attachments and tasks
  - Log deletion count

#### Context Fetching (Python)
- [ ] Implement conversation history fetching:
  - Call Node.js API: `GET /api/discord/history/{channel_id}`
  - Request last 10 messages
  - Store context messages separately (flag `is_context=true`)
  - Link context to main message

#### Error Handling (Both Services)
- [ ] Node.js error handling:
  - Rate limit detection (HTTP 429) - backoff
  - Token validation errors (HTTP 401/403) - alert Python
  - Gateway disconnects - auto-reconnect
  - Log all errors to console (Docker logs)
- [ ] Python error handling:
  - Node.js service down - alert admin
  - Webhook timeout - log and retry
  - Invalid message format - log and skip
  - Create audit log entries for all errors

#### Security & Token Management
- [ ] Secure token in Node.js service:
  - Load from environment variable only
  - Never log token
  - Never expose via API
- [ ] Shared secret management:
  - Generate strong random secret (32+ chars)
  - Store in both `.env` files
  - Use for all inter-service communication
  - Rotate periodically (document process)

### 🎯 Definition of Done

- [x] Node.js Discord Service runs in Docker container
- [x] Discord Gateway connects successfully with User Token
- [x] Heartbeat maintains connection without disconnects
- [x] `MESSAGE_CREATE` events are received by Node.js
- [x] Events are forwarded to Python webhook successfully
- [x] Python webhook receives and processes events
- [x] Messages from allowed channels are stored in Python DB
- [x] Messages from non-allowed channels are dropped (Node.js filtering)
- [x] Attachments metadata is stored in DB
- [x] Context (last 10 messages) can be fetched via Node.js API
- [x] Thread messages are handled correctly
- [x] Reconnection works with auto-retry
- [x] Rate limits are respected in Node.js
- [x] Token is secured in Node.js environment
- [x] Shared secret authentication works between services
- [x] Python can send messages via Node.js API
- [x] Critical errors trigger admin alerts
- [x] 90-day retention cleanup task runs successfully
- [x] Both services start and connect via docker-compose

### 🧪 Testing Plan

#### Node.js Service Tests
- [ ] `test_gateway.test.js` (Jest):
  - Test Gateway connection with valid token
  - Test Gateway connection with invalid token
  - Test event listener registration
  - Test reconnection on disconnect
  - Mock discord-user-bots client
- [ ] `test_api.test.js`:
  - Test POST /api/discord/send endpoint
  - Test GET /api/discord/channels endpoint
  - Test GET /api/discord/history/:id endpoint
  - Test authentication (valid/invalid secret)
  - Test error responses
- [ ] `test_webhook.test.js`:
  - Test message normalization
  - Test webhook call to Python
  - Test retry logic on failure
  - Test allowlist filtering

#### Python Integration Tests
- [ ] `test_discord_client.py`:
  - Test HTTP client methods
  - Test send_message()
  - Test get_channels()
  - Test get_message_history()
  - Test auth header inclusion
  - Test timeout handling
- [ ] `test_discord_webhook.py`:
  - Test webhook endpoint receives POST
  - Test auth header validation
  - Test message parsing
  - Test message storage in DB
  - Test invalid payloads rejected
- [ ] `test_allowlist.py`:
  - Test allowlist API endpoint
  - Test add/remove channel operations
  - Test Python → Node.js sync

#### Integration Tests (Both Services)
- [ ] `test_full_flow.py`:
  - Start both services via docker-compose
  - Mock Discord message event in Node.js
  - Verify webhook called in Python
  - Verify message stored in PostgreSQL
  - Verify allowlist filtering works
  - Test send message from Python → Node.js → Discord
- [ ] `test_service_communication.py`:
  - Test inter-service auth
  - Test Node.js → Python webhook
  - Test Python → Node.js API calls
  - Test error handling when service down

#### Manual Testing
- [ ] Start services: `docker-compose up`
- [ ] Verify Node.js connects to Discord Gateway
- [ ] Send test message in Discord → verify received in Python
- [ ] Check Python logs for webhook call
- [ ] Check DB for stored message
- [ ] Test sending reply from Python
- [ ] Verify reply appears in Discord channel
- [ ] Stop Node.js service → verify Python alerts
- [ ] Restart Node.js → verify reconnection
- [ ] Test with message in non-allowed channel → verify dropped

### 📊 Component Dependencies

```mermaid
graph TB
    subgraph "Node.js Discord Service"
        A[Discord Gateway Client]
        A --> B[discord-user-bots]
        B --> C[Discord WebSocket]
        A --> D[Event Handler]
        D --> E[Message Normalizer]
        E --> F[Allowlist Filter]
        F --> G[Webhook Caller]
        H[Express API Server]
        H --> I[/api/discord/send]
        H --> J[/api/discord/channels]
        H --> K[/api/discord/history]
    end

    subgraph "Python Main Service"
        L[Webhook Endpoint]
        L --> M[Message Processor]
        M --> N[Message Storage]
        N --> O[PostgreSQL]
        P[Discord HTTP Client]
        P --> Q[HTTP Requests]
        R[Telegram Bot]
        S[Allowlist API]
        S --> O
    end

    G -->|HTTP POST| L
    Q -->|HTTP GET/POST| H
    F -->|Fetch allowlist| S
    M --> R
    P --> I

    C <-->|Gateway Protocol| T[Discord Servers]
    I -->|REST API| T

    style A fill:#90EE90
    style H fill:#90EE90
    style L fill:#FFD700
    style P fill:#FFD700
```

**Architecture Flow:**
1. Discord message → Node.js Gateway receives
2. Node.js normalizes → filters by allowlist
3. Node.js → HTTP POST to Python webhook
4. Python stores message in PostgreSQL
5. Python generates Telegram card
6. Moderator replies → Python calls Node.js API
7. Node.js sends message to Discord

### ⚠️ Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Discord account ban | Medium | Critical | Use dedicated account, monitor activity, have backup |
| Gateway protocol changes | Low | High | Pin discord-user-bots version, monitor repo updates |
| Node.js service crash | Medium | High | Auto-restart with Docker, health checks, alerting |
| Inter-service communication failure | Medium | High | Retry logic, timeouts, circuit breaker pattern |
| Network latency (Node↔Python) | Low | Low | Services in same Docker network (~1-5ms latency) |
| Rate limiting | Medium | Medium | Implement backoff in Node.js, queue in Python |
| WebSocket disconnects | High | Medium | Auto-reconnect (built-in), monitor connection state |
| Token leak | Low | Critical | Environment variables only, never log, never expose |
| Message flood (spam) | Medium | Medium | Implement message queue in Python (Iteration 7) |
| Shared secret leak | Low | High | Strong secret, rotate periodically, secure storage |
| Node.js memory leak | Low | Medium | Monitor memory usage, restart policy, profiling |

### 📝 Notes

**Architecture:**
- **Microservices pattern:** Node.js handles Discord, Python handles business logic
- **Why Node.js?** discord-user-bots is mature and actively maintained for user tokens
- **Communication:** HTTP REST between services (simple, debuggable)
- **Latency:** ~5-20ms overhead for inter-service calls (acceptable)
- **Scaling:** Can scale Node.js and Python independently in future

**Security:**
- **CRITICAL:** Using User Token violates Discord ToS - account may be banned
- **DO NOT** use main Discord account - create dedicated test account
- **Shared secret:** Generate with `openssl rand -hex 32`
- **Token security:** Never commit to Git, never log, never expose via API

**Development:**
- **DO** test each service independently before integration
- **DO** use Docker networks for service isolation
- **DO** implement comprehensive logging in both services
- **DO** document all API endpoints and payloads

**Discord Integration:**
- Gateway connection maintained by Node.js only
- Python never talks to Discord Gateway directly
- Respect rate limits: 120 requests/minute for User Token
- Test with low-volume server first before production use
- Monitor discord-user-bots GitHub for updates/issues

**Deployment:**
- Use `docker-compose up` to start both services
- Node.js service must start before Python webhook can receive events
- Python service must be ready before Node.js sends webhooks
- Use `depends_on` in docker-compose for startup order

---

## Iteration 2: Telegram Bot Core

**Duration:** 5-7 days
**Goal:** Implement Telegram bot interface with command handlers, state management, and allowlist management

**Dependencies:** Iteration 0 (Infrastructure), Iteration 1 (Discord for /add_channel testing)

### ✅ Task Checklist

#### Telegram Bot Setup
- [ ] Implement Telegram bot client in `services/telegram_service.py`:
  - Initialize bot with Bot Token
  - Set up Long Polling (or webhooks for production)
  - Register command handlers
  - Register callback query handlers
  - Error handler for bot errors
- [ ] Add bot configuration:
  - Parse mode: Plain text (no Markdown)
  - Timeout settings
  - Retry logic for API calls

#### Command Handlers
- [ ] Implement `/start` command:
  - Welcome message
  - Check if user is authorized (match `ADMIN_TELEGRAM_ID`)
  - If not authorized, reject and log attempt
  - Initialize user settings if first time
- [ ] Implement `/help` command:
  - Show all available commands
  - Brief description of each
  - Link to documentation if available
- [ ] Implement `/status` command:
  - Show Discord connection status (connected/disconnected)
  - Show DND mode status (on/off)
  - Show count of open tasks
  - Show allowlist channel count
- [ ] Implement `/add_channel` command:
  - Start conversation flow (FSM state machine)
  - Ask for channel ID or link
  - Validate channel ID format
  - Fetch channel info from Discord API
  - Confirm with user (inline keyboard: Yes/No)
  - Add to allowlist on confirmation
  - Create audit log entry
- [ ] Implement `/remove_channel` command:
  - Show current allowlist (inline keyboard buttons)
  - User selects channel to remove
  - Confirm removal
  - Remove from allowlist
  - Create audit log entry
- [ ] Implement `/list_channels` command:
  - Fetch all channels from allowlist
  - Format as list with server names
  - Handle pagination if >20 channels
- [ ] Implement `/dnd` command (placeholder for Iteration 4):
  - Basic toggle for now
  - Will be enhanced in Iteration 4

#### State Management (FSM)
- [ ] Implement Finite State Machine for conversations:
  - Use python-telegram-bot `ConversationHandler`
  - States: `WAITING_CHANNEL_ID`, `CONFIRMING_CHANNEL`, `WAITING_RESPONSE`
  - Store user context in memory (or Redis in v0.2+)
  - Timeout after 5 minutes of inactivity
- [ ] Add state transitions:
  - `/add_channel` → `WAITING_CHANNEL_ID`
  - User sends channel ID → `CONFIRMING_CHANNEL`
  - User confirms → END (add to allowlist)
  - User cancels → END
  - Timeout → END (show timeout message)

#### Callback Query Handlers
- [ ] Implement inline keyboard callbacks:
  - `add_channel_yes` - confirm adding channel
  - `add_channel_no` - cancel adding channel
  - `remove_channel_{id}` - remove specific channel
  - `show_more_context` - show more message history (Iteration 3)
  - `confirm_reply` - confirm sending reply (Iteration 3)
  - `cancel_reply` - cancel reply (Iteration 3)
  - `retry_send` - retry failed send (Iteration 3)
- [ ] Add callback query acknowledgment (answer callback query)
- [ ] Add callback data validation

#### Authorization & Security
- [ ] Implement user authorization:
  - Check `message.from_user.id` against `ADMIN_TELEGRAM_ID`
  - Reject unauthorized users immediately
  - Log unauthorized access attempts
  - Send alert to admin on repeated unauthorized attempts
- [ ] Add command rate limiting:
  - Max 10 commands per minute
  - Block user temporarily on abuse
  - Log rate limit violations

#### Error Handling
- [ ] Implement Telegram API error handling:
  - Network errors with retry
  - Invalid bot token
  - Message too long (split into chunks)
  - User blocked bot
  - Chat not found
- [ ] Add error logging:
  - Log all errors with full context
  - Create audit log entries for failures
  - Send admin alerts for critical errors

#### Testing Commands (Development)
- [ ] Implement `/test_discord` command (dev only):
  - Test Discord connection status
  - Show last received message timestamp
  - Show gateway latency
- [ ] Implement `/test_db` command (dev only):
  - Test database connection
  - Show table row counts
  - Show last migration version

### 🎯 Definition of Done

- [x] Telegram bot starts and responds to commands
- [x] `/start` command works and checks authorization
- [x] `/help` command shows all available commands
- [x] `/status` command shows current system state
- [x] `/add_channel` flow works end-to-end (FSM)
- [x] `/remove_channel` flow works with inline keyboard
- [x] `/list_channels` displays allowlist correctly
- [x] Only authorized user can use commands
- [x] Unauthorized access is rejected and logged
- [x] State machine handles conversation flows correctly
- [x] Callback queries are handled and acknowledged
- [x] Errors are caught, logged, and handled gracefully
- [x] Bot can survive restarts without losing state (if using Redis)

### 🧪 Testing Plan

#### Unit Tests
- [ ] `test_telegram_commands.py`:
  - Test each command handler logic
  - Test authorization check
  - Test command parsing
- [ ] `test_fsm.py`:
  - Test state transitions
  - Test timeout handling
  - Test context preservation
- [ ] `test_callbacks.py`:
  - Test callback query routing
  - Test callback data validation
  - Test acknowledgment

#### Integration Tests
- [ ] `test_telegram_integration.py`:
  - Test full `/add_channel` conversation flow
  - Test `/remove_channel` with database
  - Test `/status` command with real data
  - Test unauthorized access rejection
- [ ] `test_telegram_to_db.py`:
  - Test allowlist modifications persist to DB
  - Test audit log creation

#### Manual Testing
- [ ] Send `/start` as authorized user → should work
- [ ] Send `/start` as unauthorized user → should reject
- [ ] Send `/help` → should show all commands
- [ ] Send `/status` → should show Discord status
- [ ] Run `/add_channel` → complete full flow
- [ ] Run `/list_channels` → verify allowlist display
- [ ] Run `/remove_channel` → remove a channel
- [ ] Test conversation timeout (wait 5 minutes)
- [ ] Test rate limiting (send 15 commands quickly)

### 📊 Component Dependencies

```mermaid
graph TB
    A[Telegram Bot Client] --> B[Long Polling / Webhooks]
    A --> C[Command Dispatcher]
    C --> D[/start Handler]
    C --> E[/help Handler]
    C --> F[/status Handler]
    C --> G[/add_channel Handler]
    C --> H[/remove_channel Handler]
    C --> I[/list_channels Handler]
    G --> J[FSM State Machine]
    J --> K[Conversation Context]
    G --> L[Callback Query Handler]
    H --> L
    L --> M[Database Operations]
    M --> N[channels_allowlist Table]
    M --> O[audit_log Table]
    F --> P[Discord Service Status]
    P --> Q[discord_connection Table]
    A --> R[Authorization Middleware]
    R --> S[Admin ID Check]
    A --> T[Error Handler]
    T --> U[Alert Service]
```

### ⚠️ Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Telegram API rate limits | Low | Medium | Implement retry with backoff, batch operations |
| Bot token leak | Low | Critical | Store in .env, never commit, rotate if leaked |
| Unauthorized access | Medium | High | Strict ID check, log attempts, alert on abuse |
| State loss on restart | Medium | Medium | Use persistent storage (Redis/DB) in v0.2+ |
| Long message truncation | Low | Low | Detect and split messages >4096 chars |
| User blocks bot | Low | Low | Handle gracefully, log event, notify admin |

### 📝 Notes

- **DO** verify `ADMIN_TELEGRAM_ID` on every command
- **DO** use inline keyboards for better UX
- **DO NOT** use Markdown (plain text only per requirements)
- Bot username format: `@moderator_console_bot` (or similar)
- Use conversation handlers for multi-step flows
- Telegram message limit: 4096 characters
- Test bot with BotFather before deployment
- Consider using webhook instead of polling in production

---

## Iteration 3: Message Processing & Response Flow

**Duration:** 7-10 days
**Goal:** Implement core moderation workflow - message cards, context display, response composition, and confirmation

**Dependencies:** Iterations 0, 1 (Discord), 2 (Telegram Bot)

### ✅ Task Checklist

#### Message Card Generation
- [ ] Implement card formatter in `services/card_formatter.py`:
  - Build plain text message card with:
    - Platform badge (📱 Discord / 💬 Telegram)
    - Server name (for Discord)
    - Channel name
    - Thread name (if applicable)
    - Sender username + discriminator
    - Message timestamp (relative: "5 minutes ago")
    - Message content (truncate if >1000 chars)
    - Attachment indicators (🖼️ Image, 📎 File)
    - Task ID reference
  - Format example:
    ```
    📱 Discord
    Server: My Community
    Channel: #general
    From: user#1234
    5 minutes ago

    Hey, I need help with...

    🖼️ 1 image attached

    --- Context (last 10 messages) ---
    [Show More] button
    ```
- [ ] Add attachment handling in cards:
  - Download images via Telegram Bot API
  - Send as photo with card text as caption
  - For multiple attachments, send album
  - For files, send as document
  - Include alt text/filename

#### Context Display
- [ ] Implement context fetching and formatting:
  - Fetch last 10 messages from same channel
  - Format in reverse chronological order
  - Each context message shows:
    - Author username
    - Relative timestamp
    - Content (truncate if needed)
  - Format example:
    ```
    user2: Thanks! (2 min ago)
    user1: How do I...? (5 min ago)
    moderator: Check the docs (10 min ago)
    ```
- [ ] Add "Show More" button:
  - Inline keyboard button at bottom of card
  - Callback: `show_more_context:{task_id}`
  - Fetch additional 10 messages on click
  - Update message with expanded context
  - Limit to max 30 total messages

#### Response Composition
- [ ] Implement reply input handling:
  - Detect plain text message from moderator
  - Check if it's a reply to a message card
  - If yes, treat as response to that task
  - If no, ignore or show help message
- [ ] Add reply context preservation:
  - Link reply to specific task ID
  - Store draft reply in `replies` table
  - Update task status to `pending_confirmation`
  - Save timestamp

#### Response Confirmation Flow
- [ ] Implement confirmation mechanism:
  - After moderator sends reply text, show confirmation card:
    ```
    You're about to send this reply to user#1234 in #general:

    "Your message text here..."

    ✅ Confirm Send    ❌ Cancel
    ```
  - Inline keyboard with two buttons
  - Timeout after 5 minutes (cancel automatically)
- [ ] Handle confirmation actions:
  - `confirm_reply:{task_id}` callback:
    - Post reply to platform (Discord or Telegram)
    - Update task status to `answered`
    - Store sent reply in `replies` table
    - Show success message to moderator
    - Archive or delete message card (optional)
  - `cancel_reply:{task_id}` callback:
    - Delete draft reply
    - Revert task status to `open`
    - Show cancellation message

#### Discord Reply Posting
- [ ] Implement Discord message sender in `services/discord_poster.py`:
  - Use Discord REST API (`POST /channels/{channel_id}/messages`)
  - Send with User Token (same as ingestion)
  - Include reply reference if thread
  - Handle rate limits (backoff)
  - Return message ID on success
- [ ] Add error handling for Discord posting:
  - Missing permissions (403)
  - Channel not found (404)
  - Rate limit (429) - retry with backoff
  - Show error card to moderator with:
    - Error description
    - Retry button
    - Option to edit reply

#### Telegram Reply Posting
- [ ] Implement Telegram message sender in `services/telegram_poster.py`:
  - Use Bot API (`sendMessage`)
  - Send to DM chat
  - Plain text only (no formatting)
  - Handle rate limits
  - Return message ID on success
- [ ] Add error handling for Telegram posting:
  - User blocked bot
  - Chat not found
  - Message too long (split if needed)
  - Show error card with retry option

#### Task Management
- [ ] Implement task lifecycle:
  - `open` - New message received
  - `pending_confirmation` - Moderator composed reply, awaiting confirm
  - `answered` - Reply sent successfully
  - `error` - Failed to send reply
  - `muted` - Moderator chose to ignore (future)
- [ ] Add task querying:
  - Get all open tasks
  - Get task by ID
  - Get tasks by status
  - Get tasks by platform
- [ ] Implement task cleanup:
  - Auto-close tasks after 7 days if no reply
  - Archive old tasks (90-day retention)

#### Retry Mechanism
- [ ] Implement retry for failed sends:
  - Show "❌ Send Failed" message with error
  - Add inline button: "🔄 Retry"
  - Callback: `retry_send:{task_id}`
  - Re-attempt posting with same reply text
  - Max 3 retries, then mark as permanent failure
  - Alert admin on permanent failure

#### Telegram DM Ingestion (Optional for MVP)
- [ ] Implement Telegram DM handling:
  - Detect private messages to bot (not commands)
  - Create task for each DM
  - Generate message card (similar to Discord)
  - Store in database with platform=telegram
  - Apply same response flow

### 🎯 Definition of Done

- [x] Message cards are sent to Telegram for new Discord messages
- [x] Cards include all required metadata (platform, server, channel, author, timestamp)
- [x] Attachments are sent with cards (images, files)
- [x] Context (last 10 messages) is included in card
- [x] "Show More" button fetches additional context
- [x] Moderator can reply by sending text message
- [x] Reply triggers confirmation flow with inline keyboard
- [x] Confirming sends reply to original platform (Discord/Telegram)
- [x] Reply is posted successfully to Discord channel
- [x] Task status is updated to `answered` after send
- [x] Failed sends show error with retry button
- [x] Retry mechanism works (max 3 attempts)
- [x] Telegram DMs are ingested and processed (optional)
- [x] All flows create audit log entries

### 🧪 Testing Plan

#### Unit Tests
- [ ] `test_card_formatter.py`:
  - Test card generation for Discord message
  - Test card generation for Telegram DM
  - Test attachment indicators
  - Test context formatting
  - Test truncation for long messages
- [ ] `test_discord_poster.py`:
  - Test message posting logic
  - Test rate limit handling
  - Test error scenarios (403, 404, 429)
- [ ] `test_telegram_poster.py`:
  - Test message sending
  - Test message splitting (>4096 chars)
  - Test error handling
- [ ] `test_task_management.py`:
  - Test task lifecycle transitions
  - Test task querying
  - Test auto-close after 7 days

#### Integration Tests
- [ ] `test_full_response_flow.py`:
  - Mock Discord message → Card sent to Telegram
  - Moderator sends reply → Confirmation shown
  - Moderator confirms → Reply posted to Discord
  - Verify task status = `answered`
  - Verify reply stored in DB
- [ ] `test_context_display.py`:
  - Test fetching 10 messages from Discord
  - Test "Show More" pagination
  - Test max 30 message limit
- [ ] `test_retry_mechanism.py`:
  - Force send failure → Verify error card
  - Click retry → Verify re-attempt
  - Fail 3 times → Verify permanent failure alert

#### Manual Testing
- [ ] Send test message in Discord → verify card in Telegram
- [ ] Verify context shows last 10 messages
- [ ] Click "Show More" → verify additional messages
- [ ] Send reply text → verify confirmation prompt
- [ ] Click "Confirm" → verify message appears in Discord
- [ ] Verify task status = `answered` in DB
- [ ] Force error (remove bot from channel) → verify error card
- [ ] Click "Retry" → verify retry attempt
- [ ] Send message with image → verify image in card
- [ ] Send Telegram DM to bot → verify card created

### 📊 Component Dependencies

```mermaid
graph TB
    A[Discord Message Event] --> B[Card Formatter]
    B --> C[Context Fetcher]
    C --> D[Discord REST API]
    B --> E[Attachment Handler]
    E --> F[File Download]
    B --> G[Telegram Bot]
    G --> H[Send Card to Moderator]
    H --> I[Moderator Reply]
    I --> J[Reply Handler]
    J --> K[Confirmation Flow]
    K --> L{Confirmed?}
    L -->|Yes| M[Discord Poster]
    L -->|Yes| N[Telegram Poster]
    M --> O[Discord REST API]
    N --> P[Telegram Bot API]
    M --> Q[Task Manager]
    N --> Q
    Q --> R[Update Task Status]
    R --> S[PostgreSQL]
    L -->|No| T[Cancel Reply]
    T --> Q
    M -->|Error| U[Error Handler]
    N -->|Error| U
    U --> V[Show Error Card]
    V --> W[Retry Button]
    W --> M
    W --> N
```

### ⚠️ Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Message card too long (>4096 chars) | Medium | Low | Truncate content, add "Show Full" button |
| Attachment download fails | Low | Medium | Show placeholder, allow manual retry |
| Discord posting fails (permissions) | Medium | High | Show clear error, allow editing allowlist |
| Rate limit exceeded | Medium | Medium | Implement queue, backoff, warn moderator |
| Moderator sends reply to wrong message | Medium | Medium | Show task context in confirmation |
| Reply context lost on bot restart | Low | Medium | Persist drafts in DB, not memory |

### 📝 Notes

- **CRITICAL:** This is the core MVP functionality - prioritize stability over features
- **DO** include task ID in every message card for tracking
- **DO** implement confirmation to prevent accidental sends
- **DO NOT** send replies without explicit confirmation
- Message card should be easily scannable (use whitespace)
- Context should help moderator understand conversation without leaving Telegram
- Consider using Telegram reply_to_message_id for better UX
- Test with both short and long messages
- Test with different attachment types (images, GIFs, files)
- Ensure all user-facing text is clear and actionable

---

## Iteration 4: DND & Advanced Features

**Duration:** 5-7 days
**Goal:** Implement "Do Not Disturb" mode with scheduling, image/link support, and alert system

**Dependencies:** Iterations 0-3 (Full message flow must work)

### ✅ Task Checklist

#### DND Mode Implementation
- [ ] Implement DND service in `services/dnd_service.py`:
  - Toggle DND on/off
  - Store state in `settings` table
  - Query DND status before sending cards
  - Skip card sending if DND is active
  - Queue messages during DND (store in memory or DB)
- [ ] Add DND schedule support:
  - Allow multiple time windows:
    ```
    Monday-Friday: 22:00-08:00
    Saturday-Sunday: All day
    ```
  - Parse schedule from user input
  - Store as JSON in `settings.dnd_schedule`
  - Evaluate current time against schedule
  - Auto-enable/disable based on schedule

#### DND Command Enhancement
- [ ] Enhance `/dnd` command:
  - Sub-commands:
    - `/dnd on` - Enable DND immediately
    - `/dnd off` - Disable DND
    - `/dnd status` - Show current state and schedule
    - `/dnd schedule` - Start schedule configuration flow
  - Show current status when called without args
- [ ] Implement schedule configuration flow (FSM):
  - Ask for day(s): "Monday-Friday" or "Weekend" or "Every day"
  - Ask for time range: "22:00-08:00" or "All day"
  - Confirm schedule
  - Save to database
  - Show summary of all schedules
- [ ] Add schedule management:
  - `/dnd list` - Show all configured schedules
  - `/dnd remove {id}` - Remove schedule by ID
  - `/dnd clear` - Clear all schedules

#### Message Queueing During DND
- [ ] Implement message queue:
  - When DND is active, store incoming message cards in queue
  - Queue storage options:
    - In-memory list (simple, loses on restart)
    - Database table `dnd_queue` (persistent)
  - Track queued message count
- [ ] Implement queue release:
  - When DND is disabled, send all queued cards
  - Send in chronological order
  - Add indicator: "Queued while DND was active"
  - Limit burst: max 5 cards per minute to avoid flood
  - Show count: "Sending 10 queued messages..."

#### Image & Link Support
- [ ] Enhance attachment handling:
  - For images:
    - Download from Discord CDN
    - Re-upload to Telegram via `sendPhoto`
    - Send image with card text as caption
    - Fallback to URL if upload fails
  - For links in message text:
    - Detect URLs (regex)
    - Preserve formatting
    - No preview generation (plain links only per requirements)
- [ ] Handle multiple images:
  - Use Telegram `sendMediaGroup` for albums (2-10 photos)
  - First image has card text as caption
  - Others have filename/description
- [ ] Handle other file types:
  - GIFs: Send as animation
  - Videos: Send as video (if <50MB)
  - Documents: Send as document with filename

#### Alert System
- [ ] Implement alert service in `services/alert_service.py`:
  - Send critical alerts to `ADMIN_TELEGRAM_ID`
  - Alert types:
    - `DISCORD_DISCONNECTED` - Gateway connection lost
    - `DISCORD_TOKEN_INVALID` - Token rejected by Discord
    - `DISCORD_RATE_LIMITED` - Severe rate limiting
    - `DATABASE_ERROR` - DB connection failed
    - `SEND_FAILED_PERMANENT` - Reply failed after 3 retries
  - Alert format:
    ```
    🚨 CRITICAL ALERT

    Type: Discord Token Invalid
    Time: 2025-11-17 15:30:45

    Your Discord account may be banned. Please check.
    ```
- [ ] Add alert configuration:
  - Enable/disable specific alert types
  - Store in `settings` table
  - `/alerts config` command to manage

#### Audit Logging Enhancement
- [ ] Expand audit log entries:
  - Log DND mode changes (on/off, schedule updates)
  - Log alert triggers
  - Log all message sends (with recipient)
  - Log allowlist modifications
  - Log errors and retries
- [ ] Add audit log viewing:
  - `/logs` command (dev/admin only)
  - Show last 20 entries
  - Filter by type: `/logs alerts`, `/logs errors`
  - Pagination support

#### Error Recovery
- [ ] Implement automatic recovery mechanisms:
  - Discord connection: Auto-reconnect on disconnect
  - Database: Retry queries up to 3 times
  - Telegram API: Retry with exponential backoff
  - Failed sends: Queue for retry later
- [ ] Add health check:
  - Background task checking:
    - Discord connection alive
    - Database connection alive
    - Telegram bot responsive
    - Disk space >1GB free
  - Run every 60 seconds
  - Alert on unhealthy state

#### Performance Optimization
- [ ] Optimize database queries:
  - Add indexes on:
    - `messages.created_at`
    - `messages.channel_id`
    - `tasks.status`
    - `channels_allowlist.channel_id`
  - Use connection pooling (min 5, max 20)
  - Cache allowlist in memory (refresh hourly)
- [ ] Optimize Discord API calls:
  - Batch context fetching where possible
  - Cache channel/server names (refresh daily)
  - Use ETags for conditional requests

### 🎯 Definition of Done

- [x] DND mode can be toggled on/off via `/dnd` command
- [x] DND schedules can be configured and saved
- [x] Messages are queued when DND is active
- [x] Queued messages are released when DND is disabled
- [x] Schedule evaluator correctly enables/disables DND
- [x] Images are sent with message cards
- [x] Multiple images are sent as album
- [x] Links in messages are preserved
- [x] Critical alerts are sent to admin
- [x] Alert types can be configured
- [x] Audit log captures all major events
- [x] `/logs` command shows recent entries
- [x] Auto-recovery works for common failures
- [x] Health check detects unhealthy states
- [x] Database queries are optimized with indexes

### 🧪 Testing Plan

#### Unit Tests
- [ ] `test_dnd_service.py`:
  - Test DND toggle
  - Test schedule parsing
  - Test schedule evaluation (current time vs windows)
  - Test queue/dequeue operations
- [ ] `test_alert_service.py`:
  - Test alert formatting
  - Test alert filtering
  - Test alert configuration
- [ ] `test_attachment_handler.py`:
  - Test image download
  - Test image upload to Telegram
  - Test album creation
  - Test file type detection
- [ ] `test_audit_log.py`:
  - Test log entry creation
  - Test log retrieval
  - Test filtering

#### Integration Tests
- [ ] `test_dnd_flow.py`:
  - Enable DND → Send Discord message → Verify queued
  - Disable DND → Verify message delivered
  - Test schedule auto-enable at configured time
- [ ] `test_alerts_integration.py`:
  - Trigger critical error → Verify alert sent
  - Configure alert filters → Verify filtering works
- [ ] `test_image_sending.py`:
  - Discord message with image → Verify image in Telegram card
  - Discord message with 3 images → Verify album
- [ ] `test_health_check.py`:
  - Disconnect Discord → Verify unhealthy state detected
  - Reconnect → Verify healthy state restored

#### Manual Testing
- [ ] Run `/dnd on` → Send Discord message → Verify not received immediately
- [ ] Run `/dnd off` → Verify queued message delivered
- [ ] Configure schedule: "Weekdays 22:00-08:00" → Wait for time → Verify DND activates
- [ ] Send message with image in Discord → Verify image in Telegram
- [ ] Send message with 5 images → Verify album
- [ ] Force Discord disconnect → Verify alert received
- [ ] Run `/logs` → Verify entries displayed
- [ ] Run `/alerts config` → Disable alert type → Verify not sent

### 📊 Component Dependencies

```mermaid
graph TB
    A[DND Service] --> B[Settings Table]
    A --> C[Schedule Evaluator]
    C --> D[Current Time]
    A --> E[Message Queue]
    E --> F[In-Memory / DB]
    G[Message Ingestor] --> H{DND Active?}
    H -->|Yes| E
    H -->|No| I[Card Formatter]
    I --> J[Telegram Bot]
    K[Alert Service] --> L[Alert Config]
    L --> B
    K --> J
    M[Health Check] --> N[Discord Service]
    M --> O[Database]
    M --> P[Telegram Bot]
    M -->|Unhealthy| K
    Q[Audit Logger] --> R[audit_log Table]
    S[Attachment Handler] --> T[File Downloader]
    T --> U[Discord CDN]
    S --> V[Telegram sendPhoto]
    S --> W[Telegram sendMediaGroup]
```

### ⚠️ Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Queue overflow during long DND | Low | Medium | Limit queue size, alert when >100 messages |
| Schedule timezone confusion | Medium | Low | Store times in UTC, show in user's TZ |
| Image upload failures | Medium | Medium | Fallback to URL link if upload fails |
| Alert spam (too many alerts) | Low | High | Rate limit alerts, group similar alerts |
| Health check false positives | Low | Medium | Add grace period, retry before alerting |
| Performance degradation with large queue | Low | Medium | Process queue in batches, limit burst rate |

### 📝 Notes

- **DO** test DND schedules across timezone boundaries
- **DO** limit queue size to prevent memory issues (max 500 messages)
- **DO** show clear feedback when DND is active (status in `/status` command)
- **DO NOT** lose messages if queue is full - alert moderator
- Consider using cron expressions for advanced schedules in future
- Image compression may be needed for very large images (>10MB)
- Alert noise is a real problem - be conservative with alert triggers
- Health check should not spam alerts - use backoff
- Test schedule transitions (e.g., at exactly 22:00)

---

## Iteration 5: Testing & MVP Release

**Duration:** 3-5 days
**Goal:** Comprehensive testing, bug fixes, documentation, and v0.1 MVP release

**Dependencies:** Iterations 0-4 (All MVP features complete)

### ✅ Task Checklist

#### Comprehensive Testing
- [ ] Run full unit test suite:
  - Ensure all tests pass
  - Aim for >80% code coverage
  - Fix any failing tests
  - Add missing tests for edge cases
- [ ] Run integration test suite:
  - Test all major workflows end-to-end
  - Discord → Telegram → Response → Discord
  - DND mode full cycle
  - Allowlist management flow
  - Alert system
- [ ] Perform stress testing:
  - Send 100+ messages rapidly
  - Verify no message loss
  - Check memory usage stays stable
  - Monitor database query performance
  - Test rate limit handling

#### Manual Testing & Bug Fixes
- [ ] End-to-end manual testing scenarios:
  - [ ] **Scenario 1: First-time setup**
    - Fresh install → Configure tokens → Connect Discord → Add channel → Receive first message
  - [ ] **Scenario 2: Normal moderation flow**
    - Receive Discord message → View card → Reply → Confirm → Verify sent
  - [ ] **Scenario 3: DND workflow**
    - Enable DND → Send messages → Verify queued → Disable → Verify delivered
  - [ ] **Scenario 4: Error handling**
    - Force Discord disconnect → Verify alert → Reconnect → Verify recovery
  - [ ] **Scenario 5: Image handling**
    - Send message with 1 image → 3 images → 10 images → Verify all cases
  - [ ] **Scenario 6: Multiple channels**
    - Add 5 channels → Receive messages from each → Verify proper tagging
- [ ] Document all found bugs in GitHub Issues
- [ ] Fix critical and high-priority bugs
- [ ] Defer low-priority bugs to backlog

#### Performance Optimization
- [ ] Profile code for bottlenecks:
  - Use Python profilers (cProfile, line_profiler)
  - Identify slow queries
  - Optimize hot paths
- [ ] Optimize database:
  - Run EXPLAIN on slow queries
  - Add missing indexes
  - Vacuum/analyze tables
- [ ] Optimize memory usage:
  - Check for memory leaks
  - Limit in-memory caches
  - Clean up old objects

#### Documentation
- [ ] Update `README.md`:
  - Clear installation instructions
  - Configuration guide
  - Quick start guide
  - Troubleshooting section
- [ ] Create `DEPLOYMENT.md` (update existing):
  - Docker Compose setup steps
  - Environment variables reference
  - Database migration steps
  - Monitoring recommendations
- [ ] Create `USER_GUIDE.md`:
  - How to use the bot
  - List of all commands with examples
  - DND mode usage
  - Allowlist management
  - Troubleshooting common issues
- [ ] Document code:
  - Add docstrings to all functions
  - Comment complex logic
  - Update inline comments
- [ ] Create `CHANGELOG.md`:
  - Document v0.1 features
  - Known limitations
  - Next steps (v0.2 preview)

#### Security Review
- [ ] Security checklist:
  - [ ] No plaintext tokens in logs
  - [ ] All tokens encrypted in database
  - [ ] `.env` file in `.gitignore`
  - [ ] No secrets in Docker image
  - [ ] Telegram bot authorization working
  - [ ] SQL injection prevention (parameterized queries)
  - [ ] Input validation on all user inputs
  - [ ] Rate limiting enabled
  - [ ] Audit logging captures sensitive operations
- [ ] Run security scan:
  - Use `bandit` for Python security linting
  - Check dependencies with `safety` or `pip-audit`
  - Fix any high/critical vulnerabilities

#### MVP Release Preparation
- [ ] Version tagging:
  - Update version to `v0.1.0` in code
  - Create git tag: `v0.1.0`
  - Update CHANGELOG.md
- [ ] Build release artifacts:
  - Docker image build and tag
  - Test image in clean environment
  - Push to Docker Hub (optional)
- [ ] Create GitHub Release:
  - Release notes summarizing v0.1 features
  - Installation instructions
  - Known issues
  - Link to documentation
- [ ] Deployment to production:
  - Deploy to production server
  - Run database migrations
  - Configure environment variables
  - Test in production
  - Monitor for first 24 hours

#### Post-Release Monitoring
- [ ] Set up monitoring:
  - Log aggregation (check log files)
  - Error tracking (monitor audit_log)
  - Health check results
  - Database size and growth
- [ ] Monitor for issues:
  - Watch for errors in first 48 hours
  - Respond to critical issues immediately
  - Collect user feedback (if any)
- [ ] Plan v0.2:
  - Review backlog
  - Prioritize features for v0.2
  - Create v0.2 milestone

### 🎯 Definition of Done

- [x] All unit tests passing (>80% coverage)
- [x] All integration tests passing
- [x] Stress testing completed successfully
- [x] All manual test scenarios pass
- [x] Critical and high-priority bugs fixed
- [x] Performance is acceptable (no obvious bottlenecks)
- [x] Documentation complete (README, USER_GUIDE, DEPLOYMENT)
- [x] Code is documented with docstrings
- [x] Security review passed
- [x] No high/critical security vulnerabilities
- [x] Version tagged as v0.1.0
- [x] Release published on GitHub
- [x] Deployed to production successfully
- [x] Monitoring in place
- [x] No critical issues in first 48 hours

### 🧪 Testing Plan

This iteration is primarily testing, so the test plan is the task checklist itself.

#### Acceptance Criteria (Must Pass)
- [ ] User can install from scratch following README
- [ ] User can configure Discord and Telegram tokens
- [ ] User can receive Discord messages in Telegram
- [ ] User can reply to messages successfully
- [ ] DND mode works as expected
- [ ] Allowlist management works correctly
- [ ] Alerts are sent for critical errors
- [ ] System recovers from common failures
- [ ] No data loss under normal operation
- [ ] Performance is acceptable (<2s for message delivery)

### 📊 Component Dependencies

```mermaid
graph TB
    A[Iteration 5: Testing & Release] --> B[Unit Tests]
    A --> C[Integration Tests]
    A --> D[Manual Testing]
    A --> E[Bug Fixes]
    E --> F[Code Quality]
    A --> G[Documentation]
    G --> H[README]
    G --> I[USER_GUIDE]
    G --> J[DEPLOYMENT]
    G --> K[CHANGELOG]
    A --> L[Security Review]
    L --> M[Vulnerability Scan]
    A --> N[Release Artifacts]
    N --> O[Docker Image]
    N --> P[Git Tag]
    N --> Q[GitHub Release]
    A --> R[Deployment]
    R --> S[Production Server]
    S --> T[Monitoring]
```

### ⚠️ Risks & Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Critical bugs found late | Medium | High | Extensive manual testing, staged rollout |
| Performance issues in production | Medium | Medium | Load testing, monitoring, rollback plan |
| Documentation gaps | Low | Low | User testing of docs, peer review |
| Security vulnerabilities | Low | Critical | Security scan, code review, rapid patching |
| Deployment failures | Low | Medium | Test deployment in staging, rollback plan |
| Post-release critical bugs | Medium | High | 24/7 monitoring first week, hotfix readiness |

### 📝 Notes

- **CRITICAL:** Do not release until all acceptance criteria are met
- **DO** test installation from scratch in clean environment
- **DO** have rollback plan ready before production deployment
- **DO NOT** skip security review
- **DO** monitor actively for first 48-72 hours post-release
- Keep v0.1 scope minimal - defer non-critical features to v0.2
- Document known limitations clearly in release notes
- Celebrate the MVP release! 🎉
- Use semantic versioning: v0.1.0 = MVP, v0.2.0 = LLM features, v1.0.0 = Production-ready

---

## PHASE 2: v0.2 - LLM Integration

**Goal:** Enhance moderation workflow with AI-powered response suggestions and automation

**Duration:** 2-3 weeks (3 iterations)

**Core Features:**
- LLM-generated response variants (2-3 options)
- "Soften" function (rephrase to polite tone)
- Message queues with BullMQ/Celery
- Enhanced rate limiting
- Optional reminder system

---

## Iteration 6: LLM Integration

**Duration:** 7-10 days
**Goal:** Integrate OpenAI/Anthropic LLM for response generation and tone adjustment

**Dependencies:** Phase 1 complete (MVP v0.1 released)

### ✅ Task Checklist

#### LLM Service Setup
- [ ] Choose LLM provider (OpenAI GPT-4 or Anthropic Claude)
- [ ] Implement `services/llm_service.py`:
  - API client initialization
  - Token management and cost tracking
  - Rate limiting (requests per minute)
  - Error handling and retries
  - Response caching (optional)
- [ ] Add LLM configuration to `.env`:
  - `LLM_PROVIDER` (openai or anthropic)
  - `LLM_API_KEY`
  - `LLM_MODEL` (gpt-4, claude-3-sonnet, etc.)
  - `LLM_MAX_TOKENS`
  - `LLM_TEMPERATURE`

#### Response Variant Generation
- [ ] Implement response suggestion feature:
  - Input: Original Discord message + context
  - Output: 2-3 response variants with different tones:
    - Formal/professional
    - Friendly/casual
    - Concise/brief
  - Each variant 50-200 chars
  - Plain text only (no Markdown)
- [ ] Add variant display to message cards:
  - Show variants as numbered inline buttons:
    ```
    Suggested replies:
    1️⃣ Formal    2️⃣ Friendly    3️⃣ Concise
    ✏️ Write Custom
    ```
  - Callback: `use_variant:{task_id}:{variant_num}`
  - Show selected variant in confirmation
- [ ] Implement custom reply flow:
  - "Write Custom" button preserves existing flow
  - Moderator types own response
  - Both flows end in same confirmation step

#### "Soften" Function
- [ ] Implement tone adjustment feature:
  - Input: Moderator's draft reply
  - Output: Softened/polite version
  - Preserve meaning, adjust tone only
  - Remove harsh words, add politeness markers
- [ ] Add "Soften" button to confirmation card:
  - Show alongside "Confirm" and "Cancel"
  - Callback: `soften_reply:{task_id}`
  - Replace draft with softened version
  - Show comparison (before/after)
  - Re-confirm before sending

#### Prompt Engineering
- [ ] Design response generation prompt:
  ```
  You are a helpful community moderator. A user sent the following message:

  [MESSAGE CONTENT]

  Recent conversation context:
  [CONTEXT]

  Generate 3 brief reply options (50-200 chars each) in different tones:
  1. Formal/professional
  2. Friendly/casual
  3. Concise/brief

  Use plain text only, no formatting.
  ```
- [ ] Design softening prompt:
  ```
  Rewrite the following message to be more polite and friendly while preserving the meaning:

  [ORIGINAL MESSAGE]

  Output plain text only, no formatting.
  ```
- [ ] Test prompts with various message types:
  - Questions
  - Complaints
  - Feedback
  - Spam reports

#### Cost Management
- [ ] Implement token usage tracking:
  - Count tokens for each API call
  - Store in database (`llm_usage` table - add via migration)
  - Calculate approximate cost
  - Alert if daily cost exceeds budget
- [ ] Add usage dashboard:
  - `/llm_stats` command showing:
    - Total requests today/week/month
    - Total tokens consumed
    - Estimated cost
    - Most expensive operation types
- [ ] Implement cost controls:
  - Max requests per day (configurable)
  - Max cost per day (alert threshold)
  - Disable LLM if budget exceeded
  - Fallback to manual mode

### 🎯 Definition of Done

- [x] LLM API integration works (OpenAI or Anthropic)
- [x] Response variants generated for incoming messages
- [x] 2-3 variants with different tones displayed
- [x] Moderator can select variant with inline button
- [x] "Soften" function rewrites drafts to polite tone
- [x] Token usage tracked and cost calculated
- [x] Daily budget alerts working
- [x] Custom reply flow still available
- [x] LLM errors handled gracefully (fallback to manual)
- [x] Cost dashboard (`/llm_stats`) shows accurate data

### 📝 Notes

- Start with GPT-4-mini or Claude-3-haiku for lower costs
- Cache common responses to reduce API calls
- Consider using streaming for faster perceived response
- Test thoroughly with non-English messages if needed
- Prompt engineering is iterative - refine based on output quality

---

## Iteration 7: Queue System & Rate Limiting

**Duration:** 5-7 days
**Goal:** Implement message queues for reliability and enhanced rate limiting for Discord API

**Dependencies:** Iteration 6 (LLM integration)

### ✅ Task Checklist

#### Message Queue Setup
- [ ] Choose queue system:
  - Python: Celery + Redis
  - Node.js: BullMQ + Redis
- [ ] Set up Redis:
  - Add Redis to `docker-compose.yml`
  - Configure connection in backend
  - Test connection
- [ ] Implement queue workers:
  - Worker for Discord message processing
  - Worker for LLM API calls
  - Worker for message sending (Discord/Telegram)
  - Worker for cleanup tasks

#### Queue-Based Processing
- [ ] Migrate critical operations to queues:
  - Incoming Discord messages → Queue for processing
  - LLM response generation → Queue with retry
  - Outgoing message sends → Queue with rate limiting
  - DND queue release → Background job
- [ ] Add queue monitoring:
  - Track queue lengths
  - Alert if queue growing (>100 items)
  - Dead letter queue for failed jobs
  - Retry logic (max 3 attempts)

#### Enhanced Rate Limiting
- [ ] Implement Discord API rate limiter:
  - Track requests per endpoint
  - 50 requests per second global
  - 5 requests per second per channel
  - Queue requests when limit approached
  - Backoff when 429 received
- [ ] Add rate limit dashboard:
  - Current rate limit status
  - Requests remaining
  - Time until reset
  - Queue depth

#### Task Reminders (Optional Feature)
- [ ] Implement reminder system:
  - If task unanswered after 24h, send reminder
  - If task unanswered after 48h, send escalation
  - Option to snooze reminder (4h, 12h, 24h)
  - Option to mute task permanently
- [ ] Add reminder commands:
  - `/remind {task_id} in {duration}` - Custom reminder
  - `/snooze {task_id}` - Snooze current reminder
  - `/mute {task_id}` - Permanently mute task

### 🎯 Definition of Done

- [x] Redis running in Docker Compose
- [x] Celery/BullMQ workers running
- [x] Message processing queued
- [x] LLM calls queued and rate-limited
- [x] Discord API rate limits respected
- [x] Queue monitoring dashboard accessible
- [x] Failed jobs retry automatically
- [x] Reminders sent for old tasks (optional)
- [x] All queues drain properly on shutdown

### 📝 Notes

- Redis persistence should be configured (AOF or RDB)
- Monitor Redis memory usage
- Consider separate queues for high/low priority tasks
- Test queue behavior under high load

---

## Iteration 8: Advanced v0.2 Features & Release

**Duration:** 3-5 days
**Goal:** Polish LLM features, enhanced allowlist management, and v0.2 release

**Dependencies:** Iterations 6-7 complete

### ✅ Task Checklist

#### Enhanced Allowlist Management
- [ ] Add bulk allowlist operations:
  - `/add_server {server_id}` - Add all channels from server
  - `/remove_server {server_id}` - Remove all channels from server
  - `/import_allowlist` - Import from JSON file
  - `/export_allowlist` - Export to JSON file
- [ ] Add channel filtering:
  - Filter by server
  - Filter by channel type (text/voice/thread)
  - Search by name

#### LLM Feature Enhancements
- [ ] Add context awareness to LLM:
  - Include last 5 messages in prompt
  - Include user's previous messages (if available)
  - Detect recurring issues
- [ ] Add variant preferences:
  - Track which variants moderator selects most
  - Adapt tone over time
  - Store preference in `settings`
- [ ] Add LLM disable toggle:
  - `/llm off` - Disable LLM suggestions
  - `/llm on` - Re-enable LLM
  - Fallback to manual mode when disabled

#### Testing & Bug Fixes
- [ ] Test LLM edge cases:
  - Very long messages (>2000 chars)
  - Non-English messages
  - Code blocks in messages
  - Special characters
- [ ] Test queue system:
  - High load (100+ messages)
  - Worker crashes and recovery
  - Redis disconnect
  - Queue overflow
- [ ] Fix discovered bugs

#### v0.2 Release
- [ ] Update documentation:
  - Document LLM features in USER_GUIDE
  - Update CHANGELOG for v0.2
  - Document queue configuration
- [ ] Version bump to v0.2.0
- [ ] Create GitHub release
- [ ] Deploy to production
- [ ] Monitor for 48 hours

### 🎯 Definition of Done

- [x] Enhanced allowlist commands working
- [x] LLM context-aware responses improved
- [x] LLM can be disabled via command
- [x] All v0.2 features tested
- [x] Documentation updated
- [x] v0.2.0 released and deployed
- [x] No critical issues in first 48h

### 📝 Notes

- v0.2 should feel significantly more intelligent than v0.1
- User feedback on LLM quality is crucial
- Monitor LLM costs closely in production
- Consider A/B testing different prompts

---

## PHASE 3: v1.0 - Production Ready

**Goal:** Add advanced features for production use: multi-server support, search, analytics, and full polish

**Duration:** 3-4 weeks (3 iterations)

**Core Features:**
- Multi-server Discord support
- Edit sent messages
- Search message history
- Statistics and metrics
- Quick reply templates
- Health check API
- Complete documentation

---

## Iteration 9: Multi-server & Advanced UI

**Duration:** 7-10 days
**Goal:** Support multiple Discord servers and enhance UI with quick actions

**Dependencies:** Phase 2 complete (v0.2 released)

### ✅ Task Checklist

#### Multi-server Support
- [ ] Update database schema:
  - Add `server_id` to all relevant tables
  - Add `servers` table for server metadata
  - Migration for existing data
- [ ] Update Discord service:
  - Track multiple server connections
  - Support multiple gateway connections (if needed)
  - Filter events by server
- [ ] Update allowlist:
  - Group channels by server
  - `/list_servers` - Show all connected servers
  - `/add_server` - Add entire server to allowlist
  - Server-based filtering in UI

#### Message Editing
- [ ] Implement edit sent messages:
  - Store sent message IDs in database
  - `/edit {task_id}` - Edit previous reply
  - Fetch original, allow editing
  - Update on Discord/Telegram
  - Track edit history in audit log
- [ ] Add edit UI:
  - "✏️ Edit" button on sent confirmations
  - Show before/after comparison
  - Confirm edit before applying

#### Quick Reply Templates
- [ ] Implement template system:
  - Store templates in `reply_templates` table
  - `/template add {name} {text}` - Create template
  - `/template list` - Show all templates
  - `/template delete {name}` - Remove template
  - `/template use {name} {task_id}` - Use template for reply
- [ ] Add template UI:
  - Show templates as inline buttons on message cards
  - "📋 Templates" button → Show template list
  - Select template → Pre-fill reply
  - Allow editing before confirming

#### Enhanced Message Cards
- [ ] Add quick actions to cards:
  - 👍 Quick Approve (send pre-defined reply)
  - 🚫 Quick Reject (send pre-defined rejection)
  - 📌 Pin (mark as important)
  - 🔇 Mute (ignore this task)
  - ⏭️ Skip (deal with later)
- [ ] Add card customization:
  - Configurable card format
  - Show/hide context by default
  - Show/hide LLM suggestions
  - Color coding by priority (optional)

### 🎯 Definition of Done

- [x] Multiple Discord servers supported
- [x] Server-based allowlist management working
- [x] Sent messages can be edited
- [x] Reply templates can be created and used
- [x] Quick action buttons functional
- [x] Multi-server tested with 3+ servers
- [x] Edit history tracked in audit log
- [x] Templates stored and retrieved correctly

### 📝 Notes

- Test with different server sizes (small, medium, large)
- Ensure server names are clear in all UI elements
- Quick actions should feel fast and intuitive
- Templates are personal productivity feature - keep simple

---

## Iteration 10: Search & Analytics

**Duration:** 5-7 days
**Goal:** Add message search, statistics dashboard, and analytics

**Dependencies:** Iteration 9 complete

### ✅ Task Checklist

#### Message Search
- [ ] Implement search functionality:
  - `/search {query}` - Search message content
  - Search filters:
    - By server
    - By channel
    - By date range
    - By sender
    - By status (answered/open/muted)
  - Full-text search on message content
  - Return paginated results (10 per page)
- [ ] Add search index:
  - PostgreSQL full-text search (tsvector)
  - Index on message content
  - Optimize search queries
- [ ] Search results UI:
  - Show matches with context
  - Highlight search terms
  - Link to original task
  - Show task status

#### Statistics Dashboard
- [ ] Implement `/stats` command:
  - Overall statistics:
    - Total messages received (all-time, this month, this week)
    - Total replies sent
    - Average response time
    - Messages per channel/server
  - Response statistics:
    - Response rate (% of messages answered)
    - Busiest hours/days
    - Most active channels
  - LLM statistics:
    - Variant selection frequency
    - Soften function usage
    - Token costs
  - DND statistics:
    - Time in DND mode
    - Messages queued
- [ ] Add statistics storage:
  - `statistics` table for aggregated data
  - Daily aggregation job
  - Historical trends (7 days, 30 days, 90 days)

#### Analytics & Insights
- [ ] Generate insights:
  - Identify busiest channels (suggest priority)
  - Identify slow response times
  - Detect patterns (recurring questions)
  - Suggest templates for common replies
- [ ] Add insights to `/stats`:
  - "Top 3 busiest channels this week"
  - "Average response time increased 20%"
  - "5 unanswered messages older than 24h"

#### Export & Reports
- [ ] Implement data export:
  - `/export messages {date_range}` - Export to JSON
  - `/export stats` - Export statistics to CSV
  - Include metadata and context
  - Respect 90-day retention limit

### 🎯 Definition of Done

- [x] Search works across all messages
- [x] Search filters functional
- [x] Full-text search indexed and fast
- [x] `/stats` shows comprehensive statistics
- [x] Statistics accurate and up-to-date
- [x] Insights generated and useful
- [x] Data export works (JSON/CSV)
- [x] Historical trends displayed correctly

### 📝 Notes

- Search should be fast (<500ms for typical queries)
- Statistics should help identify issues and improvements
- Insights should be actionable, not just informative
- Consider privacy when exporting data

---

## Iteration 11: Final Polish & v1.0 Release

**Duration:** 5-7 days
**Goal:** Complete documentation, final testing, production hardening, v1.0 release

**Dependencies:** All previous iterations complete

### ✅ Task Checklist

#### Health Check API
- [ ] Implement HTTP health check endpoint:
  - `GET /health` - Overall health status
  - `GET /health/detailed` - Component-level status
  - Check:
    - Discord connection
    - Database connection
    - Redis connection
    - Telegram bot connection
    - Disk space
    - Memory usage
  - Return JSON with status codes
- [ ] Add Prometheus metrics (optional):
  - Expose `/metrics` endpoint
  - Track request counts, latencies
  - Track queue depths
  - Track error rates

#### Production Hardening
- [ ] Security hardening:
  - Review all authentication points
  - Ensure HTTPS for all external APIs
  - Validate all inputs rigorously
  - Rate limit all endpoints
  - Security audit with automated tools
- [ ] Performance optimization:
  - Profile production workload
  - Optimize slow queries
  - Add caching where appropriate
  - Load testing (simulate 1000+ messages/day)
- [ ] Reliability improvements:
  - Circuit breakers for external APIs
  - Graceful degradation when services down
  - Data backup strategy (despite no-backup policy, document recovery)
  - Disaster recovery plan

#### Complete Documentation
- [ ] User documentation:
  - Complete USER_GUIDE with screenshots/examples
  - FAQ section
  - Troubleshooting guide
  - Command reference
- [ ] Admin documentation:
  - DEPLOYMENT guide with step-by-step
  - OPERATIONS guide (monitoring, backups, etc.)
  - TROUBLESHOOTING for common issues
  - SCALING guide (if needed for future)
- [ ] Developer documentation:
  - CODE_STRUCTURE.md - Architecture overview
  - CONTRIBUTING.md - For future contributors
  - API.md - Internal API documentation (update existing)
  - Comment all complex code

#### Final Testing
- [ ] End-to-end testing:
  - Fresh installation test
  - Upgrade test (v0.2 → v1.0)
  - All features tested systematically
  - Load testing
  - Failure recovery testing
- [ ] User acceptance testing:
  - Run through all user scenarios
  - Verify all commands work
  - Verify all features accessible
  - No broken flows
- [ ] Security testing:
  - Penetration testing (basic)
  - Vulnerability scanning
  - Dependency audit
  - Fix all critical/high issues

#### v1.0 Release
- [ ] Pre-release checklist:
  - All tests passing
  - All documentation complete
  - Security review passed
  - Performance acceptable
  - No known critical bugs
- [ ] Version management:
  - Update version to v1.0.0
  - Update CHANGELOG comprehensively
  - Create git tag `v1.0.0`
  - Write detailed release notes
- [ ] Release process:
  - Create GitHub Release
  - Publish Docker images
  - Update documentation site (if any)
  - Announce release
- [ ] Post-release:
  - Deploy to production
  - Monitor for 72 hours
  - Address any issues immediately
  - Collect feedback
  - Plan v1.1 features

#### Celebration & Retrospective
- [ ] Document lessons learned
- [ ] Identify what went well
- [ ] Identify areas for improvement
- [ ] Celebrate the v1.0 release! 🎉🎊

### 🎯 Definition of Done

- [x] Health check API working
- [x] All documentation complete and accurate
- [x] Security audit passed
- [x] Load testing successful
- [x] Fresh install works perfectly
- [x] Upgrade path tested
- [x] v1.0.0 tagged and released
- [x] Deployed to production
- [x] No critical issues in first 72h
- [x] Project is production-ready!

### 📝 Notes

- **DO NOT** rush v1.0 - quality over speed
- v1.0 means production-ready - act accordingly
- Documentation quality reflects overall project quality
- Health checks are essential for production monitoring
- Have rollback plan ready
- This is a milestone worth celebrating properly!
- Consider open-sourcing or sharing (if applicable)

---

## Dependencies Map

### Full Iteration Dependencies

```mermaid
graph TB
    I0[Iteration 0: Infrastructure] --> I1[Iteration 1: Discord]
    I0 --> I2[Iteration 2: Telegram Bot]
    I1 --> I3[Iteration 3: Message Processing]
    I2 --> I3
    I3 --> I4[Iteration 4: DND & Advanced]
    I4 --> I5[Iteration 5: Testing & MVP]

    I5 --> I6[Iteration 6: LLM Integration]
    I6 --> I7[Iteration 7: Queue System]
    I7 --> I8[Iteration 8: v0.2 Release]

    I8 --> I9[Iteration 9: Multi-server]
    I9 --> I10[Iteration 10: Search & Analytics]
    I10 --> I11[Iteration 11: v1.0 Release]

    style I5 fill:#90EE90
    style I8 fill:#FFD700
    style I11 fill:#FF6B6B
```

**Legend:**
- 🟢 Green = MVP v0.1 Release
- 🟡 Yellow = v0.2 Release
- 🔴 Red = v1.0 Release

---

## Risk Management

Comprehensive project-level risks across all iterations.

### High Priority Risks

| Risk | Iterations | Probability | Impact | Mitigation |
|------|-----------|-------------|--------|------------|
| **Discord Account Ban** | 1, 3, 4, 6+ | Medium | Critical | Dedicated test account, minimal activity, backup accounts ready |
| **Discord Protocol Changes** | 1, 6+ | Low | High | Pin library versions, monitor community, quick response plan |
| **LLM Cost Overrun** | 6-8 | Medium | High | Daily budget alerts, cost caps, cheaper models, caching |
| **Data Loss** | 0, 3+ | Low | High | Regular exports, document recovery procedures, monitor disk |
| **Performance Degradation** | 3, 7, 10 | Medium | Medium | Profiling, indexing, load testing, monitoring |
| **Security Vulnerability** | All | Low | Critical | Security scans, code reviews, dependency audits, quick patching |

### Mitigation Timeline

**Phase 1 (MVP):**
- Focus on core stability and error handling
- Implement basic monitoring and alerts
- Document recovery procedures

**Phase 2 (LLM):**
- Add cost tracking and budget alerts
- Implement queue-based reliability
- Enhanced error recovery

**Phase 3 (Production):**
- Full security audit
- Load testing and optimization
- Production monitoring and health checks

---

## Timeline Summary

### Optimistic Timeline (Best Case)

| Phase | Duration | Cumulative |
|-------|----------|------------|
| **Phase 1: MVP v0.1** | 4 weeks | 4 weeks |
| **Phase 2: v0.2 (LLM)** | 2 weeks | 6 weeks |
| **Phase 3: v1.0 (Production)** | 3 weeks | **9 weeks total** |

### Realistic Timeline (Expected)

| Phase | Duration | Cumulative |
|-------|----------|------------|
| **Phase 1: MVP v0.1** | 5 weeks | 5 weeks |
| **Phase 2: v0.2 (LLM)** | 3 weeks | 8 weeks |
| **Phase 3: v1.0 (Production)** | 4 weeks | **12 weeks total** |

### Pessimistic Timeline (Worst Case)

| Phase | Duration | Cumulative |
|-------|----------|------------|
| **Phase 1: MVP v0.1** | 6 weeks | 6 weeks |
| **Phase 2: v0.2 (LLM)** | 4 weeks | 10 weeks |
| **Phase 3: v1.0 (Production)** | 5 weeks | **15 weeks total** |

**Recommendation:** Plan for **12 weeks (realistic)** with buffer for unexpected issues.

---

## Key Metrics & Success Criteria

### MVP v0.1 Success Metrics
- ✅ Can receive and display Discord messages in Telegram
- ✅ Can reply to messages with confirmation
- ✅ DND mode works and queues messages
- ✅ No critical bugs in first week
- ✅ Average message delivery latency <2 seconds
- ✅ Uptime >95% in first month

### v0.2 Success Metrics
- ✅ LLM generates useful response variants
- ✅ "Soften" function improves tone
- ✅ LLM daily cost stays under budget
- ✅ Queue system prevents message loss
- ✅ Response time for moderator improved by 30%

### v1.0 Success Metrics
- ✅ Supports 3+ Discord servers simultaneously
- ✅ Search returns relevant results <500ms
- ✅ Statistics dashboard shows actionable insights
- ✅ Can handle 1000+ messages/day
- ✅ Uptime >99% over 30 days
- ✅ All documentation complete and accurate

---

## Development Best Practices

### Throughout All Iterations

1. **Testing First**
   - Write tests before or alongside implementation
   - Maintain >80% code coverage
   - Run tests before every commit
   - Integration tests for critical flows

2. **Incremental Development**
   - Complete one iteration before starting next
   - Mark tasks as complete immediately after finishing
   - Deploy and test each iteration
   - Get feedback early and often

3. **Documentation**
   - Document as you build, not after
   - Keep README updated
   - Add docstrings to all functions
   - Maintain CHANGELOG

4. **Security**
   - Never commit secrets
   - Encrypt sensitive data at rest
   - Validate all user inputs
   - Regular security scans

5. **Performance**
   - Profile before optimizing
   - Add indexes as needed
   - Monitor resource usage
   - Load test before major releases

6. **Git Workflow**
   - Use conventional commits (feat:, fix:, docs:, etc.)
   - Create feature branches
   - Meaningful commit messages
   - Tag all releases (v0.1.0, v0.2.0, v1.0.0)

---

## Resource Requirements

### Development Resources
- **Developer Time:** 1 developer, ~20-30 hours/week
- **Testing Time:** ~20% of development time
- **Documentation Time:** ~15% of development time

### Infrastructure Resources

**MVP v0.1:**
- Server: 2 vCPU, 4GB RAM, 20GB SSD
- Database: PostgreSQL (included in server)
- Estimated cost: $20-30/month

**v0.2 (with LLM & Redis):**
- Server: 2 vCPU, 4GB RAM, 30GB SSD
- LLM API: ~$10-50/month (depends on usage)
- Estimated cost: $40-90/month

**v1.0 (Production):**
- Server: 4 vCPU, 8GB RAM, 50GB SSD
- LLM API: ~$50-100/month
- Monitoring: $10-20/month (optional)
- Estimated cost: $80-150/month

### Third-Party Services
- Discord: Free (using User Token - against ToS)
- Telegram Bot API: Free
- OpenAI API: Pay-per-use (~$0.03-0.06 per 1K tokens)
- Anthropic API: Pay-per-use (~$3-15 per 1M tokens)

---

## Next Steps

### After Completing This Plan

1. **Choose Your Starting Point:**
   - ✅ Iteration 0 if starting from scratch
   - ✅ Later iteration if you have partial implementation

2. **Set Up Your Environment:**
   - Clone/create repository
   - Set up development environment
   - Install dependencies
   - Configure .env file

3. **Begin Iteration 0:**
   - Follow task checklist step-by-step
   - Test each component as you build
   - Mark tasks complete in this document
   - Move to next iteration when DoD is met

4. **Track Progress:**
   - Update checkboxes in this document
   - Create GitHub issues for bugs
   - Use GitHub Projects for kanban board (optional)
   - Regular commits with conventional format

5. **Iterate and Adapt:**
   - This plan is a guide, not a contract
   - Adjust timelines based on actual progress
   - Defer non-critical features if needed
   - Focus on DoD criteria

---

## Appendix: Command Reference

Quick reference of all bot commands across versions.

### MVP v0.1 Commands
- `/start` - Initialize bot
- `/help` - Show help
- `/status` - Show system status
- `/add_channel` - Add channel to allowlist
- `/remove_channel` - Remove channel from allowlist
- `/list_channels` - List all allowed channels
- `/dnd [on|off|status|schedule]` - Manage DND mode
- `/logs` - View audit logs

### v0.2 Commands (Additional)
- `/llm_stats` - Show LLM usage statistics
- `/llm [on|off]` - Toggle LLM suggestions
- `/alerts config` - Configure alert preferences
- `/remind {task_id} in {duration}` - Set task reminder
- `/snooze {task_id}` - Snooze reminder
- `/mute {task_id}` - Mute task permanently

### v1.0 Commands (Additional)
- `/list_servers` - Show all connected servers
- `/add_server {server_id}` - Add entire server
- `/template add/list/delete/use` - Manage reply templates
- `/edit {task_id}` - Edit sent message
- `/search {query}` - Search message history
- `/stats` - Show statistics dashboard
- `/export messages/stats` - Export data

---

## Final Notes

This iteration plan provides a **comprehensive roadmap** for building the Moderator project from zero to v1.0 production-ready release.

**Key Takeaways:**
- **11 iterations** across **3 phases** (~12 weeks realistic timeline)
- **Incremental delivery:** Each iteration produces working, testable functionality
- **Flexible structure:** Adjust as needed based on feedback and discoveries
- **Quality-focused:** Testing, documentation, and security at every step
- **Clear milestones:** v0.1 (MVP), v0.2 (LLM), v1.0 (Production)

**Success Factors:**
1. Follow the plan but adapt when necessary
2. Complete each iteration's DoD before moving forward
3. Test early and test often
4. Document as you go
5. Monitor and iterate based on real usage

**Remember:**
- This is a marathon, not a sprint
- Quality > Speed
- User feedback is invaluable
- Celebrate milestones! 🎉

Good luck building the Moderator! 🚀

---

**Document Version:** 1.0
**Last Updated:** 2025-11-17
**Maintained By:** Development Team

