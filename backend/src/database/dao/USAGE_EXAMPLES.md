# DAO Layer Usage Examples

This document provides practical examples of how to use the Data Access Object (DAO) layer for database operations.

## Table of Contents
- [Setup](#setup)
- [MessageDAO Examples](#messagedao-examples)
- [TaskDAO Examples](#taskdao-examples)
- [ReplyDAO Examples](#replydao-examples)
- [UserDAO Examples](#userdao-examples)
- [DiscordDAO Examples](#discorddao-examples)
- [AllowlistDAO Examples](#allowlistdao-examples)
- [AttachmentDAO Examples](#attachmentdao-examples)
- [AuditDAO Examples](#auditdao-examples)

## Setup

```python
import asyncpg
from database.dao import (
    MessageDAO, TaskDAO, ReplyDAO, UserDAO,
    DiscordDAO, AllowlistDAO, AttachmentDAO, AuditDAO
)

# Establish database connection
DATABASE_URL = "postgresql://user:pass@localhost:5432/moderator_db"
conn = await asyncpg.connect(DATABASE_URL)

# Use connection pool for production
pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=5,
    max_size=20
)
```

## MessageDAO Examples

### Create a new message
```python
from datetime import datetime

message_id = await MessageDAO.create_message(
    conn=conn,
    platform='discord',
    ext_message_id='1234567890',
    channel_id='9876543210',
    author_id='1111111111',
    author_name='JohnDoe',
    content='Hello, world!',
    server_id='5555555555',
    has_image=True,
    platform_created_at=datetime.utcnow()
)
print(f"Created message with ID: {message_id}")
```

### Retrieve message by external ID
```python
message = await MessageDAO.get_message_by_external_id(
    conn, 'discord', '1234567890'
)
if message:
    print(f"Content: {message['content']}")
    print(f"Author: {message['author_name']}")
```

### Get recent messages from a channel
```python
messages = await MessageDAO.get_messages_by_channel(
    conn,
    platform='discord',
    channel_id='9876543210',
    limit=50
)
for msg in messages:
    print(f"{msg['author_name']}: {msg['content']}")
```

### Get context messages for AI processing
```python
from datetime import datetime

context = await MessageDAO.get_context_messages(
    conn,
    channel_id='9876543210',
    thread_id=None,
    before_timestamp=datetime.utcnow(),
    limit=10
)
```

## TaskDAO Examples

### Create a task
```python
task_id = await TaskDAO.create_task(
    conn=conn,
    source_message_id=123,
    assignee_user_id=1
)
```

### Get open tasks for a user
```python
open_tasks = await TaskDAO.get_open_tasks(conn, user_id=1)
print(f"You have {len(open_tasks)} open tasks")
for task in open_tasks:
    print(f"Task {task['id']}: Created at {task['created_at']}")
```

### Update task status
```python
# Mark task as answered
await TaskDAO.mark_task_answered(conn, task_id=42)

# Mark task as error
await TaskDAO.update_task_status(
    conn,
    task_id=42,
    status='error',
    error_message='Failed to post reply to Discord'
)
```

### Link Telegram card to task
```python
await TaskDAO.update_task_card_id(
    conn,
    task_id=42,
    tg_card_message_id=999
)
```

## ReplyDAO Examples

### Create a human reply
```python
reply_id = await ReplyDAO.create_reply(
    conn=conn,
    task_id=42,
    content='Thank you for your message!',
    generated_by='human'
)
```

### Create an LLM-generated reply
```python
reply_id = await ReplyDAO.create_reply(
    conn=conn,
    task_id=42,
    content='I can help you with that.',
    generated_by='llm',
    llm_confidence=0.92
)
```

### Confirm and post a reply
```python
# Confirm reply
await ReplyDAO.mark_reply_confirmed(conn, reply_id=123)

# Mark as posted
import json
platform_ref = json.dumps({
    "platform": "discord",
    "message_id": "999888777"
})
await ReplyDAO.mark_reply_posted(conn, reply_id=123, platform_ref=platform_ref)
```

### Get all replies for a task
```python
replies = await ReplyDAO.get_replies_for_task(conn, task_id=42)
for reply in replies:
    print(f"{reply['generated_by']}: {reply['content']}")
    print(f"Confirmed: {reply['confirmed']}")
```

## UserDAO Examples

### Create or get user
```python
# Get or create user (idempotent)
user = await UserDAO.get_or_create_user(
    conn,
    tg_user_id=123456789,
    username='moderator1'
)
print(f"User ID: {user['id']}")
```

### Manage user settings
```python
import json

# Create default settings
await UserDAO.create_default_settings(conn, user_id=1)

# Update DND settings
dnd_schedule = json.dumps({
    "start": "22:00",
    "end": "08:00",
    "timezone": "UTC"
})
await UserDAO.update_dnd_settings(
    conn,
    user_id=1,
    dnd_enabled=True,
    dnd_schedule_json=dnd_schedule
)

# Get settings
settings = await UserDAO.get_user_settings(conn, user_id=1)
print(f"DND enabled: {settings['dnd_enabled']}")
```

## DiscordDAO Examples

### Save Discord connection
```python
from database.encryption import encrypt_token

# Encrypt token before saving
encrypted_token = encrypt_token('discord_user_token_here')

conn_id = await DiscordDAO.save_discord_connection(
    conn=conn,
    user_id=1,
    encrypted_token=encrypted_token,
    super_properties='{"os":"Windows","browser":"Chrome"}'
)
```

### Get decrypted Discord token
```python
from database.encryption import decrypt_token

token = await DiscordDAO.get_discord_token(
    conn,
    user_id=1,
    decrypt_func=decrypt_token
)
# Use token for Discord API calls
```

### Update connection status
```python
# Connected
await DiscordDAO.update_connection_status(
    conn,
    user_id=1,
    status='connected',
    session_id='abc123xyz'
)

# Disconnected
await DiscordDAO.clear_session(conn, user_id=1)

# Error
await DiscordDAO.update_connection_status(
    conn,
    user_id=1,
    status='error',
    error_message='Authentication failed'
)
```

## AllowlistDAO Examples

### Add channels to allowlist
```python
# Add Discord channel
await AllowlistDAO.add_channel(
    conn=conn,
    platform='discord',
    channel_id='9876543210',
    server_id='1111111111'
)

# Add Telegram channel
await AllowlistDAO.add_channel(
    conn=conn,
    platform='telegram',
    channel_id='telegram_chat_id'
)
```

### Check if channel is allowed
```python
allowed = await AllowlistDAO.is_channel_allowed(
    conn,
    platform='discord',
    channel_id='9876543210',
    server_id='1111111111'
)
if allowed:
    # Process message
    pass
```

### Manage thread filters
```python
import json

# Allow only specific threads
thread_filter = json.dumps({
    "allowed_threads": ["123", "456", "789"]
})
await AllowlistDAO.update_thread_filter(
    conn,
    channel_id='9876543210',
    thread_filter_json=thread_filter,
    platform='discord'
)
```

## AttachmentDAO Examples

### Create attachments
```python
import json

# Single attachment
meta = json.dumps({
    "size": 2048,
    "type": "image/jpeg",
    "width": 800,
    "height": 600
})
attachment_id = await AttachmentDAO.create_attachment(
    conn=conn,
    message_id=123,
    kind='image',
    ref='https://cdn.discord.com/attachments/...',
    meta=meta
)

# Bulk create
attachments = [
    {
        "message_id": 123,
        "kind": "image",
        "ref": "https://example.com/image1.jpg",
        "meta": '{"size": 1024}'
    },
    {
        "message_id": 123,
        "kind": "link",
        "ref": "https://example.com",
        "meta": None
    }
]
ids = await AttachmentDAO.bulk_create_attachments(conn, attachments)
```

### Get attachments
```python
# Get all attachments for a message
attachments = await AttachmentDAO.get_attachments_for_message(conn, 123)

# Get only images
images = await AttachmentDAO.get_images_for_message(conn, 123)
for img in images:
    print(f"Image URL: {img['ref']}")

# Check if message has attachments
has_images = await AttachmentDAO.has_attachments(conn, 123, kind='image')
```

## AuditDAO Examples

### Log events
```python
import json

# Log user login
payload = json.dumps({
    "action": "login",
    "ip_address": "192.168.1.1",
    "user_agent": "TelegramBot/1.0"
})
await AuditDAO.log_event(
    conn=conn,
    kind='user.login',
    payload_json=payload,
    user_id=1
)

# Log message received
payload = json.dumps({
    "platform": "discord",
    "channel_id": "9876543210",
    "message_id": "1234567890"
})
await AuditDAO.log_event(
    conn=conn,
    kind='message.received',
    payload_json=payload
)
```

### Query logs
```python
from datetime import datetime, timedelta

# Get recent logs
recent = await AuditDAO.get_recent_logs(conn, limit=50)

# Get logs by type
logins = await AuditDAO.get_logs_by_kind(
    conn,
    kind='user.login',
    limit=20
)

# Get logs for specific user
user_logs = await AuditDAO.get_logs_by_user(conn, user_id=1, limit=100)

# Get logs in time range
start = datetime.utcnow() - timedelta(hours=24)
end = datetime.utcnow()
logs = await AuditDAO.get_logs_in_timerange(
    conn,
    start_time=start,
    end_time=end,
    kind='error.occurred'
)

# Get event statistics
stats = await AuditDAO.get_event_statistics(conn)
for stat in stats:
    print(f"{stat['kind']}: {stat['count']} events")
```

## Using Connection Pools

For production, always use connection pools:

```python
# Create pool
pool = await asyncpg.create_pool(
    DATABASE_URL,
    min_size=5,
    max_size=20
)

# Use pool with context manager
async with pool.acquire() as conn:
    message_id = await MessageDAO.create_message(
        conn=conn,
        platform='discord',
        ext_message_id='123',
        channel_id='456',
        author_id='789',
        content='Hello!'
    )

# Close pool when done
await pool.close()
```

## Transaction Examples

```python
# Using transactions
async with pool.acquire() as conn:
    async with conn.transaction():
        # Create message
        message_id = await MessageDAO.create_message(
            conn, 'discord', '123', '456', '789', 'Hello'
        )

        # Create task
        task_id = await TaskDAO.create_task(
            conn, message_id, assignee_user_id=1
        )

        # Log event
        import json
        payload = json.dumps({"message_id": message_id, "task_id": task_id})
        await AuditDAO.log_event(
            conn, 'task.created', payload, user_id=1
        )

        # If any operation fails, entire transaction rolls back
```

## Error Handling

```python
import asyncpg

try:
    message_id = await MessageDAO.create_message(
        conn,
        platform='discord',
        ext_message_id='123',
        channel_id='456',
        author_id='789',
        content='Hello'
    )
except asyncpg.UniqueViolationError:
    print("Message already exists")
    # Get existing message
    message = await MessageDAO.get_message_by_external_id(
        conn, 'discord', '123'
    )
except asyncpg.PostgresError as e:
    print(f"Database error: {e}")
    # Log error
    import json
    payload = json.dumps({"error": str(e)})
    await AuditDAO.log_event(
        conn, 'error.occurred', payload
    )
```

## Best Practices

1. **Always use connection pools** in production for better performance
2. **Use transactions** for operations that need to be atomic
3. **Handle exceptions** gracefully and log errors to audit log
4. **Close connections** when done to prevent resource leaks
5. **Use type hints** when calling DAO methods for better IDE support
6. **Validate input** before passing to DAO methods
7. **Log important events** using AuditDAO for debugging and security
8. **Use pagination** for queries that might return many results
9. **Encrypt sensitive data** before storing (especially Discord tokens)
10. **Clean up old audit logs** periodically to manage database size
