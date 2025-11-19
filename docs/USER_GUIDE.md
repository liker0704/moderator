# User Guide - Discord ↔ Telegram Moderator Console

## Introduction

This user guide provides complete instructions for using the Discord-Telegram Moderator Console. This system allows you to manage messages from Discord servers and Telegram DMs through a unified Telegram bot interface.

**Version**: v1.0 (Stable Release)
**Last Updated**: November 19, 2025

---

## Table of Contents

- [Getting Started](#getting-started)
- [Initial Setup](#initial-setup)
- [Working with Message Cards](#working-with-message-cards)
- [Bot Commands Reference](#bot-commands-reference)
- [Advanced Features](#advanced-features)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Tips and Best Practices](#tips-and-best-practices)

---

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- A Telegram account
- The Telegram bot link (provided by your administrator)
- Your Telegram User ID (get from [@userinfobot](https://t.me/userinfobot))
- Access to Discord (for obtaining your User Token)

### First Steps

1. **Open Telegram** and find your moderator bot
2. **Send `/start`** to initialize the bot
3. The bot will respond with a welcome message and instructions

---

## Initial Setup

### Step 1: Start the Bot

```
/start
```

**Expected Response**:
```
Welcome to the Discord-Telegram Moderator Console!

This bot helps you moderate messages from Discord and Telegram
in a unified interface. Let's get started with setup.

First, configure your Discord connection: /setup_discord
```

### Step 2: Configure Discord Connection

Command: **`/setup_discord`**

#### How to Get Your Discord User Token

⚠️ **IMPORTANT**: This is your personal Discord account token. Never share it with anyone!

1. Open **Discord Web** at https://discord.com/app in your browser
2. Log in to your Discord account
3. Open **Developer Tools** (Press `F12`)
4. Go to the **Console** tab
5. Paste this code and press Enter:

```javascript
(webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()
```

6. **Copy the token** (long string that appears)
7. **Send the token** to the bot in Telegram

The bot will:
- Encrypt and securely store the token in the database
- Attempt to connect to Discord Gateway
- Confirm successful connection or show an error

### Step 3: Verify Connection

Command: **`/test_connection`**

**Expected Response** (if successful):
```
✅ Connection to Discord active
Connected to 3 servers
Last message: 2 minutes ago
```

If you see an error, verify your token and try `/setup_discord` again.

### Step 4: Add Channels to Allowlist

To receive messages from specific Discord channels, you must add them to the allowlist.

#### Get Channel and Server IDs

1. In Discord, enable **Developer Mode**:
   - Settings → Advanced → Developer Mode (toggle ON)

2. Right-click on a server → **Copy Server ID**
3. Right-click on a channel → **Copy Channel ID**

#### Add Channels

Command: **`/allow_channel {server_id} {channel_id}`**

**Example**:
```
/allow_channel 111111111111111111 222222222222222222
```

**Expected Response**:
```
✅ Channel #general added to allowlist
Server: My Discord Server
```

Repeat this for all channels you want to moderate.

#### Alternative: Multi-Server Management (v1.0.3+)

For easier management with multiple channels:

1. **Browse servers**: `/servers`
2. **View channels**: `/channels {server_id}`
3. **Bulk add channels**: `/bulk_allow {server_id}`

This allows you to select multiple channels at once from a server.

### Step 5: Test the System

1. Send a message in one of your allowlisted Discord channels
2. You should receive a **message card** in Telegram within seconds
3. Try responding to verify the full workflow

---

## Working with Message Cards

### Understanding Message Cards

When a new message arrives from Discord or Telegram, the bot sends a **message card**:

```
📝 Discord • My Server • #general • @username • 12:34:56

Context:
[12:30] user1: Previous message
[12:32] user2: Another message
[12:34] username: Current message text here

🖼 Image: https://cdn.discord.com/attachments/...

[Reply] [Show More] [DND]
```

#### Card Elements

- **Header**: Platform, server, channel, author, timestamp
- **Context**: Last ~10 messages from this channel (for conversation context)
- **Attachments**: Images, files, or links (if any)
- **Buttons**: Action buttons for responding or managing

### Actions with Message Cards

#### 1. Reply to a Message

Click **[Reply]** button

**Workflow**:
1. Bot prompts: "Enter your response:"
2. Type your reply (plain text only, no Markdown)
3. Bot shows confirmation:
   ```
   Your response:
   "Your message text here"

   Send to #general?

   [Confirm] [Cancel]
   ```
4. Click **[Confirm]**
5. Message is posted to Discord/Telegram
6. Card updates to show success:
   ```
   ✅ Sent to #general at 12:35:20
   Your reply: "Your message text"

   [Edit] [Delete] [View History]
   ```

**Important**: Without confirmation, nothing is sent. You can always cancel before confirming.

#### 2. Show More Context

Click **[Show More]** button

The bot loads the next 10 messages from the conversation history and updates the card in-place. You can click multiple times to load more context—there's no limit.

**Progressive Loading**:
- First click: Load 10 more messages (total: 20)
- Second click: Load 10 more messages (total: 30)
- Continues indefinitely

#### 3. Enable Do Not Disturb (DND)

Click **[DND]** button or use `/dnd on`

When DND is active:
- New message cards stop arriving
- Messages are still saved in the database
- You can re-enable cards with `/dnd off`

See [Do Not Disturb Mode](#do-not-disturb-mode) for advanced scheduling.

#### 4. Edit Sent Replies (v1.0.2+)

After sending a reply, you'll see an **[Edit]** button if:
- The reply was sent within the last **48 hours**
- The message still exists in Discord/Telegram

**Editing Workflow**:
1. Click **[Edit]** button
2. Current reply text is shown
3. Type the new text
4. Click **[Confirm]** to update
5. Edit is sent to Discord/Telegram
6. Card updates with new text

All edits are tracked in the audit log with complete history.

### Handling Errors

If posting fails, the card shows an error:

```
❌ Error sending reply
Error: Missing Access

[Retry] [Cancel]
```

Click **[Retry]** after resolving the issue.

#### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| **Missing Access** | No permission in Discord channel | Verify bot permissions |
| **Invalid Token** | Discord token expired | Run `/setup_discord` again |
| **Channel Not Found** | Channel deleted or inaccessible | Remove from allowlist |
| **Rate Limited** | Too many requests | Wait a moment and retry |

---

## Bot Commands Reference

### Setup and Status Commands

#### `/start`
Initialize the bot and show welcome message.

#### `/help`
Show interactive help system with 5 categories:
- 🔧 Setup & Configuration
- ⚙️ Settings & Management
- 📝 Working with Message Cards
- 🔍 Troubleshooting
- 🤖 AI Features

Navigate with buttons and access specific help topics.

#### `/setup_discord`
Configure Discord User Token. See [Initial Setup](#step-2-configure-discord-connection).

#### `/test_connection`
Verify Discord Gateway connection is active.

**Example Response**:
```
✅ Connection to Discord active
Connected to 3 servers
Last message: 2 minutes ago
```

#### `/discord_status`
Detailed Discord connection status including session ID, heartbeat, and server count.

#### `/status`
Overall system status showing:
- Open tasks
- Tasks processed today
- DND status
- Discord connection status
- Database health

**Example**:
```
System Status:
━━━━━━━━━━━━━━━━━━━━━
Open tasks: 12
Tasks today: 47
DND: OFF
Discord: ✅ Connected
Database: ✅ OK
Redis: ✅ OK
━━━━━━━━━━━━━━━━━━━━━
```

### Do Not Disturb Mode

#### `/dnd on`
Manually enable DND mode. New cards stop arriving.

#### `/dnd off`
Manually disable DND mode. Cards resume.

#### `/dnd`
Open DND settings menu with options to:
- Enable/disable DND
- Configure schedule (automatic DND)
- Set time intervals and days

**Schedule Example**:
```
Configure DND Schedule:

Current: OFF

Presets:
[Weeknights] - Mon-Fri, 22:00-08:00
[Weekends] - Sat-Sun, all day
[Always] - 24/7
[Custom] - Set your own intervals
```

### Channel Management

#### `/allow_channel {server_id} {channel_id}`
Add a Discord channel to the allowlist.

**Example**:
```
/allow_channel 111111111111111111 222222222222222222
```

#### `/unallow_channel`
Remove a channel from allowlist with interactive selection dialog (v0.2.7+).

**Workflow**:
1. Send `/unallow_channel`
2. Bot shows all allowlisted channels
3. Click channel to remove
4. Confirm removal

**Legacy**: `/unallow_channel {channel_id}` still works for direct removal.

#### `/settings`
View and manage all settings:
- Discord connection status
- DND status
- Allowlist channels (actual data from database)
- Action buttons for quick access

**Example Display**:
```
⚙️ Settings
━━━━━━━━━━━━━━━━━━━━━

Discord Connection:
Status: ✅ Connected
Last connected: 2 minutes ago

DND Mode:
Status: OFF

Allowlist Channels: 5
• #general (My Server)
• #support (My Server)
• #bugs (Other Server)
• #alerts (Other Server)
• #moderation (Other Server)

[➕ Add Channel] [➖ Remove Channel]
[🔕 Toggle DND] [🔄 Refresh]
```

### Multi-Server Management (v1.0.3+)

#### `/servers`
Browse all Discord servers you're connected to.

**Response**: List of servers with buttons to view channels.

#### `/channels {server_id}`
View all channels in a specific server.

**Example**:
```
/channels 111111111111111111
```

Shows channels with indicators for which are already in your allowlist.

#### `/bulk_allow {server_id}`
Add multiple channels from a server at once.

**Workflow**:
1. Send `/bulk_allow {server_id}`
2. Bot shows all channels with checkboxes
3. Select channels to add
4. Confirm bulk addition
5. All selected channels added to allowlist

### Search Functionality (v1.0.4+)

#### `/search`
Search through message history with filters.

**Workflow**:
1. Send `/search`
2. Bot prompts for search parameters:
   - **Text**: Search within message content
   - **Author**: Filter by username
   - **Channel**: Filter by channel
   - **Date range**: Specify start and end dates
3. Results displayed with pagination (10 per page)

**Example Interaction**:
```
Search Message History
━━━━━━━━━━━━━━━━━━━━━

Enter search text (or skip): urgent

Author filter (or skip): @john

Channel filter (or skip): #support

Date range (YYYY-MM-DD to YYYY-MM-DD, or skip): 2025-11-01 to 2025-11-19

Searching...

Found 47 results

Showing 1-10 of 47

[Result 1] [Result 2] [Result 3] ...

[Prev] [1] [2] [3] [4] [5] [Next]
```

#### `/search_help`
Show search syntax, examples, and tips.

### Statistics & Analytics (v1.0.5+)

#### `/stats`
View comprehensive statistics and metrics.

**Metrics Included**:
- Total messages received
- Average response time
- Open tasks exceeding 24 hours
- Completed tasks count
- Most active channel
- LLM requests count (if enabled)
- LLM usage cost
- Response distribution by channel
- Top responders
- Task completion rate

**Period Switching**:
Use buttons to switch between time periods:
- [24h] - Last 24 hours
- [7d] - Last 7 days
- [30d] - Last 30 days
- [All-time] - Since beginning

**Example Display**:
```
📊 Statistics (Last 7 days)
━━━━━━━━━━━━━━━━━━━━━

Messages Received: 234
Avg Response Time: 8 min 23 sec
Open Tasks >24h: 3
Completed Tasks: 156

Most Active Channel:
#general - 87 messages

LLM Usage:
Requests: 45
Cost: $0.87

[24h] [7d] [30d] [All-time]
[Channel Breakdown] [Details]
```

### Quick Reply Templates (v1.0.6+)

#### `/templates list`
Show all saved reply templates.

#### `/templates add`
Create a new template with optional variables.

**Variables Supported**:
- `{user}` - Username
- `{channel}` - Channel name
- `{timestamp}` - Current timestamp
- `{server}` - Server name

**Example**:
```
/templates add

Name: greeting
Category: greeting
Text: Hello {user}! Thanks for reaching out in {channel}. How can I help?
```

#### `/templates delete`
Remove a template with interactive selection.

**Template Usage**:
When replying to a message, saved templates appear as quick-action buttons for one-click insertion.

### Data Export & Privacy (v1.0.7+)

#### `/export`
Export message history to JSON format.

**Options**:
- `--anonymize`: Remove sensitive data (usernames, IDs)
- `--date-range {start} {end}`: Export specific date range
- `--channels {ch1,ch2}`: Export specific channels only
- `--authors {user1,user2}`: Export specific users only

**Example**:
```
/export --anonymize --date-range 2025-11-01 2025-11-19
```

Generates a JSON file with all message history, optionally anonymized.

---

## Advanced Features

### AI-Powered Response Suggestions (v0.2+)

When LLM integration is enabled, message cards include AI-generated response variants.

**Card with AI Suggestions**:
```
📝 Discord • Server • #channel • @user • 12:34

Context:
[12:30] user1: Message 1
[12:34] user: Current message

🤖 AI Suggestions:

Variant 1 (Confidence: 85%): [Generated response 1]
Variant 2 (Confidence: 78%): [Generated response 2]

[Use Variant 1] [Use Variant 2]
[More Variants] [Soften...] [Reply Manually]
```

#### Actions

**Select a Variant**:
- Click **[Use Variant 1]** or **[Use Variant 2]**
- Bot shows confirmation dialog
- Click **[Confirm]** to send

**Generate More Variants**:
- Click **[More Variants]**
- AI generates 2 new responses
- Replace previous variants

**Soften Response**:
- Type your own reply first
- Click **[Soften...]**
- AI rephrases your text to be more polite/professional
- Review and confirm

**Reply Manually**:
- Click **[Reply Manually]**
- Proceed with standard reply workflow
- Ignores AI suggestions

#### Low Confidence Warning

If AI confidence is below 70%, you'll see:
```
⚠️ Model is not confident in this response
Confidence: 62%
```

**Recommendation**: Review carefully or write your own response.

### Reminder System (v0.2+)

The system automatically sends reminders for open tasks:

- **Frequency**: Every 30 minutes
- **Maximum**: 3 reminders per task
- **Condition**: Task is open and no response sent
- **Respects**: DND mode (no reminders during DND)

**Reminder Message Example**:
```
🔔 Reminder: Open Task

Channel: #general
From: @username
Age: 2 hours 15 minutes
Message: "Current message text..."

This is reminder #2 of 3.

[View Task] [Reply Now] [Snooze]
```

Enable/disable reminders in `/settings`.

### Error Handling System (v0.2.7+)

All errors use standardized error codes in format `ERR-XXX-NNN`:

**Example Error Message**:
```
❌ Error Code: ERR-DISCORD-001
Failed to Post Message to Discord

Reason: Missing Access
Details: No permission to send messages in #general

Recovery Steps:
1. Verify you have permissions in the Discord channel
2. Check if the channel still exists
3. Try sending a test message manually in Discord

Request ID: REQ-A3F29B7C
```

### Health Check & Monitoring (v1.0.1+)

System administrators can monitor health via HTTP endpoint:

**Endpoint**: `GET http://localhost:8000/health`

**Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-11-19T12:00:00.000000Z",
  "checks": {
    "discord": {
      "status": "healthy",
      "connected": true,
      "session_id": "abc123..."
    },
    "database": {
      "status": "healthy",
      "response_time_ms": 12.34
    },
    "redis": {
      "status": "healthy",
      "response_time_ms": 5.67
    },
    "llm": {
      "status": "configured",
      "provider": "openai",
      "model": "gpt-4-turbo"
    }
  },
  "version": "1.0.0"
}
```

### Prometheus Metrics (v1.0.8+)

For advanced monitoring with Prometheus/Grafana:

**Endpoint**: `GET http://localhost:8000/metrics`

**Metrics Available**:
- `moderator_tasks_total` - Total tasks by status
- `moderator_messages_received_total` - Messages by platform
- `moderator_replies_sent_total` - Replies sent
- `moderator_open_tasks` - Current open tasks (gauge)
- `moderator_response_time_seconds` - Response latency histogram
- `moderator_llm_response_time_seconds` - LLM latency histogram

---

## Common Workflows

### Workflow 1: Respond to a Discord Message

1. Receive message card in Telegram
2. Read context (click "Show More" if needed)
3. Click "Reply"
4. Type your response
5. Click "Confirm"
6. Message sent to Discord

**Total Time**: ~30 seconds

### Workflow 2: Enable DND for the Evening

**Option A - Manual**:
```
Before bed:
/dnd on

Next morning:
/dnd off
```

**Option B - Automatic Schedule**:
```
/dnd
→ Select "Weeknights"
→ Configured: Mon-Fri, 22:00-08:00
→ Auto-enable/disable daily
```

### Workflow 3: Edit a Sent Reply

1. Locate the sent card (shows ✅ Sent...)
2. Click **[Edit]** button (available for 48 hours)
3. Current text shown
4. Type new text
5. Click **[Confirm]**
6. Edit applied to Discord/Telegram
7. Card updates with new text

### Workflow 4: Add Multiple Channels from a Server

```
Step 1: Browse servers
/servers
→ View all connected servers

Step 2: View channels
Click on "My Server"
→ Shows all channels in that server

Step 3: Bulk add
/bulk_allow 111111111111111111
→ Select: #general, #support, #alerts
→ Confirm
→ All 3 channels added to allowlist

Step 4: Verify
/settings
→ See all new channels listed
```

### Workflow 5: Search for Past Messages

```
Step 1: Start search
/search

Step 2: Enter filters
→ Text: "urgent"
→ Author: @john
→ Channel: #support
→ Date: 2025-11-01 to 2025-11-19

Step 3: Browse results
→ Showing 1-10 of 47 results
→ Click [2] to go to page 2
→ Click on a result to see full message

Step 4: Take action
→ Can reply or edit directly from search results
```

### Workflow 6: Review Statistics

```
Step 1: View stats
/stats

Step 2: Choose period
→ Click [7d] for last 7 days
→ Shows activity metrics

Step 3: Drill down
→ Click [Channel Breakdown]
→ See per-channel statistics
→ Identify busiest channels

Step 4: Export data (if needed)
/export --date-range 2025-11-01 2025-11-19
```

---

## Troubleshooting

### Bot Not Responding to Commands

**Check**:
1. You're messaging the bot directly (not in a group)
2. You've sent `/start` to initialize
3. The bot service is running

**Solution**: Contact your administrator if the bot is offline.

### No Message Cards Arriving from Discord

**Checklist**:
- [ ] Discord connection active? → `/test_connection`
- [ ] Channel in allowlist? → `/settings`
- [ ] DND mode off? → `/dnd off`
- [ ] Messages sent in allowlisted channel?
- [ ] Backend service running?

**Debug**:
```
/test_connection
→ Verify Discord is connected

/settings
→ Check allowlist includes the channel

/dnd off
→ Ensure DND is disabled

/status
→ Check overall system health
```

### Reply Not Sending

**Common Causes**:

1. **Missing Access**: No permission in Discord channel
   - **Solution**: Verify bot/account permissions

2. **Invalid Token**: Discord token expired
   - **Solution**: Run `/setup_discord` with new token

3. **Channel Not Found**: Channel deleted
   - **Solution**: Remove from allowlist with `/unallow_channel`

4. **Rate Limited**: Too many requests
   - **Solution**: Wait a moment and click [Retry]

**Always**: Check the error message in the card for specific guidance.

### Edit Button Missing

**Requirements for Edit Button**:
- Reply sent within last **48 hours**
- Original message still exists
- Discord/Telegram API supports editing

If button is missing, the time window has expired. You cannot edit older replies.

### Search Returns No Results

**Tips**:
- Check spelling in search text
- Broaden date range
- Remove author/channel filters
- Try simpler search terms
- Verify messages exist in that period

### Statistics Show Zero

**Possible Reasons**:
- No activity in selected time period
- Database not tracking metrics (check logs)
- Try longer time period (switch to [30d] or [All-time])

---

## FAQ

### Q: Can I use Markdown or formatting in replies?

**A**: No, the system only supports plain text by design. This ensures compatibility with both Discord and Telegram.

### Q: How long are messages stored?

**A**: Messages are stored for **90 days** and then automatically deleted. This is a privacy/storage policy.

### Q: Can multiple moderators use the system?

**A**: No, this is a **single-user system**. Only one moderator can use it at a time.

### Q: What happens to messages during DND?

**A**: Messages are still **saved in the database** but cards are not sent. When you disable DND, past messages are NOT retroactively shown (by design).

### Q: Can I get Desktop notifications?

**A**: Yes, configure Telegram Desktop to show notifications for the bot's messages.

### Q: Is my Discord token safe?

**A**: Yes, it's encrypted with AES-256 (Fernet) and stored securely in the database. However, you should still use a dedicated Discord account if possible.

### Q: How much does LLM cost?

**A**: Depends on usage. The system tracks costs and shows them in `/stats`. Set budget alerts in your LLM provider dashboard.

### Q: Can I export my data?

**A**: Yes, use `/export` to generate a JSON file with all message history. You can also anonymize it for privacy.

### Q: What if I accidentally send a wrong message?

**A**: Use the **[Edit]** button (available for 48 hours) to correct sent replies. All edits are tracked in the audit log.

### Q: Why did I receive a reminder?

**A**: The system sends reminders for open tasks every 30 minutes (max 3 per task). Disable in `/settings` if you don't want reminders.

---

## Tips and Best Practices

### 1. Always Read Context

Before replying, click **[Show More]** to load additional context. Understanding the full conversation prevents miscommunication.

### 2. Review Before Confirming

The confirmation dialog is your safety net. Always review your reply text before clicking **[Confirm]**.

### 3. Use DND Schedules

Instead of manually toggling DND, set up automatic schedules that match your work hours. This prevents interruptions during off-hours.

### 4. Regularly Check `/status`

Monitor system health and task backlog with `/status`. This helps you stay on top of pending work.

### 5. Leverage AI Suggestions

AI variants can save time, but always review before sending. The confidence score indicates reliability.

### 6. Organize with Search

Use `/search` to quickly find past conversations, especially when users reference previous discussions.

### 7. Review Statistics

Check `/stats` weekly to identify:
- Busiest channels (consider adding more moderators)
- Response time trends (are you meeting SLAs?)
- LLM costs (budget management)

### 8. Use Templates for Common Replies

Create templates for frequently used responses:
- Greetings
- Closing statements
- Support ticket acknowledgments
- FAQ answers

This maintains consistency and saves typing time.

### 9. Keep Allowlist Clean

Periodically review `/settings` and remove inactive or irrelevant channels from your allowlist.

### 10. Backup Your Configuration

Export your data regularly with `/export` as a backup. Store exports securely.

---

## Security Best Practices

### Never Share

- Discord User Token
- Telegram Bot Token
- Bot link (if private)
- Exported data (contains message history)

### If Token is Compromised

1. **Change Discord password immediately**
2. **Logout all Discord sessions**: Settings → Logout All Devices
3. **Get new token** using the procedure in Step 2
4. **Run `/setup_discord`** with the new token
5. **Monitor activity** for unauthorized access

### Regular Security Checks

- Review allowlist channels monthly
- Check `/discord_status` for unusual activity
- Monitor system logs for errors or intrusions

---

## Conclusion

The Discord-Telegram Moderator Console provides a powerful, unified interface for managing messages across platforms. With features like AI-powered suggestions, comprehensive search, detailed statistics, and flexible workflows, it streamlines moderation tasks significantly.

For questions, issues, or feature requests, contact your system administrator or consult the technical documentation in the `docs/` directory.

**Happy Moderating!** 🎉
