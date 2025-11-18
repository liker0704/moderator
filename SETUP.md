# Complete Setup Guide - Discord/Telegram Moderator Console

This guide will walk you through the complete setup process for the TG-консоль модератора, from installing prerequisites to verifying your first message flow.

> **Important Notice**: This project uses Discord User Token authentication, which violates Discord's Terms of Service. Use at your own risk. Your Discord account may be suspended or banned.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Discord Setup](#2-discord-setup)
3. [Telegram Bot Setup](#3-telegram-bot-setup)
4. [Project Setup](#4-project-setup)
5. [Database Setup](#5-database-setup)
6. [First Run](#6-first-run)
7. [Initial Configuration](#7-initial-configuration)
8. [Verification](#8-verification)
9. [Troubleshooting](#9-troubleshooting)
10. [Advanced Configuration](#10-advanced-configuration)

---

## 1. Prerequisites

Before starting, ensure you have the following installed on your system.

### 1.1 Docker and Docker Compose

Docker is required to run the application and database in containers.

#### Ubuntu/Debian Installation

```bash
# Update package index
sudo apt update
sudo apt upgrade -y

# Install dependencies
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Add Docker's official GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Add Docker repository
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Add your user to docker group (to run without sudo)
sudo usermod -aG docker $USER
newgrp docker
```

**Verify Installation:**

```bash
docker --version
docker compose version
```

**Expected Output:**
```
Docker version 24.0.7, build afdd53b
Docker Compose version v2.23.0
```

> **Note**: If you see "permission denied" errors, log out and log back in, or run `newgrp docker` to reload group membership.

#### Alternative: macOS Installation

```bash
# Install Docker Desktop from https://www.docker.com/products/docker-desktop
# Or use Homebrew:
brew install --cask docker
```

### 1.2 Git

Git is required to clone the repository.

```bash
# Ubuntu/Debian
sudo apt install -y git

# macOS
brew install git

# Verify
git --version
```

**Expected Output:**
```
git version 2.34.1
```

### 1.3 Python 3.11+ (Optional, for Development)

Only needed if you plan to run the application outside of Docker or contribute to development.

```bash
# Ubuntu/Debian
sudo apt install -y python3.11 python3.11-venv python3-pip

# macOS
brew install python@3.11

# Verify
python3 --version
```

### 1.4 Text Editor

You'll need a text editor to modify the `.env` file:
- **nano** (simple, terminal-based) - already installed on most systems
- **vim** or **vi** (advanced, terminal-based)
- **VS Code** (GUI, recommended)
- **Sublime Text** (GUI)

---

## 2. Discord Setup

This is the most critical and sensitive part of the setup.

### 2.1 Understanding Discord User Token

A **User Token** is your personal authentication key for Discord. Unlike Bot Tokens:
- It represents **your personal account**
- It has **all your permissions** on all servers
- It **violates Discord ToS** if used for automation
- If leaked, someone can **impersonate you** on Discord

> **Security Warning**:
> - Never share your User Token with anyone
> - Never commit it to git or paste it in public channels
> - Never use it on untrusted services
> - Discord may ban your account if detected

### 2.2 Getting Your Discord User Token

There are two methods to obtain your token. Method 1 is easier and recommended.

#### Method 1: DevTools Console (Recommended)

**Step-by-step with screenshots:**

1. **Open Discord Web Application**
   - Navigate to: https://discord.com/app
   - Log in with your Discord account
   - Wait for Discord to fully load

2. **Open Browser DevTools**
   - Press `F12` (Windows/Linux) or `Cmd+Option+I` (macOS)
   - Or right-click anywhere → "Inspect" → "Console" tab

3. **Execute Token Extraction Code**
   - Click into the Console tab
   - Copy and paste this code:

   ```javascript
   (webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()
   ```

   - Press `Enter`

4. **Copy the Token**
   - You'll see a string like: `"XXXXXXXXXXXXXXXXXX.XXXXXX.XXXXXXXXXXXXXXXXXXXXXXXXXXX"`
   - **Copy this entire string** (including quotes if shown)
   - The token format: `{user_id_base64}.{timestamp_base64}.{hmac_signature}`

**Example Token Format** (do NOT use this example):
```
YOUR_DISCORD_USER_TOKEN_HERE
```

> **Screenshot Reference**: See `docs/screenshots/discord_token_extraction.png` (if available)

#### Method 2: Network Inspector (Alternative)

1. Open Discord Web (https://discord.com/app)
2. Open DevTools (`F12`) → **Network** tab
3. Filter: `Fetch/XHR`
4. Send any message in Discord
5. Find a request to `https://discord.com/api/v9/...`
6. Click on it → **Headers** tab
7. Look for `Authorization` header
8. Copy the value (the token)

### 2.3 Getting Super Properties (Optional but Recommended)

Super Properties help your connection appear more legitimate to Discord.

1. In the same DevTools Console, paste:

```javascript
JSON.parse(atob(
  (webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m)
  .find(m=>m?.exports?.default?.getSuperPropertiesBase64!==void 0)
  .exports.default.getSuperPropertiesBase64()
))
```

2. Press `Enter`

3. You'll see output like:

```json
{
  "os": "Windows",
  "browser": "Chrome",
  "device": "",
  "system_locale": "en-US",
  "browser_version": "120.0.0.0",
  "os_version": "10",
  "client_build_number": 261053
}
```

4. **Save the `client_build_number`** - you may need it later

> **Note**: This is optional for MVP v0.1, but may be required in future versions for better stability.

### 2.4 Security and ToS Implications

> **Warning - Terms of Service**:
> - Using a User Token for automation violates [Discord Terms of Service](https://discord.com/terms)
> - Discord actively detects and bans self-bots
> - Your account may be suspended without warning
> - Use a secondary/burner account if possible

**Risk Mitigation:**
- Don't spam messages
- Add delays between actions
- Use realistic user agent strings
- Don't run 24/7 if possible
- Monitor Discord for protocol changes

### 2.5 Testing the Token (Before Using It)

You can verify your token works using curl:

```bash
curl -H "Authorization: YOUR_TOKEN_HERE" https://discord.com/api/v9/users/@me
```

**Expected Output (Success):**
```json
{
  "id": "123456789012345678",
  "username": "your_username",
  "discriminator": "1234",
  "avatar": "hash",
  "verified": true,
  "email": "your@email.com",
  ...
}
```

**If you see an error:**
```json
{"message": "401: Unauthorized", "code": 0}
```
→ Your token is invalid or expired. Obtain a new one.

---

## 3. Telegram Bot Setup

The Telegram bot is your command center for receiving and responding to messages.

### 3.1 Creating a Bot with BotFather

**BotFather** is Telegram's official bot for creating and managing bots.

1. **Open Telegram** (desktop, web, or mobile)

2. **Search for BotFather**
   - In the search bar, type: `@BotFather`
   - Click on the official bot (verified with blue checkmark)

3. **Start BotFather**
   - Click `/start`
   - BotFather will show you a menu of commands

4. **Create a New Bot**
   - Send: `/newbot`
   - BotFather asks: "Alright, a new bot. How are we going to call it?"

5. **Choose a Display Name**
   - Enter a name for your bot (can contain spaces)
   - Example: `My Moderator Console`

6. **Choose a Username**
   - BotFather asks: "Now choose a username for your bot."
   - Must end with `bot`
   - Must be unique
   - Examples: `my_moderator_bot`, `moderator_console_bot`

7. **Get Your Bot Token**
   - BotFather responds with:
   ```
   Done! Congratulations on your new bot. You will find it at t.me/your_bot_name.
   You can now add a description...

   Use this token to access the HTTP API:
   123456789:ABCdefGHIjklMNOpqrsTUVwxyz

   Keep your token secure and store it safely...
   ```

8. **Copy and Save the Token**
   - Format: `{bot_id}:{secret}`
   - Example: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

> **Screenshot Reference**: See `docs/screenshots/telegram_botfather.png` (if available)

### 3.2 Getting Your Telegram User ID

Your User ID is needed so the bot knows who the moderator is.

1. **Open @userinfobot**
   - Search for `@userinfobot` in Telegram
   - Or use direct link: https://t.me/userinfobot

2. **Start the bot**
   - Click `/start`

3. **Get Your ID**
   - The bot immediately responds with:
   ```
   Id: 987654321
   First: Your
   Last: Name
   Username: @your_username
   Language: en
   ```

4. **Copy the ID**
   - In this example: `987654321`
   - This is a numeric value (no quotes needed in .env)

**Alternative Method - Using Your Own Bot:**

If your bot is already created, you can get your ID by:
1. Send any message to your bot
2. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Look for `"from":{"id":987654321,...}`

### 3.3 Configuring Bot Commands (Optional)

You can set up a command menu for convenience.

1. **In BotFather**, send: `/setcommands`
2. **Select your bot** from the list
3. **Paste this command list:**

```
start - Start the bot
help - Show all commands
setup_discord - Configure Discord connection
test_connection - Test Discord connection
status - Show system status
dnd - Toggle Do Not Disturb mode
allow_channel - Add channel to allowlist
settings - View and change settings
```

4. **Send the list**, BotFather confirms: "Success! Command list updated."

Now users see these commands in the Telegram menu when typing `/`.

### 3.4 Security Considerations

> **Bot Token Security**:
> - Never commit the bot token to git
> - Don't share it publicly
> - If leaked, revoke it via BotFather (`/revoke`) and create a new bot

---

## 4. Project Setup

Now we'll clone the repository and configure the application.

### 4.1 Cloning the Repository

```bash
# Navigate to where you want to install (e.g., home directory)
cd ~

# Clone the repository (replace with actual repo URL)
git clone https://github.com/your-username/moderator.git

# Enter the project directory
cd moderator
```

**Expected Output:**
```
Cloning into 'moderator'...
remote: Enumerating objects: 150, done.
remote: Counting objects: 100% (150/150), done.
remote: Compressing objects: 100% (95/95), done.
Receiving objects: 100% (150/150), 250.00 KiB | 2.50 MiB/s, done.
Resolving deltas: 100% (60/60), done.
```

### 4.2 Creating the .env File

The `.env` file stores all your configuration and secrets.

```bash
# Copy the example file
cp .env.example .env

# Open it for editing
nano .env
```

> **Tip**: If `nano` is unfamiliar:
> - Use arrow keys to navigate
> - Edit directly (no "insert mode" needed)
> - `Ctrl+O` to save (confirm with Enter)
> - `Ctrl+X` to exit

### 4.3 Generating Encryption Key

The encryption key is used to securely store your Discord token in the database.

**Method 1: Using Python (Recommended)**

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**Expected Output (example - yours will be different):**
```
dGhpc19pc19hX3NhbXBsZV9rZXlfZG9fbm90X3VzZQ==
```

**Method 2: Using OpenSSL**

```bash
openssl rand -base64 32
```

**Expected Output (example):**
```
aB3dE5fG7hI9jK0lM2nO4pQ6rS8tU1vW3xY5zA7bC9d=
```

> **Important**: Both methods produce valid keys. Copy the output - you'll paste it into `.env`.

### 4.4 Configuring All Environment Variables

Open the `.env` file and fill in all values. Here's the complete configuration:

```bash
# ============================================
# Database Configuration
# ============================================

DB_NAME=moderator_db
DB_USER=moderator
# IMPORTANT: Change this! Generate with: openssl rand -base64 32
DB_PASSWORD=CHANGE_THIS_TO_A_SECURE_PASSWORD
DB_HOST=db
DB_PORT=5432


# ============================================
# Telegram Bot Configuration
# ============================================

# From BotFather (Step 3.1)
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz

# From @userinfobot (Step 3.2)
MODERATOR_TG_USER_ID=987654321


# ============================================
# Encryption Configuration
# ============================================

# Generated in Step 4.3
ENCRYPTION_KEY=dGhpc19pc19hX3NhbXBsZV9rZXlfZG9ubm90X3VzZQ==


# ============================================
# LLM Configuration (v0.2+ - Optional for MVP)
# ============================================

# Options: 'openai' or 'anthropic'
LLM_PROVIDER=openai

# Get from: https://platform.openai.com/api-keys
# Leave empty if not using LLM features yet
OPENAI_API_KEY=

# Anthropic alternative (leave commented if using OpenAI)
# ANTHROPIC_API_KEY=sk-ant-your_key_here

# Model options:
# OpenAI: gpt-4-turbo, gpt-4, gpt-3.5-turbo
# Anthropic: claude-3-opus-20240229, claude-3-sonnet-20240229
LLM_MODEL=gpt-4-turbo


# ============================================
# Alert Configuration
# ============================================

# Same as MODERATOR_TG_USER_ID or separate chat for alerts
ALERT_CHAT_ID=987654321


# ============================================
# Logging Configuration
# ============================================

# Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
# Use INFO for production, DEBUG for troubleshooting
LOG_LEVEL=INFO
```

**Save the file** (`Ctrl+O`, `Enter`, `Ctrl+X` in nano)

### 4.5 Understanding Each Variable

| Variable | Purpose | Example | Required |
|----------|---------|---------|----------|
| `DB_NAME` | PostgreSQL database name | `moderator_db` | Yes |
| `DB_USER` | PostgreSQL username | `moderator` | Yes |
| `DB_PASSWORD` | PostgreSQL password | Generate with `openssl rand -base64 32` | Yes |
| `DB_HOST` | Database host | `db` (for Docker), `localhost` (local dev) | Yes |
| `DB_PORT` | Database port | `5432` | Yes |
| `TELEGRAM_BOT_TOKEN` | Bot token from BotFather | `123456789:ABC...` | Yes |
| `MODERATOR_TG_USER_ID` | Your Telegram user ID | `987654321` | Yes |
| `ENCRYPTION_KEY` | Fernet key for encrypting Discord token | Generate with Python/OpenSSL | Yes |
| `LLM_PROVIDER` | AI provider (v0.2+) | `openai` or `anthropic` | No (v0.2+) |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` | No (v0.2+) |
| `ANTHROPIC_API_KEY` | Anthropic API key | `sk-ant-...` | No (v0.2+) |
| `LLM_MODEL` | Which AI model to use | `gpt-4-turbo` | No (v0.2+) |
| `ALERT_CHAT_ID` | Telegram chat for system alerts | `987654321` | Yes |
| `LOG_LEVEL` | Logging verbosity | `INFO` or `DEBUG` | Yes |

> **Note**: LLM variables are only needed for v0.2+. For MVP v0.1, you can leave them empty or commented out.

### 4.6 Protecting the .env File

```bash
# Restrict file permissions (only you can read/write)
chmod 600 .env

# Verify
ls -la .env
```

**Expected Output:**
```
-rw------- 1 youruser youruser 1234 Nov 16 12:00 .env
```

> **Security Tip**: Never commit `.env` to git. The `.gitignore` file should already exclude it.

---

## 5. Database Setup

The database is handled automatically by Docker Compose, but here's what happens behind the scenes.

### 5.1 Automatic Migration

When you start the application for the first time:

1. **Docker Compose creates a PostgreSQL container**
2. **Migration files in `migrations/` are executed automatically**
   - `migrations/001_initial_schema.sql` creates all tables
   - Additional migrations (if any) run in order
3. **Database is ready to use**

> **How it works**: Docker Compose mounts `./migrations:/docker-entrypoint-initdb.d`, and PostgreSQL runs all `.sql` files on first startup.

### 5.2 Manual Migration (If Needed)

If you need to run migrations manually (e.g., after updates):

```bash
# Make sure database container is running
docker compose up -d db

# Wait for it to be healthy
docker compose ps

# Run migration file
docker exec -i moderator_db psql -U moderator -d moderator_db < migrations/001_initial_schema.sql
```

**Expected Output:**
```
CREATE TABLE
CREATE TABLE
CREATE INDEX
...
```

### 5.3 Checking Database Health

```bash
# Check if database container is running
docker compose ps db
```

**Expected Output:**
```
NAME              IMAGE                  STATUS                   PORTS
moderator_db      postgres:15-alpine     Up 2 minutes (healthy)   127.0.0.1:5432->5432/tcp
```

**Connect to database (optional):**

```bash
docker exec -it moderator_db psql -U moderator -d moderator_db
```

**Inside psql:**
```sql
-- List all tables
\dt

-- Check a table structure
\d users

-- Exit
\q
```

**Expected Tables:**
- `users`
- `platform_accounts`
- `servers`
- `channels`
- `messages`
- `tasks`
- `replies`
- `audit_log`
- `dnd_settings`

---

## 6. First Run

Time to start the application!

### 6.1 Building Docker Images

```bash
# Build all services
docker compose build
```

**Expected Output:**
```
[+] Building 45.2s (12/12) FINISHED
 => [internal] load build definition from Dockerfile
 => => transferring dockerfile: 250B
 => [internal] load .dockerignore
 => [1/6] FROM docker.io/library/python:3.11-slim
 => [2/6] WORKDIR /app
 => [3/6] COPY backend/requirements.txt .
 => [4/6] RUN pip install --no-cache-dir -r requirements.txt
 => [5/6] COPY backend/src /app/src
 => exporting to image
 => => writing image sha256:abc123...
 => => naming to docker.io/library/moderator_backend
```

> **Note**: First build takes 2-5 minutes depending on your internet speed (downloading Python packages).

### 6.2 Starting Services

```bash
# Start all services in background (-d = detached mode)
docker compose up -d
```

**Expected Output:**
```
[+] Running 3/3
 ✔ Network moderator_default      Created
 ✔ Container moderator_db          Started
 ✔ Container moderator_backend     Started
```

### 6.3 Checking Logs

**View all logs:**
```bash
docker compose logs -f
```

**View backend logs only:**
```bash
docker compose logs -f backend
```

**Expected Output (backend):**
```
moderator_backend  | INFO: Starting Moderator Console v0.1
moderator_backend  | INFO: Database connected successfully
moderator_backend  | INFO: Telegram bot initialized: @your_bot_name
moderator_backend  | INFO: Discord gateway connector initialized
moderator_backend  | INFO: Waiting for Discord token configuration...
moderator_backend  | INFO: Telegram polling started
```

> **Tip**: Press `Ctrl+C` to stop viewing logs (services keep running)

### 6.4 Verifying Startup

```bash
# Check status of all containers
docker compose ps
```

**Expected Output:**
```
NAME                 IMAGE                   STATUS                   PORTS
moderator_backend    moderator-backend       Up 1 minute              127.0.0.1:8000->8000/tcp
moderator_db         postgres:15-alpine      Up 1 minute (healthy)    127.0.0.1:5432->5432/tcp
```

**Both should show "Up" status.**

### 6.5 Common Startup Issues

| Issue | Solution |
|-------|----------|
| `Error: .env file not found` | Make sure you created `.env` in project root |
| `Database connection failed` | Check `DB_PASSWORD` in `.env` |
| `Telegram bot token invalid` | Verify `TELEGRAM_BOT_TOKEN` from BotFather |
| `Port 5432 already in use` | Another PostgreSQL is running. Stop it or change port |
| `Permission denied` | Run `chmod 600 .env` and check Docker group membership |

---

## 7. Initial Configuration

Now configure the bot through Telegram.

### 7.1 Connecting to Your Telegram Bot

1. **Open Telegram** (any client)

2. **Search for your bot**
   - Search: `@your_bot_username`
   - Or use the link BotFather gave you: `t.me/your_bot_name`

3. **Start the bot**
   - Click **START** button
   - Or send: `/start`

**Expected Response:**
```
Welcome to Moderator Console! 👋

This bot helps you manage Discord and Telegram messages from a single interface.

To get started:
1. Configure Discord connection: /setup_discord
2. Test connection: /test_connection
3. Add channels to allowlist: /allow_channel

Type /help for all commands.
```

> **Note**: If bot doesn't respond, check `docker compose logs -f backend` for errors.

### 7.2 Setting Up Discord Connection

**Command:** `/setup_discord`

1. **Send the command:**
   ```
   /setup_discord
   ```

2. **Bot responds:**
   ```
   To connect to Discord, I need your User Token.

   ⚠️ WARNING: This violates Discord ToS. Use at your own risk.

   How to get your token:
   1. Open Discord Web (discord.com/app)
   2. Press F12 → Console
   3. Paste this code and press Enter:

   (webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()

   4. Copy the token and send it here.

   Send your Discord User Token:
   ```

3. **Send your Discord token**
   - Paste the token you got in Section 2.2
   - Example: `YOUR_DISCORD_USER_TOKEN_HERE`

4. **Bot validates and saves:**
   ```
   ✅ Discord token saved and encrypted
   🔄 Connecting to Discord Gateway...
   ✅ Connected successfully!

   Logged in as: YourUsername#1234
   Servers: 5

   Next step: Add channels to allowlist with /allow_channel
   ```

**If connection fails:**
```
❌ Failed to connect to Discord
Error: Invalid authentication token

Please check your token and try again with /setup_discord
```

### 7.3 Testing Connection

**Command:** `/test_connection`

```
/test_connection
```

**Expected Response (Success):**
```
✅ Discord Connection Status

Status: Connected
Session ID: abc123def456...
Username: YourUsername#1234
Servers: 5
Last heartbeat: 15 seconds ago

Everything is working correctly!
```

**If disconnected:**
```
❌ Discord Connection Status

Status: Disconnected
Last error: WebSocket closed unexpectedly

Action: Reconnecting automatically...
```

### 7.4 Adding Channels to Allowlist

Only messages from allowlisted channels will create task cards.

#### Getting Discord IDs

1. **Enable Developer Mode in Discord**
   - Discord → Settings → Advanced → Developer Mode: **ON**

2. **Get Server (Guild) ID**
   - Right-click on server icon → **Copy Server ID**
   - Example: `111111111111111111`

3. **Get Channel ID**
   - Right-click on channel name → **Copy Channel ID**
   - Example: `222222222222222222`

> **Screenshot Reference**: See `docs/screenshots/discord_copy_ids.png` (if available)

#### Add Channel Command

**Command:** `/allow_channel <server_id> <channel_id>`

**Example:**
```
/allow_channel 111111111111111111 222222222222222222
```

**Expected Response:**
```
✅ Channel added to allowlist

Server: My Discord Server
Channel: #general
Type: Text Channel

You will now receive messages from this channel.
```

**Repeat for each channel you want to monitor.**

**List all allowlisted channels:**
```
/settings
```

---

## 8. Verification

Test the complete flow to ensure everything works.

### 8.1 Testing Discord Ingestion

1. **Send a test message in Discord**
   - Go to Discord (web or app)
   - Open a channel you added to allowlist
   - Send a message: `Test message for moderator bot`

2. **Check Telegram**
   - Within 1-5 seconds, you should receive a task card:

   ```
   📬 New Message

   Discord • My Server • #general • @testuser • 14:30:45

   Context:
   [14:28] user1: Previous message
   [14:30] testuser: Test message for moderator bot

   [Reply] [Show More Context] [DND]
   ```

**If you don't receive a card:**
- Check `docker compose logs -f backend` for errors
- Verify channel is in allowlist: `/settings`
- Verify Discord connection: `/test_connection`
- Check DND is OFF: `/dnd off`

### 8.2 Testing Telegram Commands

**Test the help command:**
```
/help
```

**Expected Response:**
```
Available Commands:

🔧 Setup & Status:
/setup_discord - Configure Discord connection
/test_connection - Test Discord connection
/status - System status

🔕 Do Not Disturb:
/dnd on - Enable DND mode
/dnd off - Disable DND mode
/dnd - Configure DND schedule

📋 Channel Management:
/allow_channel - Add channel to allowlist
/unallow_channel - Remove channel from allowlist

⚙️ Other:
/settings - View settings
/help - This help message
```

**Test status command:**
```
/status
```

**Expected Response:**
```
📊 System Status

Open tasks: 1
Tasks today: 3
DND mode: OFF

Discord: ✅ Connected
Database: ✅ Healthy
Uptime: 15 minutes
```

### 8.3 Testing Reply Flow

1. **Receive a task card** (send a Discord message if needed)

2. **Click the [Reply] button**

3. **Bot prompts:**
   ```
   Enter your reply:
   ```

4. **Type a response:**
   ```
   This is my test reply
   ```

5. **Bot shows confirmation:**
   ```
   📝 Reply Preview

   Your reply:
   "This is my test reply"

   Will be sent to:
   Discord • My Server • #general

   [✅ Confirm] [❌ Cancel]
   ```

6. **Click [✅ Confirm]**

7. **Bot confirms:**
   ```
   ✅ Reply sent successfully

   Sent to: #general at 14:35:20
   Message ID: 333333333333333333
   ```

8. **Verify in Discord**
   - Check the Discord channel
   - Your reply should appear as a message from your account

### 8.4 Testing DND Mode

**Enable DND:**
```
/dnd on
```

**Expected Response:**
```
🔕 Do Not Disturb enabled

You will not receive new task cards.
Messages will still be saved in the database.

To disable: /dnd off
```

**Test by sending a Discord message:**
- Send a message in an allowlisted channel
- You should **not** receive a task card in Telegram
- The message is still saved (verified by `/status` showing increased count)

**Disable DND:**
```
/dnd off
```

**Expected Response:**
```
🔔 Do Not Disturb disabled

You will now receive task cards again.
```

---

## 9. Troubleshooting

Common issues and their solutions.

### 9.1 Bot Not Responding

**Symptoms:**
- Bot doesn't reply to `/start` or any command

**Solutions:**

1. **Check if backend is running:**
   ```bash
   docker compose ps backend
   ```
   Should show "Up" status.

2. **Check logs for errors:**
   ```bash
   docker compose logs backend | tail -50
   ```

3. **Verify bot token:**
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getMe"
   ```
   Should return bot info, not an error.

4. **Check if webhook is set (should be deleted):**
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getWebhookInfo"
   ```
   If webhook is set, delete it:
   ```bash
   curl "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/deleteWebhook"
   ```

5. **Restart backend:**
   ```bash
   docker compose restart backend
   docker compose logs -f backend
   ```

### 9.2 Discord Not Connecting

**Symptoms:**
- `/test_connection` shows "Disconnected"
- No messages received from Discord

**Solutions:**

1. **Check if token is valid:**
   ```bash
   curl -H "Authorization: YOUR_DISCORD_TOKEN" https://discord.com/api/v9/users/@me
   ```
   Should return your user info.

2. **Token expired/invalid:**
   - Get a new token (Section 2.2)
   - Send `/setup_discord` again

3. **Check backend logs:**
   ```bash
   docker compose logs backend | grep -i discord
   ```
   Look for connection errors.

4. **Verify encryption key:**
   - Ensure `ENCRYPTION_KEY` in `.env` is valid
   - If changed, you need to re-setup Discord: `/setup_discord`

5. **Restart backend:**
   ```bash
   docker compose restart backend
   ```

### 9.3 Database Connection Issues

**Symptoms:**
- Backend crashes on startup
- Logs show "Database connection failed"

**Solutions:**

1. **Check if database is running:**
   ```bash
   docker compose ps db
   ```
   Should show "Up (healthy)".

2. **Check database logs:**
   ```bash
   docker compose logs db
   ```

3. **Verify credentials:**
   - Open `.env`
   - Check `DB_PASSWORD` matches in all variables
   - No special characters needing escaping

4. **Test database connection:**
   ```bash
   docker exec -it moderator_db psql -U moderator -d moderator_db -c "SELECT 1"
   ```
   Should output: `1`

5. **Recreate database (WARNING: deletes data):**
   ```bash
   docker compose down -v
   docker compose up -d
   ```

### 9.4 No Task Cards Received

**Symptoms:**
- Discord messages sent, but no cards in Telegram

**Solutions:**

1. **Check DND is off:**
   ```
   /dnd off
   ```

2. **Verify channel is allowlisted:**
   ```
   /settings
   ```
   If not listed, add it:
   ```
   /allow_channel <guild_id> <channel_id>
   ```

3. **Check Discord connection:**
   ```
   /test_connection
   ```

4. **Check backend logs:**
   ```bash
   docker compose logs backend | grep MESSAGE_CREATE
   ```
   Should show incoming messages.

5. **Verify you're sending in the correct channel:**
   - Copy IDs again from Discord
   - Ensure Developer Mode is enabled

### 9.5 Reply Not Sending

**Symptoms:**
- Reply confirmation clicked, but message doesn't appear in Discord

**Solutions:**

1. **Check error message in task card:**
   - Common errors:
     - `Missing Access` - No permission to write in channel
     - `Invalid Token` - Discord token expired
     - `Unknown Channel` - Channel deleted or ID wrong
     - `Rate Limited` - Too many messages, wait 30 seconds

2. **Verify permissions:**
   - Make sure your Discord account can write in that channel

3. **Check backend logs:**
   ```bash
   docker compose logs backend | grep -i error
   ```

4. **Test with a simple message:**
   - Try replying with just "test"
   - Special characters sometimes cause issues

### 9.6 Port Conflicts

**Symptoms:**
- `Error: bind: address already in use`

**Solutions:**

1. **Check what's using the port:**
   ```bash
   sudo lsof -i :5432
   sudo lsof -i :8000
   ```

2. **Stop conflicting service:**
   ```bash
   # If PostgreSQL is running locally
   sudo systemctl stop postgresql
   ```

3. **Or change port in docker-compose.yml:**
   ```yaml
   ports:
     - "127.0.0.1:5433:5432"  # Changed from 5432
   ```

### 9.7 Debug Mode

For detailed troubleshooting, enable debug logging:

1. **Edit `.env`:**
   ```bash
   LOG_LEVEL=DEBUG
   ```

2. **Restart backend:**
   ```bash
   docker compose restart backend
   ```

3. **View detailed logs:**
   ```bash
   docker compose logs -f backend
   ```

4. **Remember to change back to INFO in production**

---

## 10. Advanced Configuration

### 10.1 DND Schedule Configuration

Set up automatic Do Not Disturb based on time and day.

**Command:** `/dnd`

1. **Send the command:**
   ```
   /dnd
   ```

2. **Bot shows menu:**
   ```
   🔕 Do Not Disturb Settings

   Current status: OFF

   Schedule:
   Weekdays (Mon-Fri): Not set
   Weekends (Sat-Sun): Not set

   [Set Weekday Schedule] [Set Weekend Schedule]
   [Enable Schedule] [Disable Schedule]
   ```

3. **Click [Set Weekday Schedule]**

4. **Enter time range:**
   ```
   Enter schedule in format: HH:MM-HH:MM
   Example: 22:00-08:00
   ```

5. **Bot confirms:**
   ```
   ✅ Weekday DND schedule set

   Active: Monday-Friday, 22:00-08:00

   DND will automatically enable during these hours.
   ```

**Example schedules:**
- Work hours off: `18:00-09:00`
- Sleep time: `23:00-07:00`
- Weekend full day: `00:00-23:59`

### 10.2 Multiple Servers Setup (Future - v1.0)

Currently, the system works with multiple servers automatically. Just add channels from any server:

```
# Server 1, Channel A
/allow_channel 111111111111111111 222222222222222222

# Server 1, Channel B
/allow_channel 111111111111111111 333333333333333333

# Server 2, Channel A
/allow_channel 444444444444444444 555555555555555555
```

All messages from all allowlisted channels will arrive in Telegram.

### 10.3 Environment Variables Reference Table

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `DB_NAME` | String | `moderator_db` | PostgreSQL database name |
| `DB_USER` | String | `moderator` | PostgreSQL username |
| `DB_PASSWORD` | String | *required* | PostgreSQL password |
| `DB_HOST` | String | `db` | Database host (use `db` for Docker, `localhost` for local dev) |
| `DB_PORT` | Integer | `5432` | PostgreSQL port |
| `TELEGRAM_BOT_TOKEN` | String | *required* | Token from @BotFather |
| `MODERATOR_TG_USER_ID` | Integer | *required* | Your Telegram user ID |
| `ENCRYPTION_KEY` | String | *required* | Fernet key for Discord token encryption |
| `LLM_PROVIDER` | String | `openai` | AI provider: `openai` or `anthropic` (v0.2+) |
| `OPENAI_API_KEY` | String | - | OpenAI API key (v0.2+) |
| `ANTHROPIC_API_KEY` | String | - | Anthropic API key (v0.2+) |
| `LLM_MODEL` | String | `gpt-4-turbo` | AI model to use (v0.2+) |
| `ALERT_CHAT_ID` | Integer | *required* | Telegram chat ID for system alerts |
| `LOG_LEVEL` | String | `INFO` | Logging level: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

### 10.4 Updating the Application

When new versions are released:

```bash
# Stop services
docker compose stop

# Backup database (optional)
docker exec moderator_db pg_dump -U moderator moderator_db > backup_$(date +%Y%m%d).sql

# Update code
git pull

# Check for new migration files
ls migrations/

# Rebuild images
docker compose build

# Start services
docker compose up -d

# Check logs for errors
docker compose logs -f backend
```

### 10.5 Production Checklist

Before running in production:

- [ ] `.env` file permissions set to `600`
- [ ] `DB_PASSWORD` is strong and random
- [ ] `ENCRYPTION_KEY` is unique (never reuse from examples)
- [ ] `LOG_LEVEL` set to `INFO` (not `DEBUG`)
- [ ] Discord token is from a secondary account (not your main)
- [ ] Telegram bot token is kept secret
- [ ] Firewall rules configured (if on a server)
- [ ] Automatic startup configured (e.g., systemd service)
- [ ] Cron job for database cleanup (90 days):
  ```bash
  0 3 * * * cd /path/to/moderator && docker exec moderator_db psql -U moderator -d moderator_db -c "DELETE FROM messages WHERE created_at < NOW() - INTERVAL '90 days'"
  ```

---

## Conclusion

You've successfully set up the Discord/Telegram Moderator Console!

**Quick Reference:**

- **Start services:** `docker compose up -d`
- **Stop services:** `docker compose stop`
- **View logs:** `docker compose logs -f backend`
- **Restart:** `docker compose restart backend`
- **Update:** `git pull && docker compose build && docker compose up -d`

**Key Telegram Commands:**

- `/setup_discord` - Configure Discord
- `/test_connection` - Test Discord
- `/allow_channel <guild_id> <channel_id>` - Add channel
- `/dnd on|off` - Toggle DND
- `/status` - System status
- `/help` - All commands

**Need Help?**

- Check logs: `docker compose logs -f backend`
- Review [User Guide](docs/USER_GUIDE.md)
- Check [Troubleshooting](#9-troubleshooting) section above
- Review [Architecture](docs/ARCHITECTURE.md) for system design

**Security Reminders:**

- Never share your Discord User Token
- Never commit `.env` to git
- Use at your own risk (violates Discord ToS)
- Monitor for unusual activity

**Happy moderating! 🎉**
