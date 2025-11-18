# Reminder System Integration Guide

## Overview

The Reminder System has been implemented in `backend/src/services/reminders.py` and provides periodic notifications for open tasks.

## Features

- **Periodic Scanning**: Scans open tasks every 30 minutes
- **Smart Filtering**: Only sends reminders when appropriate:
  - Respects DND (Do Not Disturb) mode
  - Checks user reminder preferences
  - Limits to 3 reminders per task
  - Only reminds for tasks older than 30 minutes
  - Respects 30-minute interval between reminders
- **Formatted Notifications**: Sends rich Markdown-formatted messages via Telegram
- **Logging**: Comprehensive logging for monitoring and debugging

## Integration with main.py

To integrate the Reminder System into your application, add the following to `backend/src/main.py`:

### 1. Import the reminder service

Add to imports section:
```python
from services.reminders import start_reminder_scheduler, stop_reminder_scheduler
```

### 2. Initialize in ModeratorApplication.__init__()

Add instance variable:
```python
def __init__(self):
    # ... existing code ...
    self._reminder_task: Optional[asyncio.Task] = None
```

### 3. Start in ModeratorApplication.start()

Add after starting other components:
```python
async def start(self):
    # ... existing code for telegram_bot and discord_gateway ...

    # Start reminder service (after telegram_bot is started)
    logger.info("Starting reminder service...")
    self._reminder_task = asyncio.create_task(
        start_reminder_scheduler(self.telegram_bot),
        name="reminder_service"
    )

    # ... rest of start method ...
```

### 4. Stop in ModeratorApplication.stop()

Add cleanup:
```python
async def stop(self):
    # ... existing stop code ...

    # Stop reminder service
    if self._reminder_task and not self._reminder_task.done():
        logger.info("Stopping reminder service...")
        await stop_reminder_scheduler()
        self._reminder_task.cancel()
        try:
            await self._reminder_task
        except asyncio.CancelledError:
            pass
        logger.info("Reminder service stopped")

    # ... rest of stop method ...
```

## Configuration

The reminder system uses these constants (defined in `reminders.py`):

- `REMINDER_INTERVAL_MINUTES = 30`: How often to scan for tasks needing reminders
- `MAX_REMINDERS = 3`: Maximum number of reminders per task
- `MIN_TASK_AGE_MINUTES = 30`: Minimum age before first reminder

These can be adjusted as needed by modifying the constants in the file.

## User Settings

Users can control reminders via their settings in the database:

```sql
-- Enable/disable reminders for a user
UPDATE settings
SET reminders_enabled = TRUE
WHERE user_id = <user_id>;

-- Check current setting
SELECT reminders_enabled, dnd_enabled, dnd_schedule_json
FROM settings
WHERE user_id = <user_id>;
```

## Testing

To test the reminder system:

1. Create an open task in the database
2. Ensure the task is older than 30 minutes
3. Set `reminders_enabled = TRUE` for the user
4. Wait for the next scan interval (up to 30 minutes)
5. Check Telegram for the reminder notification

Or manually trigger a scan:
```python
from services.reminders import get_reminder_service

# Get service instance
service = get_reminder_service()

# Manually trigger scan (for testing)
await service.scan_and_send_reminders()
```

## Monitoring

Check logs for reminder activity:

```bash
# View reminder service logs
grep "ReminderService" /var/log/moderator/app_*.log

# View reminder scan results
grep "Reminder scan" /var/log/moderator/app_*.log

# View sent reminders
grep "Sent reminder for task" /var/log/moderator/app_*.log
```

## Troubleshooting

### Reminders not being sent

Check the following:

1. **Service running**: Look for "Reminder service started" in logs
2. **User settings**: Verify `reminders_enabled = TRUE` in database
3. **DND mode**: Check if DND is active for the user
4. **Task age**: Ensure task is older than MIN_TASK_AGE_MINUTES
5. **Max reminders**: Check if task has reached MAX_REMINDERS
6. **Database connection**: Verify asyncpg pool is initialized

### Telegram send failures

If reminders fail to send:

1. Check Telegram bot token in config
2. Verify bot has started successfully
3. Check network connectivity
4. Review Telegram API errors in logs

## Architecture

### Flow Diagram

```
Scheduler (every 30min)
    ↓
scan_and_send_reminders()
    ↓
Get all open tasks from database
    ↓
For each task:
    ↓
    _should_send_reminder()
    ├─ Check max reminders
    ├─ Check task age
    ├─ Check time since update
    ├─ Check user settings
    └─ Check DND mode
        ↓
    If should send:
        ↓
        _send_reminder()
        ├─ Get message details
        ├─ Build reminder text
        └─ Send via Telegram
            ↓
        Increment reminder_count
```

### Database Schema

The reminder system uses these tables:

- `tasks`: Contains `reminder_count`, `created_at`, `updated_at`
- `settings`: Contains `reminders_enabled`, `dnd_enabled`, `dnd_schedule_json`
- `messages`: Contains source message details for context

## API Reference

### Functions

#### `start_reminder_scheduler(telegram_bot)`

Entry point for starting the reminder scheduler.

**Args:**
- `telegram_bot`: TelegramBot instance for sending notifications

**Returns:**
- `ReminderService` instance

#### `stop_reminder_scheduler()`

Stop the reminder scheduler gracefully.

#### `get_reminder_service()`

Get the singleton reminder service instance.

**Returns:**
- `ReminderService` instance or None if not initialized

### ReminderService Class

#### Methods

- `start()`: Start the periodic scheduler
- `stop()`: Stop the scheduler gracefully
- `scan_and_send_reminders()`: Main scan function (can be called manually)

## Changes Made

### Files Created

- `backend/src/services/reminders.py`: Complete reminder system implementation

### Files Modified

- `backend/src/telegram/bot.py`: Added `parse_mode` parameter to `send_message()` method to support Markdown formatting

## Version

- **Phase**: 4 - Reminder System
- **Version**: v0.2 Iteration 5+
- **Status**: Ready for integration
