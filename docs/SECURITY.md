# Security Guide

This document provides comprehensive security guidance for the moderator system, including secrets management, token rotation procedures, and security best practices.

## Table of Contents

- [Overview](#overview)
- [Secrets Management](#secrets-management)
  - [Docker Secrets](#docker-secrets)
  - [Environment Variables](#environment-variables)
  - [Supported Secrets](#supported-secrets)
- [Token Rotation Procedures](#token-rotation-procedures)
  - [Discord Token Rotation](#discord-token-rotation)
  - [Telegram Bot Token Rotation](#telegram-bot-token-rotation)
  - [Database Password Rotation](#database-password-rotation)
  - [Encryption Key Rotation](#encryption-key-rotation)
  - [LLM API Keys Rotation](#llm-api-keys-rotation)
- [Token Validation](#token-validation)
- [Emergency Procedures](#emergency-procedures)
- [Rotation Schedule](#rotation-schedule)
- [Security Best Practices](#security-best-practices)

---

## Overview

The moderator system handles sensitive credentials including Discord tokens, Telegram bot tokens, database passwords, encryption keys, and LLM API keys. Proper management and regular rotation of these secrets is critical for maintaining system security.

This guide covers:
- How to securely store and manage secrets
- Step-by-step procedures for rotating each type of credential
- Zero-downtime rotation strategies
- Emergency response procedures
- Recommended rotation schedules

---

## Secrets Management

The system supports two methods for providing sensitive credentials:

### Docker Secrets

**Recommended for production deployments.**

Docker Secrets provide a secure way to manage sensitive data in containerized environments. Secrets are mounted as files in `/run/secrets/` and are only accessible to authorized containers.

#### Setting Up Docker Secrets

1. **Create a secret:**
   ```bash
   # From a file
   docker secret create TELEGRAM_TOKEN ./telegram_token.txt

   # From stdin
   echo "your_secret_value" | docker secret create ENCRYPTION_KEY -
   ```

2. **Reference in docker-compose.yml:**
   ```yaml
   version: '3.8'

   services:
     backend:
       image: moderator-backend
       secrets:
         - TELEGRAM_TOKEN
         - DISCORD_TOKEN
         - DATABASE_PASSWORD
         - ENCRYPTION_KEY
         - OPENAI_KEY
         - ANTHROPIC_KEY

   secrets:
     TELEGRAM_TOKEN:
       external: true
     DISCORD_TOKEN:
       external: true
     DATABASE_PASSWORD:
       external: true
     ENCRYPTION_KEY:
       external: true
     OPENAI_KEY:
       external: true
     ANTHROPIC_KEY:
       external: true
   ```

3. **The system will automatically read from `/run/secrets/` first, then fall back to environment variables if secrets are not found.**

#### Benefits of Docker Secrets

- Secrets are encrypted at rest and in transit
- Only accessible to authorized containers
- Not stored in image layers or container inspection output
- Can be rotated without rebuilding images
- Centralized secret management

### Environment Variables

**Acceptable for development and testing.**

Environment variables can be used via `.env` files or shell exports. This method is less secure than Docker Secrets and should only be used in non-production environments.

```bash
# .env file
TELEGRAM_BOT_TOKEN=your_telegram_token
DISCORD_USER_TOKEN=your_discord_token
DB_PASSWORD=your_db_password
ENCRYPTION_KEY=your_encryption_key
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
```

**Security Warning:** Environment variables may be visible in process listings, logs, and error messages. Use Docker Secrets for production deployments.

### Supported Secrets

The system supports Docker Secrets for the following credentials:

| Secret Name (Docker) | Environment Variable (Fallback) | Description |
|---------------------|----------------------------------|-------------|
| `TELEGRAM_TOKEN` | `TELEGRAM_BOT_TOKEN` | Telegram Bot API token |
| `DISCORD_TOKEN` | `DISCORD_USER_TOKEN` | Discord user token |
| `DATABASE_PASSWORD` | `DB_PASSWORD` | PostgreSQL database password |
| `ENCRYPTION_KEY` | `ENCRYPTION_KEY` | Fernet encryption key for storing sensitive data |
| `OPENAI_KEY` | `OPENAI_API_KEY` | OpenAI API key (optional) |
| `ANTHROPIC_KEY` | `ANTHROPIC_API_KEY` | Anthropic API key (optional) |

---

## Token Rotation Procedures

### Discord Token Rotation

Discord user tokens should be rotated when:
- Suspicion of compromise
- As part of regular security maintenance (every 90 days recommended)
- After employee/contractor offboarding

#### Step-by-Step Procedure

**Preparation:**

1. **Obtain a new Discord token:**
   - Log into Discord in a browser
   - Open Developer Tools (F12)
   - Go to Network tab, filter by XHR
   - Look for any request to discord.com/api
   - Find the `Authorization` header - this is your new token

2. **Verify the new token works:**
   ```bash
   curl -H "Authorization: YOUR_NEW_TOKEN" https://discord.com/api/v10/users/@me
   ```
   Should return your user information (HTTP 200).

**Zero-Downtime Rotation (Docker Secrets):**

3. **Create the new secret:**
   ```bash
   echo "YOUR_NEW_DISCORD_TOKEN" | docker secret create DISCORD_TOKEN_v2 -
   ```

4. **Update docker-compose.yml to reference the new secret:**
   ```yaml
   services:
     backend:
       secrets:
         - source: DISCORD_TOKEN_v2
           target: DISCORD_TOKEN

   secrets:
     DISCORD_TOKEN_v2:
       external: true
   ```

5. **Deploy the updated configuration:**
   ```bash
   docker stack deploy -c docker-compose.yml moderator
   # OR for docker-compose
   docker-compose up -d
   ```

6. **Verify the service is running with the new token:**
   ```bash
   # Check logs for successful connection
   docker-compose logs -f backend

   # Use the /discord_status command in Telegram to verify connection
   ```

7. **Remove the old secret (after 24-48 hours of stability):**
   ```bash
   docker secret rm DISCORD_TOKEN
   ```

**Environment Variable Rotation:**

3. **Update the `.env` file:**
   ```bash
   # Edit .env
   DISCORD_USER_TOKEN=YOUR_NEW_DISCORD_TOKEN
   ```

4. **Restart the service:**
   ```bash
   docker-compose restart backend
   ```

5. **Verify the service is running:**
   ```bash
   docker-compose logs -f backend
   ```

**Rollback Procedure:**

If issues occur after rotation:

```bash
# Revert to previous secret version
docker secret create DISCORD_TOKEN_rollback -
# Update docker-compose.yml to point to old secret
docker stack deploy -c docker-compose.yml moderator
```

---

### Telegram Bot Token Rotation

Telegram bot tokens should be rotated when:
- Token is accidentally exposed (logs, public repository, etc.)
- Suspicion of unauthorized access
- As part of security audit requirements

#### Step-by-Step Procedure

**Preparation:**

1. **Revoke the old token and generate a new one:**
   - Open Telegram and message @BotFather
   - Send `/mybots`
   - Select your bot
   - Select "API Token"
   - Select "Revoke current token"
   - Copy the new token

2. **IMPORTANT:** Revoking the old token immediately breaks the current bot. Plan for brief downtime or use the zero-downtime procedure below.

**Zero-Downtime Rotation (Recommended):**

3. **Create a new bot (temporary):**
   - Message @BotFather
   - Send `/newbot`
   - Follow the wizard to create a temporary bot
   - Copy the new token

4. **Update the secret with the NEW bot token:**
   ```bash
   echo "YOUR_NEW_BOT_TOKEN" | docker secret create TELEGRAM_TOKEN_v2 -
   ```

5. **Update docker-compose.yml:**
   ```yaml
   services:
     backend:
       secrets:
         - source: TELEGRAM_TOKEN_v2
           target: TELEGRAM_TOKEN
   ```

6. **Deploy the update:**
   ```bash
   docker stack deploy -c docker-compose.yml moderator
   ```

7. **Test the new bot:**
   - Send `/start` to the new bot
   - Verify all commands work
   - Check logs for errors

8. **Once verified stable, revoke the old bot token:**
   - Message @BotFather
   - Revoke the old bot's token

9. **Clean up the temporary bot (if created).**

**Alternative: Accept Brief Downtime:**

If zero-downtime is not required:

1. **Revoke and regenerate the token with @BotFather**
2. **Update the secret:**
   ```bash
   echo "YOUR_NEW_TOKEN" | docker secret create TELEGRAM_TOKEN_new -
   ```
3. **Update docker-compose.yml and redeploy**
4. **Service will be down for ~1-2 minutes during restart**

---

### Database Password Rotation

Database passwords should be rotated:
- Every 90 days (recommended)
- After suspected compromise
- After admin access revocation

#### Step-by-Step Procedure

**Preparation:**

1. **Choose the new password:**
   ```bash
   # Generate a strong password
   openssl rand -base64 32
   ```

2. **Update the database user password:**
   ```bash
   # Connect to PostgreSQL
   docker-compose exec db psql -U postgres

   # Change the password
   ALTER USER moderator_user WITH PASSWORD 'NEW_SECURE_PASSWORD';
   ```

**Zero-Downtime Rotation:**

3. **Create the new secret:**
   ```bash
   echo "NEW_SECURE_PASSWORD" | docker secret create DATABASE_PASSWORD_v2 -
   ```

4. **Update docker-compose.yml:**
   ```yaml
   services:
     backend:
       secrets:
         - source: DATABASE_PASSWORD_v2
           target: DATABASE_PASSWORD

     db:
       environment:
         POSTGRES_PASSWORD: # Reference secret or update manually
   ```

5. **Deploy the update:**
   ```bash
   docker stack deploy -c docker-compose.yml moderator
   ```

6. **Verify database connectivity:**
   ```bash
   # Check backend logs for successful DB connection
   docker-compose logs backend | grep -i database

   # Test via health check
   curl http://localhost:8000/health
   ```

7. **Remove old secret after verification:**
   ```bash
   docker secret rm DATABASE_PASSWORD
   ```

**Important Notes:**
- Database password rotation requires coordination between the DB and application
- Test connectivity before removing old credentials
- Keep a backup of the old password for 48 hours for rollback

---

### Encryption Key Rotation

The encryption key is used for encrypting sensitive data in the database (tokens, credentials). Rotation is complex and requires re-encryption of all data.

**WARNING:** Encryption key rotation requires careful planning and database migration.

#### Step-by-Step Procedure

**Preparation:**

1. **Generate a new Fernet key:**
   ```python
   from cryptography.fernet import Fernet
   new_key = Fernet.generate_key()
   print(new_key.decode())
   ```

2. **Create a database migration script** to re-encrypt all encrypted fields:
   - User tokens
   - Discord connection credentials
   - Any other encrypted metadata

3. **Test the migration in a staging environment first.**

**Migration Procedure:**

4. **Backup the database:**
   ```bash
   docker-compose exec db pg_dump -U moderator_user moderator_db > backup_pre_rotation.sql
   ```

5. **Put the system in maintenance mode** (stop accepting new messages).

6. **Run the migration script:**
   ```python
   # Example migration logic
   from cryptography.fernet import Fernet

   old_cipher = Fernet(OLD_ENCRYPTION_KEY)
   new_cipher = Fernet(NEW_ENCRYPTION_KEY)

   # For each encrypted field in database:
   # 1. Decrypt with old key
   # 2. Encrypt with new key
   # 3. Update database

   async with pool.acquire() as conn:
       rows = await conn.fetch("SELECT id, user_token_encrypted FROM discord_connection")
       for row in rows:
           decrypted = old_cipher.decrypt(row['user_token_encrypted'].encode())
           encrypted = new_cipher.encrypt(decrypted)
           await conn.execute(
               "UPDATE discord_connection SET user_token_encrypted = $1 WHERE id = $2",
               encrypted.decode(), row['id']
           )
   ```

7. **Update the encryption key secret:**
   ```bash
   echo "NEW_ENCRYPTION_KEY" | docker secret create ENCRYPTION_KEY_v2 -
   ```

8. **Update docker-compose.yml and redeploy.**

9. **Verify all encrypted data can be read correctly.**

10. **Remove maintenance mode and monitor for errors.**

**Rollback:**
If issues occur, restore from backup and revert to old key:
```bash
docker-compose exec db psql -U moderator_user moderator_db < backup_pre_rotation.sql
```

---

### LLM API Keys Rotation

LLM API keys (OpenAI, Anthropic) should be rotated:
- Every 30-90 days
- Immediately if exposed
- After team member changes

#### Step-by-Step Procedure

**OpenAI API Key:**

1. **Generate a new key:**
   - Visit https://platform.openai.com/api-keys
   - Create a new API key
   - Copy the key (it's only shown once)

2. **Update the secret:**
   ```bash
   echo "sk-new-openai-key" | docker secret create OPENAI_KEY_v2 -
   ```

3. **Update docker-compose.yml:**
   ```yaml
   services:
     backend:
       secrets:
         - source: OPENAI_KEY_v2
           target: OPENAI_KEY
   ```

4. **Deploy and verify:**
   ```bash
   docker stack deploy -c docker-compose.yml moderator

   # Test LLM functionality
   # Send a message that triggers AI response generation
   ```

5. **Revoke the old key:**
   - Visit https://platform.openai.com/api-keys
   - Delete the old key

**Anthropic API Key:**

1. **Generate a new key:**
   - Visit https://console.anthropic.com/settings/keys
   - Create a new API key
   - Copy the key

2. **Follow the same rotation procedure as OpenAI**

3. **Revoke the old key in Anthropic console**

---

## Token Validation

Before and after rotation, validate that tokens are working correctly:

### Discord Token Validation

```bash
# Test API access
curl -H "Authorization: YOUR_TOKEN" \
  https://discord.com/api/v10/users/@me

# Expected: HTTP 200 with user information
# If 401: Token is invalid or expired
```

### Telegram Bot Token Validation

```bash
# Test bot token
curl https://api.telegram.org/bot<YOUR_TOKEN>/getMe

# Expected: {"ok":true,"result":{...}}
# If ok=false: Token is invalid
```

### Database Connection Validation

```bash
# Test connection from backend
docker-compose exec backend python -c "
from config import config
from database.connection import get_pool
import asyncio

async def test():
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval('SELECT 1')
        print(f'Database connection: OK (result={result})')

asyncio.run(test())
"
```

### LLM API Key Validation

```bash
# OpenAI
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_OPENAI_KEY"

# Anthropic
curl https://api.anthropic.com/v1/messages \
  -H "x-api-key: YOUR_ANTHROPIC_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -H "content-type: application/json" \
  -d '{"model":"claude-3-sonnet-20240229","max_tokens":10,"messages":[{"role":"user","content":"test"}]}'
```

---

## Emergency Procedures

### Immediate Token Compromise Response

If you suspect a token has been compromised:

**IMMEDIATE ACTIONS (within 15 minutes):**

1. **Revoke the compromised credential immediately:**
   - Discord: Change password, invalidates all sessions/tokens
   - Telegram: Use @BotFather to revoke token
   - Database: Change password via PostgreSQL
   - LLM: Revoke API key in provider console

2. **Check audit logs for suspicious activity:**
   ```bash
   # Check recent audit logs
   docker-compose exec db psql -U moderator_user moderator_db -c \
     "SELECT * FROM audit_log WHERE created_at > NOW() - INTERVAL '24 hours' ORDER BY created_at DESC LIMIT 100;"
   ```

3. **Rotate to a new credential** (follow procedures above).

4. **Review system logs for unauthorized access:**
   ```bash
   docker-compose logs --tail=1000 backend | grep -i error
   docker-compose logs --tail=1000 backend | grep -i unauthorized
   ```

**FOLLOW-UP ACTIONS (within 24 hours):**

5. **Investigate how the compromise occurred**
6. **Review and update access controls**
7. **Conduct security audit of all other credentials**
8. **Document the incident and response**
9. **Implement additional monitoring if needed**

### Service Disruption During Rotation

If the service becomes unavailable during rotation:

1. **Check service status:**
   ```bash
   docker-compose ps
   docker-compose logs --tail=100 backend
   ```

2. **Verify secret is correctly mounted:**
   ```bash
   docker-compose exec backend ls -la /run/secrets/
   ```

3. **Test secret can be read:**
   ```bash
   docker-compose exec backend cat /run/secrets/TELEGRAM_TOKEN
   ```

4. **If secret is incorrect, roll back:**
   ```bash
   # Revert docker-compose.yml
   git checkout docker-compose.yml
   docker-compose up -d
   ```

5. **If issue persists, check logs and database connectivity**

---

## Rotation Schedule

### Recommended Rotation Frequencies

| Credential Type | Frequency | Trigger Events |
|----------------|-----------|----------------|
| Discord Token | 90 days | Compromise suspicion, security audit |
| Telegram Bot Token | 180 days | Exposure, unauthorized access |
| Database Password | 90 days | Admin changes, compromise suspicion |
| Encryption Key | 365 days | Major version upgrade, security requirement |
| OpenAI API Key | 90 days | Exposure, cost anomalies |
| Anthropic API Key | 90 days | Exposure, cost anomalies |

### Rotation Calendar

Create a recurring calendar reminder for token rotation:

- **Monthly (1st of month):** Review audit logs and access patterns
- **Quarterly (January 1, April 1, July 1, October 1):** Rotate Discord token, database password, LLM API keys
- **Semi-annually (January 1, July 1):** Rotate Telegram bot token
- **Annually (January 1):** Rotate encryption key (with database migration)

### Audit Trail

Maintain a rotation log:

```
# rotation_log.md

## 2025-11-19
- Rotated Discord token (scheduled quarterly rotation)
- Rotated OpenAI API key (scheduled quarterly rotation)
- No issues encountered

## 2025-10-15
- Emergency rotation of Telegram bot token (token exposed in logs)
- Incident report: INC-2025-001
- Root cause: Verbose logging in debug mode

## 2025-08-01
- Rotated database password (scheduled quarterly rotation)
- Rotated Anthropic API key (scheduled quarterly rotation)
- Completed without downtime
```

---

## Security Best Practices

### General

1. **Never commit secrets to version control**
   - Use `.gitignore` for `.env` files
   - Use Docker Secrets or secret management systems
   - Scan repositories with tools like `git-secrets` or `truffleHog`

2. **Use strong, unique credentials**
   - Minimum 32 characters for passwords and keys
   - Use cryptographically secure random generation
   - Never reuse credentials across systems

3. **Implement least privilege**
   - Database users should have minimum required permissions
   - API keys should have minimum required scopes
   - Use separate credentials for dev/staging/prod

4. **Monitor and audit**
   - Enable audit logging for all sensitive operations
   - Set up alerts for failed authentication attempts
   - Review logs regularly for suspicious activity

5. **Backup and recovery**
   - Keep encrypted backups of credentials (in secure vault)
   - Test recovery procedures regularly
   - Document all secret locations and access procedures

### Docker Secrets Specific

1. **Use external secrets** (don't define secrets in docker-compose.yml)
2. **Limit secret access** to only services that need them
3. **Rotate secrets regularly** as defined in schedule
4. **Use secret versioning** (e.g., `DISCORD_TOKEN_v1`, `DISCORD_TOKEN_v2`)
5. **Remove old secrets** after successful rotation and verification

### LLM API Keys

1. **Set usage limits** in provider dashboards
2. **Enable cost alerts** to detect anomalies
3. **Use separate keys** for dev and production
4. **Monitor token usage** via `/stats` command
5. **Revoke immediately** if unusual costs detected

### Database Security

1. **Use SSL/TLS** for database connections in production
2. **Limit network access** to database (firewall rules)
3. **Regular backups** with encryption
4. **Enable query logging** for audit purposes
5. **Use connection pooling** to limit concurrent connections

### Encryption

1. **Use Fernet** (AES-128 CBC) for symmetric encryption
2. **Never reuse encryption keys** across environments
3. **Rotate keys annually** or on security incidents
4. **Test decryption** after every key rotation
5. **Keep old keys** in secure vault for 30 days post-rotation (for recovery)

---

## Additional Resources

- [Discord Developer Documentation](https://discord.com/developers/docs)
- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [Docker Secrets Documentation](https://docs.docker.com/engine/swarm/secrets/)
- [OWASP Secret Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [Cryptography Best Practices](https://docs.python.org/3/library/cryptography.html)

---

## Questions and Support

If you encounter issues during token rotation or have security concerns:

1. **Check this documentation** for procedures and troubleshooting
2. **Review system logs** (`docker-compose logs`)
3. **Check audit logs** in the database
4. **Consult the incident response plan** for emergency procedures
5. **Document any new issues** to improve this guide

---

**Last Updated:** 2025-11-19
**Version:** 1.0
**Maintained by:** Security Team
