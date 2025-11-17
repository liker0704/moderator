# Node.js Discord Service Specification

**Version:** 1.0
**Last Updated:** 2025-11-17
**Part of:** Moderator Project - Hybrid Architecture

---

## Overview

This document provides a complete specification for the Node.js Discord Service microservice, which acts as a bridge between Discord and the Python main service.

### Purpose

- Connect to Discord Gateway using User Token
- Receive real-time Discord events (messages, updates)
- Forward events to Python service via HTTP webhook
- Provide REST API for Python to interact with Discord
- Handle allowlist filtering and rate limiting

### Technology Stack

- **Runtime:** Node.js 18+ (LTS)
- **Framework:** Express.js 4.x
- **Discord Client:** discord-user-bots (npm package)
- **HTTP Client:** axios
- **Environment:** dotenv
- **Testing:** Jest
- **TypeScript:** Optional but recommended

---

## Project Structure

```
discord-service/
├── src/
│   ├── index.js              # Entry point
│   ├── gateway.js            # Discord Gateway client
│   ├── api.js                # REST API server (Express)
│   ├── webhook.js            # Webhook caller to Python
│   ├── allowlist.js          # Allowlist management
│   ├── normalizer.js         # Message normalization
│   ├── config.js             # Configuration loader
│   └── utils/
│       ├── logger.js         # Logging utility
│       └── auth.js           # Auth middleware
├── tests/
│   ├── gateway.test.js
│   ├── api.test.js
│   └── webhook.test.js
├── package.json
├── Dockerfile
├── .dockerignore
├── .env.example
├── .gitignore
├── README.md
└── jest.config.js
```

---

## Configuration

### Environment Variables

Create `.env` file (never commit this):

```env
# Discord
DISCORD_USER_TOKEN=your_discord_user_token_here

# Python Service
PYTHON_SERVICE_URL=http://backend:8000
PYTHON_WEBHOOK_PATH=/webhook/discord/message

# Authentication
SERVICE_SECRET=your_shared_secret_32_chars_min

# Server
PORT=3000
NODE_ENV=development

# Logging
LOG_LEVEL=info

# Allowlist
ALLOWLIST_REFRESH_INTERVAL=300000
```

### Configuration Loader (`src/config.js`)

```javascript
require('dotenv').config();

module.exports = {
  discord: {
    token: process.env.DISCORD_USER_TOKEN || '',
  },
  python: {
    serviceUrl: process.env.PYTHON_SERVICE_URL || 'http://backend:8000',
    webhookPath: process.env.PYTHON_WEBHOOK_PATH || '/webhook/discord/message',
  },
  auth: {
    serviceSecret: process.env.SERVICE_SECRET || '',
  },
  server: {
    port: parseInt(process.env.PORT || '3000', 10),
    env: process.env.NODE_ENV || 'development',
  },
  logging: {
    level: process.env.LOG_LEVEL || 'info',
  },
  allowlist: {
    refreshInterval: parseInt(process.env.ALLOWLIST_REFRESH_INTERVAL || '300000', 10),
  },
};
```

---

## Discord Gateway Client

### Implementation (`src/gateway.js`)

```javascript
const Discord = require('discord-user-bots');
const config = require('./config');
const logger = require('./utils/logger');
const webhook = require('./webhook');

class DiscordGateway {
  constructor() {
    this.client = new Discord.Client();
    this.connected = false;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
  }

  async connect() {
    try {
      logger.info('Connecting to Discord Gateway...');

      this.client.on('ready', () => {
        this.connected = true;
        this.reconnectAttempts = 0;
        logger.info(`Logged in as ${this.client.user.tag}`);
      });

      this.client.on('messageCreate', async (message) => {
        await this.handleMessage(message);
      });

      this.client.on('messageUpdate', async (oldMessage, newMessage) => {
        // Optional: Handle edited messages
        logger.debug('Message updated', { id: newMessage.id });
      });

      this.client.on('disconnect', () => {
        this.connected = false;
        logger.warn('Disconnected from Discord Gateway');
        this.handleReconnect();
      });

      this.client.on('error', (error) => {
        logger.error('Discord Gateway error:', error);
      });

      await this.client.login(config.discord.token);
    } catch (error) {
      logger.error('Failed to connect to Discord Gateway:', error);
      this.handleReconnect();
    }
  }

  async handleMessage(message) {
    try {
      logger.debug('Received message', {
        id: message.id,
        channel: message.channel.id,
        author: message.author.tag,
      });

      // Forward to webhook handler
      await webhook.forwardMessage(message);
    } catch (error) {
      logger.error('Error handling message:', error);
    }
  }

  handleReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      logger.error('Max reconnection attempts reached. Manual intervention required.');
      // Alert Python service
      webhook.alertServiceDown('Discord Gateway connection failed after max retries');
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 60000);

    logger.info(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);

    setTimeout(() => {
      this.connect();
    }, delay);
  }

  isConnected() {
    return this.connected;
  }

  getClient() {
    return this.client;
  }
}

module.exports = new DiscordGateway();
```

---

## REST API Server

### Implementation (`src/api.js`)

```javascript
const express = require('express');
const config = require('./config');
const logger = require('./utils/logger');
const auth = require('./utils/auth');
const gateway = require('./gateway');

const app = express();
app.use(express.json());

// Health check (no auth required)
app.get('/api/health', (req, res) => {
  const status = {
    status: gateway.isConnected() ? 'healthy' : 'unhealthy',
    connected: gateway.isConnected(),
    uptime: process.uptime(),
    timestamp: new Date().toISOString(),
  };

  const httpStatus = status.connected ? 200 : 503;
  res.status(httpStatus).json(status);
});

// All other endpoints require authentication
app.use(auth.validateServiceSecret);

// Send message to Discord
app.post('/api/discord/send', async (req, res) => {
  try {
    const { channel_id, content, reply_to_id } = req.body;

    if (!channel_id || !content) {
      return res.status(400).json({ success: false, error: 'Missing required fields' });
    }

    const client = gateway.getClient();
    const channel = await client.channels.fetch(channel_id);

    if (!channel) {
      return res.status(404).json({ success: false, error: 'Channel not found' });
    }

    const sentMessage = await channel.send({
      content,
      reply: reply_to_id ? { messageReference: reply_to_id } : undefined,
    });

    logger.info('Message sent to Discord', { channel_id, message_id: sentMessage.id });

    res.json({
      success: true,
      message_id: sentMessage.id,
      timestamp: sentMessage.createdAt,
    });
  } catch (error) {
    logger.error('Error sending message:', error);
    res.status(500).json({ success: false, error: error.message });
  }
});

// List accessible channels
app.get('/api/discord/channels', async (req, res) => {
  try {
    const client = gateway.getClient();
    const channels = [];

    for (const guild of client.guilds.cache.values()) {
      for (const channel of guild.channels.cache.values()) {
        if (channel.type === 'GUILD_TEXT' || channel.type === 'GUILD_NEWS') {
          channels.push({
            id: channel.id,
            name: channel.name,
            server_id: guild.id,
            server_name: guild.name,
            type: channel.type,
          });
        }
      }
    }

    res.json({ channels });
  } catch (error) {
    logger.error('Error fetching channels:', error);
    res.status(500).json({ error: error.message });
  }
});

// Fetch message history
app.get('/api/discord/history/:channel_id', async (req, res) => {
  try {
    const { channel_id } = req.params;
    const limit = parseInt(req.query.limit || '10', 10);
    const before = req.query.before;

    const client = gateway.getClient();
    const channel = await client.channels.fetch(channel_id);

    if (!channel) {
      return res.status(404).json({ error: 'Channel not found' });
    }

    const options = { limit };
    if (before) {
      options.before = before;
    }

    const messages = await channel.messages.fetch(options);
    const normalized = messages.map(msg => ({
      id: msg.id,
      content: msg.content,
      author: {
        id: msg.author.id,
        username: msg.author.username,
        discriminator: msg.author.discriminator,
      },
      timestamp: msg.createdAt,
      attachments: msg.attachments.map(att => ({
        url: att.url,
        type: att.contentType,
        filename: att.name,
      })),
    }));

    res.json({ messages: normalized });
  } catch (error) {
    logger.error('Error fetching history:', error);
    res.status(500).json({ error: error.message });
  }
});

function start() {
  app.listen(config.server.port, () => {
    logger.info(`Discord Service API listening on port ${config.server.port}`);
  });
}

module.exports = { app, start };
```

---

## Webhook Forwarder

### Implementation (`src/webhook.js`)

```javascript
const axios = require('axios');
const config = require('./config');
const logger = require('./utils/logger');
const normalizer = require('./normalizer');
const allowlist = require('./allowlist');

class WebhookForwarder {
  constructor() {
    this.pythonUrl = `${config.python.serviceUrl}${config.python.webhookPath}`;
    this.maxRetries = 3;
  }

  async forwardMessage(message) {
    try {
      // Check allowlist
      if (!await allowlist.isChannelAllowed(message.channel.id)) {
        logger.debug('Message dropped (not in allowlist)', { channel_id: message.channel.id });
        return;
      }

      // Normalize message
      const normalized = normalizer.normalizeMessage(message);

      // Send to Python webhook
      await this.sendWithRetry(normalized);

      logger.info('Message forwarded to Python', { message_id: message.id });
    } catch (error) {
      logger.error('Failed to forward message:', error);
    }
  }

  async sendWithRetry(payload, attempt = 1) {
    try {
      await axios.post(this.pythonUrl, payload, {
        headers: {
          'Content-Type': 'application/json',
          'X-Service-Secret': config.auth.serviceSecret,
        },
        timeout: 10000,
      });
    } catch (error) {
      if (attempt < this.maxRetries) {
        const delay = 1000 * Math.pow(2, attempt);
        logger.warn(`Webhook failed, retrying in ${delay}ms (attempt ${attempt}/${this.maxRetries})...`);

        await new Promise(resolve => setTimeout(resolve, delay));
        return this.sendWithRetry(payload, attempt + 1);
      }

      logger.error('Webhook failed after max retries:', error.message);
      throw error;
    }
  }

  async alertServiceDown(reason) {
    try {
      await axios.post(`${config.python.serviceUrl}/alerts/critical`, {
        type: 'DISCORD_SERVICE_DOWN',
        reason,
        timestamp: new Date().toISOString(),
      }, {
        headers: {
          'X-Service-Secret': config.auth.serviceSecret,
        },
        timeout: 5000,
      });
    } catch (error) {
      logger.error('Failed to send alert to Python:', error.message);
    }
  }
}

module.exports = new WebhookForwarder();
```

---

## Message Normalizer

### Implementation (`src/normalizer.js`)

```javascript
function normalizeMessage(message) {
  const guild = message.guild;
  const thread = message.channel.isThread() ? message.channel : null;

  return {
    platform: 'discord',
    message_id: message.id,
    channel_id: message.channel.id,
    server_id: guild ? guild.id : null,
    server_name: guild ? guild.name : null,
    channel_name: message.channel.name,
    thread_id: thread ? thread.id : null,
    thread_name: thread ? thread.name : null,
    author: {
      id: message.author.id,
      username: message.author.username,
      discriminator: message.author.discriminator,
      bot: message.author.bot,
    },
    content: message.content,
    timestamp: message.createdAt.toISOString(),
    attachments: message.attachments.map(att => ({
      url: att.url,
      type: att.contentType || 'unknown',
      filename: att.name,
      size: att.size,
    })),
    is_edit: false,
    mentions: {
      users: message.mentions.users.map(u => u.id),
      roles: message.mentions.roles.map(r => r.id),
      everyone: message.mentions.everyone,
    },
  };
}

module.exports = { normalizeMessage };
```

---

## Allowlist Manager

### Implementation (`src/allowlist.js`)

```javascript
const axios = require('axios');
const config = require('./config');
const logger = require('./utils/logger');

class AllowlistManager {
  constructor() {
    this.allowedChannels = new Set();
    this.lastRefresh = null;
    this.refreshInterval = config.allowlist.refreshInterval;
  }

  async initialize() {
    await this.refresh();

    // Auto-refresh periodically
    setInterval(() => {
      this.refresh().catch(err => {
        logger.error('Failed to refresh allowlist:', err.message);
      });
    }, this.refreshInterval);
  }

  async refresh() {
    try {
      const response = await axios.get(`${config.python.serviceUrl}/api/allowlist`, {
        headers: {
          'X-Service-Secret': config.auth.serviceSecret,
        },
        timeout: 5000,
      });

      const { channel_ids } = response.data;
      this.allowedChannels = new Set(channel_ids);
      this.lastRefresh = new Date();

      logger.info(`Allowlist refreshed: ${channel_ids.length} channels`);
    } catch (error) {
      logger.error('Failed to fetch allowlist:', error.message);
      throw error;
    }
  }

  async isChannelAllowed(channelId) {
    if (!this.lastRefresh) {
      await this.refresh();
    }

    return this.allowedChannels.has(channelId);
  }

  getSize() {
    return this.allowedChannels.size;
  }
}

module.exports = new AllowlistManager();
```

---

## Utilities

### Logger (`src/utils/logger.js`)

```javascript
const config = require('../config');

const levels = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
};

const currentLevel = levels[config.logging.level] || levels.info;

function log(level, message, ...args) {
  if (levels[level] >= currentLevel) {
    const timestamp = new Date().toISOString();
    const prefix = `[${timestamp}] [${level.toUpperCase()}]`;
    console.log(prefix, message, ...args);
  }
}

module.exports = {
  debug: (msg, ...args) => log('debug', msg, ...args),
  info: (msg, ...args) => log('info', msg, ...args),
  warn: (msg, ...args) => log('warn', msg, ...args),
  error: (msg, ...args) => log('error', msg, ...args),
};
```

### Auth Middleware (`src/utils/auth.js`)

```javascript
const config = require('../config');
const logger = require('./logger');

function validateServiceSecret(req, res, next) {
  const providedSecret = req.headers['x-service-secret'];

  if (!providedSecret) {
    logger.warn('Request without service secret', { ip: req.ip, path: req.path });
    return res.status(401).json({ error: 'Missing authentication' });
  }

  if (providedSecret !== config.auth.serviceSecret) {
    logger.warn('Invalid service secret', { ip: req.ip, path: req.path });
    return res.status(403).json({ error: 'Invalid authentication' });
  }

  next();
}

module.exports = { validateServiceSecret };
```

---

## Entry Point

### Implementation (`src/index.js`)

```javascript
const gateway = require('./gateway');
const api = require('./api');
const allowlist = require('./allowlist');
const logger = require('./utils/logger');

async function main() {
  try {
    logger.info('Starting Discord Service...');

    // Initialize allowlist
    await allowlist.initialize();

    // Connect to Discord Gateway
    await gateway.connect();

    // Start API server
    api.start();

    logger.info('Discord Service started successfully');
  } catch (error) {
    logger.error('Failed to start Discord Service:', error);
    process.exit(1);
  }
}

// Graceful shutdown
process.on('SIGINT', () => {
  logger.info('Shutting down gracefully...');
  process.exit(0);
});

process.on('SIGTERM', () => {
  logger.info('Shutting down gracefully...');
  process.exit(0);
});

main();
```

---

## Docker Configuration

### Dockerfile

```dockerfile
FROM node:18-alpine

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci --only=production

# Copy source code
COPY src ./src

# Expose port
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD node -e "require('http').get('http://localhost:3000/api/health', (r) => {process.exit(r.statusCode === 200 ? 0 : 1)})"

# Start service
CMD ["node", "src/index.js"]
```

### .dockerignore

```
node_modules
npm-debug.log
.env
.git
.gitignore
README.md
tests
*.test.js
.vscode
.idea
```

---

## package.json

```json
{
  "name": "discord-service",
  "version": "1.0.0",
  "description": "Node.js Discord Gateway service for Moderator project",
  "main": "src/index.js",
  "scripts": {
    "start": "node src/index.js",
    "dev": "nodemon src/index.js",
    "test": "jest",
    "test:watch": "jest --watch",
    "test:coverage": "jest --coverage"
  },
  "dependencies": {
    "discord-user-bots": "^1.0.0",
    "express": "^4.18.2",
    "axios": "^1.6.0",
    "dotenv": "^16.3.0"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "nodemon": "^3.0.0"
  },
  "engines": {
    "node": ">=18.0.0"
  }
}
```

---

## Testing

### Example Test (`tests/gateway.test.js`)

```javascript
const gateway = require('../src/gateway');

// Mock discord-user-bots
jest.mock('discord-user-bots', () => {
  return {
    Client: jest.fn().mockImplementation(() => ({
      on: jest.fn(),
      login: jest.fn().mockResolvedValue(true),
      user: { tag: 'TestUser#1234' },
    })),
  };
});

describe('DiscordGateway', () => {
  test('should connect successfully', async () => {
    await expect(gateway.connect()).resolves.not.toThrow();
  });

  test('should indicate connected status', () => {
    expect(gateway.isConnected()).toBe(true);
  });
});
```

---

## Deployment

### With Docker Compose

Add to project root `docker-compose.yml`:

```yaml
services:
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
      - backend
    healthcheck:
      test: ["CMD", "node", "-e", "require('http').get('http://localhost:3000/api/health')"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  backend:
    # ... Python service config ...

networks:
  moderator-network:
    driver: bridge
```

---

## Next Steps

1. Initialize Node.js project: `npm init`
2. Install dependencies: `npm install`
3. Implement files according to this spec
4. Test locally before Docker
5. Build Docker image
6. Test with docker-compose
7. Integrate with Python service
8. Deploy to production

---

**End of Specification**
