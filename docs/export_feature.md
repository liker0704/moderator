# Export/Anonymization Feature - v1.0 Iteration 7

## Overview

The export feature allows users to export all their moderator data to JSON format, with optional anonymization for privacy protection. This feature is part of v1.0 Iteration 7 of the moderator project.

## Features

### 1. Data Export
- Export all user data to a single JSON file
- Includes:
  - All messages from monitored channels
  - All tasks created
  - All replies sent
  - User settings
  - Channel allowlist
  - Quick reply templates
  - LLM requests (optional)

### 2. Anonymization
- Replace usernames with generic identifiers (User_1, User_2, etc.)
- Replace channel IDs with generic IDs (Channel_1, Channel_2, etc.)
- Replace server IDs with generic IDs (Server_1, Server_2, etc.)
- Keep message content intact
- Remove platform-specific references
- Remove Telegram card message IDs

### 3. Export Preview
- View statistics about what will be exported
- Shows counts for all data types
- No actual export performed

## Commands

### `/export`
Exports all user data to JSON without anonymization.

**Usage:**
```
/export
```

**Output:**
- JSON file sent as Telegram document
- Filename format: `moderator_export_{user_id}_{timestamp}.json`
- File includes all data with original values

### `/export anonymize`
Exports all user data with anonymization applied.

**Usage:**
```
/export anonymize
```

**Output:**
- JSON file sent as Telegram document
- Filename format: `moderator_export_{user_id}_anonymized_{timestamp}.json`
- All personal identifiers replaced with generic values

### `/export preview`
Shows preview of export statistics without creating a file.

**Usage:**
```
/export preview
```

**Output:**
```
📊 Export Preview

📨 Messages: 1,234
📋 Tasks: 567
💬 Replies: 543
✅ Allowlist Entries: 15
📝 Templates: 8
🤖 LLM Requests: 890

Use /export to export all data
Use /export anonymize to export with anonymization
```

## JSON Export Format

```json
{
  "export_date": "2025-11-19T12:00:00Z",
  "user_id": 123,
  "anonymized": false,
  "counts": {
    "messages": 1234,
    "tasks": 567,
    "replies": 543,
    "allowlist": 15,
    "templates": 8,
    "llm_requests": 0
  },
  "data": {
    "messages": [
      {
        "id": 1,
        "platform": "discord",
        "ext_message_id": "1234567890",
        "channel_id": "9876543210",
        "server_id": "1111111111",
        "author_id": "2222222222",
        "author_name": "JohnDoe",
        "content": "Message content",
        "has_image": false,
        "created_at": "2025-11-19T10:00:00",
        "platform_created_at": "2025-11-19T10:00:00"
      }
    ],
    "tasks": [...],
    "replies": [...],
    "settings": {...},
    "allowlist": [...],
    "templates": [...]
  }
}
```

## Anonymized Export Format

When anonymization is enabled, the export looks like:

```json
{
  "export_date": "2025-11-19T12:00:00Z",
  "user_id": "anonymized",
  "anonymized": true,
  "counts": {...},
  "data": {
    "messages": [
      {
        "id": 1,
        "platform": "discord",
        "ext_message_id": "msg_1",
        "channel_id": "Channel_1",
        "server_id": "Server_1",
        "author_id": "User_1",
        "author_name": "User_1",
        "content": "Message content",
        "has_image": false,
        "created_at": "2025-11-19T10:00:00",
        "platform_created_at": "2025-11-19T10:00:00"
      }
    ],
    ...
  }
}
```

## Implementation Details

### Architecture

The export feature consists of three main components:

1. **ExportDAO** (`backend/src/database/dao/export_dao.py`)
   - Data retrieval from database
   - Queries for all data types
   - Export statistics generation

2. **ExportService** (`backend/src/services/export.py`)
   - Business logic for export
   - Anonymization logic
   - JSON file generation
   - File cleanup

3. **Command Handlers** (`backend/src/telegram/handlers.py`)
   - `/export` command handling
   - Progress messages
   - File sending via Telegram

### Database Queries

The export feature retrieves data using JOIN queries to ensure only user-specific data is exported:

- **Messages**: Joined with `channels_allowlist` to get only monitored channels
- **Tasks**: Filtered by `assignee_user_id`
- **Replies**: Joined through tasks to ensure user ownership
- **Settings**: Direct user_id match
- **Allowlist**: Filtered by user_id (if column exists)
- **Templates**: Filtered by user_id
- **LLM Requests**: Joined through tasks to ensure user ownership

### Anonymization Logic

Anonymization uses a mapping dictionary to ensure consistency:

1. First occurrence of a user ID → `User_1`
2. Second occurrence of a user ID → `User_2`
3. Same for channels and servers

This ensures that the same user always gets the same anonymous ID within a single export.

### File Handling

1. Export files are created in `/tmp` directory
2. Files are sent via Telegram's `send_document` API
3. Files are automatically cleaned up after sending
4. File creation errors are handled gracefully

## Testing

Comprehensive unit tests are provided in `backend/tests/test_export.py`:

- Serialization tests (datetime, Decimal, None)
- Anonymization tests (messages, tasks, replies, allowlist)
- Export generation tests
- File creation and cleanup tests
- Export preview tests
- DAO method tests

### Running Tests

```bash
cd backend
pytest tests/test_export.py -v
```

## Security Considerations

1. **Access Control**: Export commands require authenticated Telegram user
2. **Data Filtering**: Only user's own data is exported
3. **File Cleanup**: Temporary files are deleted after sending
4. **Anonymization**: Optional anonymization for sharing/analysis
5. **No LLM Requests by Default**: LLM request logs not included unless explicitly enabled

## Performance Considerations

1. **Large Exports**: For users with many messages, export may take time
   - Progress messages keep user informed
   - Database queries are optimized with proper indexes

2. **File Size**: JSON files can be large
   - Telegram supports documents up to 50MB
   - Consider pagination for very large datasets in future

3. **Memory Usage**: All data loaded into memory before serialization
   - Consider streaming JSON for very large exports in future

## Future Enhancements

Potential improvements for future iterations:

1. **Selective Export**: Allow exporting specific data types
2. **Date Range Filtering**: Export only data from specific time periods
3. **Export Formats**: Support CSV, Excel, or other formats
4. **Scheduled Exports**: Automatic periodic exports
5. **Export History**: Track past exports
6. **Compression**: Compress large export files
7. **Streaming**: Stream large exports instead of loading all in memory
8. **Import**: Allow importing exported data back into system

## Error Handling

The export feature handles various error scenarios:

1. **Database Errors**: Caught and logged, user notified
2. **File Creation Errors**: Caught and logged, user notified
3. **File Sending Errors**: File still cleaned up
4. **Missing Data**: Empty arrays returned for missing data types
5. **Schema Changes**: Dynamic column checking for backward compatibility

## Changelog

### v1.0 Iteration 7 (2025-11-19)
- Initial implementation of export feature
- Support for anonymization
- Export preview command
- Comprehensive unit tests
- Documentation
