# Allowlist Management Implementation Analysis

**Analysis Date:** 2025-11-18
**Codebase:** Discord-to-Telegram Moderator Bot
**Version Target:** v0.2 Requirements (Section 5: Команды управления allowlist)

---

## 1. ROADMAP REQUIREMENTS (v0.2, Section 5)

From `/home/user/moderator/docs/ROADMAP.md` (lines 143-146):

```
#### 5. Команды управления allowlist (1 день)
- [ ] Улучшенный /allow_channel (с диалогом выбора)
- [ ] /unallow_channel
- [ ] Список allowlist в /settings
```

**Current Status:** ⚠️ PARTIALLY IMPLEMENTED (commands exist but need improvements)

---

## 2. CURRENT IMPLEMENTATION SUMMARY

### What's WORKING ✅

#### 2.1 Database Schema (channels_allowlist table)
- **Location:** `/home/user/moderator/migrations/001_initial_schema.sql` (lines 62-82)
- **Table Structure:**
  ```sql
  CREATE TABLE channels_allowlist (
      id BIGSERIAL PRIMARY KEY,
      platform VARCHAR(50) NOT NULL,  -- 'discord' | 'telegram'
      server_id VARCHAR(255),          -- Discord guild ID (NULL for Telegram)
      channel_id VARCHAR(255) NOT NULL,
      thread_filter_json TEXT,         -- JSON with thread filters (optional)
      enabled BOOLEAN NOT NULL DEFAULT true,
      created_at TIMESTAMP NOT NULL DEFAULT NOW(),
      updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
      UNIQUE(platform, server_id, channel_id)
  );
  ```
- **Indexes:** platform, enabled, channel_id for fast queries
- **Status:** ✅ Fully functional with proper constraints and indexes

#### 2.2 Allowlist Service (Async)
- **Location:** `/home/user/moderator/backend/src/services/allowlist.py`
- **Functions Implemented:**
  - `async is_channel_allowed()` - checks if channel should be monitored
  - `async add_channel_to_allowlist()` - adds channel with optional thread filters
  - `async remove_channel_from_allowlist()` - disables channel (soft delete)
  - `async get_allowlist_channels()` - retrieves all channels with filtering
- **Status:** ✅ Complete with thread filtering support

#### 2.3 Allowlist DAO (Async - asyncpg)
- **Location:** `/home/user/moderator/backend/src/database/dao/allowlist_dao.py` (428 lines)
- **Methods:**
  - `add_channel()` - upsert with RETURNING id
  - `remove_channel()` - hard delete
  - `is_channel_allowed()` - with thread filter checking
  - `get_all_channels()` - with platform and enabled filters
  - `get_channel_by_id()` - retrieve specific entry
  - `update_channel_enabled()` - toggle enabled flag
  - `update_thread_filter()` - modify thread restrictions
  - `count_channels()` - get total count
- **Status:** ✅ Comprehensive with all CRUD operations

#### 2.4 Allowlist DAO (Sync - SQLAlchemy)
- **Location:** `/home/user/moderator/backend/src/database/dao.py` (lines 362-525)
- **Methods:**
  - `add_channel()` - works with session_scope()
  - `remove_channel()` - works with session_scope()
  - `get_all_channels()` - returns List[Dict]
  - `is_channel_allowed()` - simple boolean check
- **Status:** ✅ Works but synchronous (used in Telegram handlers)

#### 2.5 Telegram Commands (Partial)
- **Location:** `/home/user/moderator/backend/src/telegram/handlers.py`

**a) /allow_channel Command (lines 350-407)**
```python
async def cmd_allow_channel(message: dict, bot: 'TelegramBot'):
    """
    Handle /allow_channel command.
    Usage: /allow_channel <server_id> <channel_id>
    """
```
- **Current Implementation:**
  - Requires 2 parameters: server_id, channel_id
  - Basic validation (numeric IDs)
  - Direct database insert (upsert)
  - Simple success/error messages
- **Status:** ✅ WORKING but needs improvement

**b) /unallow_channel Command (lines 409-453)**
```python
async def cmd_unallow_channel(message: dict, bot: 'TelegramBot'):
    """
    Handle /unallow_channel command.
    Usage: /unallow_channel <channel_id>
    """
```
- **Current Implementation:**
  - Requires channel_id only
  - Numeric validation
  - Removes from allowlist
  - Simple success/error messages
- **Status:** ✅ WORKING

#### 2.6 Allowlist Usage in Core Systems

**Discord Gateway Message Processing:**
- **Location:** `/home/user/moderator/backend/src/discord/gateway.py` (lines 590-610)
- **Usage:** Checks if channel is allowed before processing MESSAGE_CREATE event
```python
is_allowed = await AllowlistDAO.is_channel_allowed(
    conn=conn,
    platform='discord',
    channel_id=channel_id,
    server_id=guild_id,
    thread_id=thread_id
)
if not is_allowed:
    logger.info(f"Message {message_id} skipped: channel {channel_id} not in allowlist")
    return
```
- **Status:** ✅ Properly integrated

**Main.py Discord Integration:**
- **Location:** `/home/user/moderator/backend/src/main.py` (lines 382-396)
- **Usage:** Uses async `is_channel_allowed()` from services
- **Status:** ✅ Integrated

#### 2.7 Status Command Integration
- **Location:** `/home/user/moderator/backend/src/telegram/handlers.py` (lines 216-259)
- **Current Display:**
```python
channels = AllowlistDAO.get_all_channels(session, platform='discord')
channel_count = len(channels)
```
- **Shows:** Only count of allowed channels
- **Status:** ⚠️ Minimal - no details about channels

#### 2.8 Settings Command
- **Location:** `/home/user/moderator/backend/src/telegram/handlers.py` (lines 456-489)
- **Current Status:**
```
📋 Monitoring:
  • Channels: 0
  • Allowlist: Empty
```
- **Status:** ❌ HARDCODED - doesn't show actual allowlist

---

## 3. WHAT NEEDS TO BE IMPLEMENTED

### 3.1 Enhanced /allow_channel with Dialog Selection ❌

**ROADMAP Requirement:** "Улучшенный /allow_channel (с диалогом выбора)"

**Current Implementation Issues:**
1. **Manual ID Entry Required:** User must provide server_id and channel_id manually
2. **No Server Discovery:** Doesn't list available Discord servers
3. **No Channel Listing:** Doesn't show channels within a server
4. **Poor UX:** Requires users to find IDs themselves

**What Should Be Implemented:**

Option 1: **Multi-step Dialog (Recommended)**
```
User: /allow_channel
Bot: "Select a Discord server:"
      [Dropdown/Buttons with server names]
User: Selects server
Bot: "Select channel(s) to monitor:"
      [Checkbox list of channels]
User: Selects channels
Bot: Confirms and adds to allowlist
```

Option 2: **Interactive Selection with State Machine (FSM)**
- Use FSM states: `awaiting_server_selection`, `awaiting_channel_selection`
- Store server_id in user state
- Show inline keyboard with servers from Discord connection
- Show channels for selected server

**Technical Requirements:**
- Fetch guild list from Discord using user's token
- Fetch channel list from guild
- Implement FSM dialog flow
- Update cmd_allow_channel to support interactive mode

**Code Location to Modify:**
- `/home/user/moderator/backend/src/telegram/handlers.py` - cmd_allow_channel (lines 350-407)

---

### 3.2 /unallow_channel Implementation Status ⚠️

**Current Status:** Command exists and works but minimal features

**Issues:**
1. Single channel removal only (can't batch remove)
2. No confirmation dialog
3. No listing of current allowlist before removal
4. No option to choose from existing allowlist

**What Should Be Enhanced:**

```
User: /unallow_channel
Bot: "Current monitored channels:"
      1. Server A > Channel 1
      2. Server A > Channel 2
      3. Server B > Channel 3
      
      "Select channel to remove (or /cancel):"
User: Selects channel
Bot: Confirms removal
```

**Code Location:**
- `/home/user/moderator/backend/src/telegram/handlers.py` - cmd_unallow_channel (lines 409-453)

---

### 3.3 Allowlist Display in /settings ❌

**ROADMAP Requirement:** "Список allowlist в /settings"

**Current Status:** Hardcoded empty message

**Current Code (lines 456-489):**
```python
settings_text = """⚙️ Current Settings
...
📋 Monitoring:
  • Channels: 0
  • Allowlist: Empty
```

**What Should Be Implemented:**

Enhanced /settings command showing:
```
📋 Monitoring:
  • Total Channels: 3
  • Active Allowlist:
    ✅ Discord > Server Name > #general
    ✅ Discord > Server Name > #moderation
    ✅ Discord > Server Name > #support
  
[Buttons:]
[+ Add Channel] [- Remove Channel] [Edit Filters]
```

**Requirements:**
1. Query allowlist from database
2. Fetch Discord server/channel names (requires Discord API calls)
3. Format human-readable display
4. Show thread filters if present
5. Add action buttons for managing allowlist

**Code Location:**
- `/home/user/moderator/backend/src/telegram/handlers.py` - cmd_settings (lines 456-489)

---

## 4. CODE STRUCTURE & ARCHITECTURE

### 4.1 Layer Architecture

```
┌─────────────────────────────────────────────┐
│ Telegram Bot (handlers.py)                   │
│ Commands: /allow_channel, /unallow_channel   │
└──────────────────┬──────────────────────────┘
                   │
         ┌─────────▼──────────┐
         │ Services Layer     │
         │ services/          │
         │ allowlist.py       │
         └─────────┬──────────┘
                   │
      ┌────────────▼──────────────┐
      │ DAO Layer (asyncpg)        │
      │ database/dao/              │
      │ allowlist_dao.py           │
      └─────────┬──────────────────┘
                │
    ┌───────────▼──────────────┐
    │ Database                 │
    │ channels_allowlist table  │
    └──────────────────────────┘
```

### 4.2 Dual DAO Implementation

**Problem:** Code uses TWO different DAO implementations:

1. **Async DAO (asyncpg)** - `/home/user/moderator/backend/src/database/dao/allowlist_dao.py`
   - Used in: Discord Gateway, main.py, services
   - Methods: async-compatible with `await`

2. **Sync DAO (SQLAlchemy)** - `/home/user/moderator/backend/src/database/dao.py` (lines 362-525)
   - Used in: Telegram handlers (with session_scope())
   - Methods: blocking operations

**Impact:** Inconsistent usage patterns - should consolidate to async throughout

---

## 5. DETAILED CODE LOCATIONS

| Component | File | Lines | Status |
|-----------|------|-------|--------|
| Database Schema | `migrations/001_initial_schema.sql` | 62-82 | ✅ |
| Async Service | `services/allowlist.py` | 1-440 | ✅ |
| Async DAO | `database/dao/allowlist_dao.py` | 1-428 | ✅ |
| Sync DAO | `database/dao.py` | 362-525 | ✅ |
| /allow_channel | `telegram/handlers.py` | 350-407 | ⚠️ Needs enhancement |
| /unallow_channel | `telegram/handlers.py` | 409-453 | ⚠️ Needs enhancement |
| /status | `telegram/handlers.py` | 216-259 | ⚠️ Shows count only |
| /settings | `telegram/handlers.py` | 456-489 | ❌ Hardcoded |
| Discord Filtering | `discord/gateway.py` | 590-610 | ✅ |
| Tests | `tests/test_integration.py` | 836-900 | ✅ Partial |

---

## 6. IMPROVEMENTS NEEDED FOR v0.2 ROADMAP

### High Priority (v0.2 Sprint)

| Item | Priority | Effort | Status |
|------|----------|--------|--------|
| Enhanced /allow_channel with dialog | HIGH | 2-3 days | ❌ NOT DONE |
| /unallow_channel with selection | HIGH | 1 day | ⚠️ PARTIAL |
| /settings allowlist display | HIGH | 1-2 days | ❌ NOT DONE |
| Channel name resolution (Discord) | MEDIUM | 1 day | ⚠️ May need Discord API |

### Technical Debt

1. **Consolidate DAO layer** - Use async DAO consistently
2. **Add confirmations** - Dialog confirmation for destructive operations
3. **Add batch operations** - Allow multiple channels add/remove
4. **Thread filter UI** - Add UI for advanced thread filtering
5. **Audit logging** - Log all allowlist changes

---

## 7. EXAMPLE IMPLEMENTATION NEEDS

### 7.1 Data Structure for Enhanced /allow_channel

```python
class DiscordServer:
    id: str
    name: str
    icon_url: Optional[str]
    owner_id: str
    
class DiscordChannel:
    id: str
    name: str
    type: str  # 'text' | 'voice' | 'category' | 'thread'
    topic: Optional[str]

class AllowlistEntry:
    server_id: str
    server_name: str
    channel_id: str
    channel_name: str
    platform: str
    enabled: bool
    thread_filters: Optional[Dict]
```

### 7.2 FSM States Needed

```
States for /allow_channel:
- awaiting_server_selection
- awaiting_channel_selection
- confirming_addition

States for /unallow_channel:
- showing_allowlist
- awaiting_channel_selection
- confirming_removal
```

---

## 8. TEST COVERAGE

**Current Tests:** `/home/user/moderator/tests/test_integration.py` (lines 836-900)

**What's Tested:**
- ✅ AllowlistDAO.is_channel_allowed()
- ✅ Allowlist filtering in message processing
- ✅ Basic CRUD operations

**What's NOT Tested:**
- ❌ /allow_channel command dialog
- ❌ /unallow_channel command selection
- ❌ /settings display with allowlist
- ❌ Thread filter handling
- ❌ Discord server/channel name resolution
- ❌ Batch operations

---

## 9. SUMMARY

### What's Working ✅
1. Database schema with proper constraints
2. Allowlist service layer (async)
3. DAO implementations (both async and sync)
4. Core /allow_channel command (basic)
5. Core /unallow_channel command (basic)
6. Discord message filtering by allowlist
7. Basic status reporting

### What Needs Work ❌
1. **Dialog-based channel selection** for /allow_channel
2. **Enhanced /unallow_channel** with channel listing
3. **Dynamic /settings display** showing actual allowlist
4. **Channel name resolution** from Discord
5. **Confirmation dialogs** for user safety
6. **Comprehensive test suite** for new features

### Effort Estimate for v0.2
- Enhanced /allow_channel: 2-3 days
- Enhanced /unallow_channel: 1 day
- /settings display: 1-2 days
- Testing: 1 day
- **Total: 5-7 days** (matches ROADMAP estimate of 1 day - requires 5-7x more work than estimated)

---

## 10. RECOMMENDATIONS

1. **Start with /settings display** - Easier to implement, high visibility
2. **Then enhance /allow_channel** - More complex, needs FSM and Discord API integration
3. **Enhance /unallow_channel** - Medium complexity
4. **Add comprehensive tests** - Before merging to main
5. **Consider consolidating DAOs** - Currently using async and sync versions inconsistently

