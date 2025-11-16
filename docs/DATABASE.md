# База данных

## Обзор

Система использует PostgreSQL для хранения всех данных: сообщений, метаданных, настроек, задач и аудит-логов.

## Схема базы данных

### Таблица: users

Информация о пользователях системы (в MVP - только один модератор).

```sql
CREATE TABLE users (
    id BIGSERIAL PRIMARY KEY,
    tg_user_id BIGINT NOT NULL UNIQUE,
    username VARCHAR(255),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_tg_user_id ON users(tg_user_id);
```

**Поля**:
- `id` - внутренний ID пользователя
- `tg_user_id` - Telegram user ID модератора
- `username` - имя пользователя (опционально)
- `created_at` - дата создания
- `updated_at` - дата последнего обновления

---

### Таблица: platform_accounts

Учетные записи на различных платформах (Discord, Telegram).

```sql
CREATE TABLE platform_accounts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    platform VARCHAR(50) NOT NULL, -- 'discord' | 'telegram'
    external_id VARCHAR(255) NOT NULL, -- Discord user ID или Telegram ID
    meta_encrypted TEXT, -- зашифрованные метаданные
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(platform, external_id)
);

CREATE INDEX idx_platform_accounts_user_id ON platform_accounts(user_id);
CREATE INDEX idx_platform_accounts_platform ON platform_accounts(platform);
```

**Поля**:
- `id` - внутренний ID аккаунта
- `user_id` - ссылка на users.id
- `platform` - платформа ('discord' или 'telegram')
- `external_id` - ID пользователя на платформе
- `meta_encrypted` - зашифрованные метаданные (JSON)
- `created_at`, `updated_at` - даты

---

### Таблица: discord_connection

Информация о подключении к Discord Gateway.

```sql
CREATE TABLE discord_connection (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    user_token_encrypted TEXT NOT NULL, -- зашифрованный User Token
    super_properties TEXT, -- JSON с super properties
    session_id VARCHAR(255),
    last_connected_at TIMESTAMP,
    status VARCHAR(50) DEFAULT 'disconnected', -- 'connected' | 'disconnected' | 'error'
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_discord_connection_user_id ON discord_connection(user_id);
CREATE INDEX idx_discord_connection_status ON discord_connection(status);
```

**Поля**:
- `id` - внутренний ID подключения
- `user_id` - ссылка на users.id
- `user_token_encrypted` - зашифрованный User Token Discord (AES-256)
- `super_properties` - технические параметры клиента (JSON)
- `session_id` - ID сессии подключения
- `last_connected_at` - время последнего успешного подключения
- `status` - статус подключения
- `error_message` - сообщение об ошибке (если есть)

---

### Таблица: channels_allowlist

Список разрешенных каналов для приема сообщений.

```sql
CREATE TABLE channels_allowlist (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL, -- 'discord' | 'telegram'
    server_id VARCHAR(255), -- Discord guild ID (NULL для Telegram)
    channel_id VARCHAR(255) NOT NULL,
    thread_filter_json TEXT, -- JSON с фильтрами по тредам (опционально)
    enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    UNIQUE(platform, server_id, channel_id)
);

CREATE INDEX idx_channels_allowlist_platform ON channels_allowlist(platform);
CREATE INDEX idx_channels_allowlist_enabled ON channels_allowlist(enabled);
CREATE INDEX idx_channels_allowlist_channel_id ON channels_allowlist(channel_id);
```

**Поля**:
- `id` - внутренний ID записи
- `platform` - платформа
- `server_id` - ID сервера Discord (NULL для Telegram)
- `channel_id` - ID канала
- `thread_filter_json` - фильтры по тредам (JSON): `{"thread_ids": ["123", "456"]}` или `{"thread_name_pattern": "Support-.*"}`
- `enabled` - активен ли канал

**Примеры thread_filter_json**:
```json
// Конкретные треды
{"thread_ids": ["123456789", "987654321"]}

// Все треды (no filter)
null

// По паттерну имени
{"thread_name_pattern": "^Support-"}
```

---

### Таблица: messages

Хранение сообщений из различных платформ.

```sql
CREATE TABLE messages (
    id BIGSERIAL PRIMARY KEY,
    platform VARCHAR(50) NOT NULL,
    ext_message_id VARCHAR(255) NOT NULL, -- ID сообщения на платформе
    server_id VARCHAR(255), -- Discord guild ID
    channel_id VARCHAR(255) NOT NULL,
    thread_id VARCHAR(255), -- Thread ID (опционально)
    author_id VARCHAR(255) NOT NULL,
    author_name VARCHAR(255),
    content TEXT,
    has_image BOOLEAN DEFAULT false,
    context_ref BIGINT, -- ссылка на "родительское" сообщение для контекста
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    platform_created_at TIMESTAMP, -- время создания на платформе
    UNIQUE(platform, ext_message_id)
);

CREATE INDEX idx_messages_platform ON messages(platform);
CREATE INDEX idx_messages_channel_id ON messages(channel_id);
CREATE INDEX idx_messages_author_id ON messages(author_id);
CREATE INDEX idx_messages_created_at ON messages(created_at);
CREATE INDEX idx_messages_context_ref ON messages(context_ref);
```

**Поля**:
- `id` - внутренний ID сообщения
- `platform` - платформа ('discord' или 'telegram')
- `ext_message_id` - ID сообщения на внешней платформе
- `server_id` - ID сервера (для Discord)
- `channel_id` - ID канала/чата
- `thread_id` - ID треда (опционально)
- `author_id` - ID автора сообщения
- `author_name` - имя автора
- `content` - текст сообщения
- `has_image` - флаг наличия изображения
- `context_ref` - ссылка на родительское сообщение (для формирования цепочки)
- `created_at` - время создания в нашей БД
- `platform_created_at` - время создания на платформе

---

### Таблица: attachments

Вложения к сообщениям (изображения, ссылки).

```sql
CREATE TABLE attachments (
    id BIGSERIAL PRIMARY KEY,
    message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    kind VARCHAR(50) NOT NULL, -- 'image' | 'link' | 'video' | 'file'
    ref TEXT NOT NULL, -- URL или путь к файлу
    meta TEXT, -- JSON с метаданными (размер, тип, и т.д.)
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_attachments_message_id ON attachments(message_id);
CREATE INDEX idx_attachments_kind ON attachments(kind);
```

**Поля**:
- `id` - внутренний ID вложения
- `message_id` - ссылка на messages.id
- `kind` - тип вложения
- `ref` - ссылка на ресурс (URL)
- `meta` - метаданные (JSON): `{"size": 1024, "mime_type": "image/png", "width": 800, "height": 600}`

---

### Таблица: tasks

Задачи для модератора (входящие сообщения, требующие ответа).

```sql
CREATE TABLE tasks (
    id BIGSERIAL PRIMARY KEY,
    source_message_id BIGINT NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL DEFAULT 'open', -- 'open' | 'answered' | 'muted' | 'error'
    assignee_user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tg_card_message_id BIGINT, -- ID карточки в Telegram
    error_message TEXT, -- сообщение об ошибке (если status = 'error')
    reminder_count INT DEFAULT 0, -- количество отправленных напоминаний
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    answered_at TIMESTAMP -- время ответа
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_assignee_user_id ON tasks(assignee_user_id);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);
CREATE INDEX idx_tasks_source_message_id ON tasks(source_message_id);
```

**Поля**:
- `id` - внутренний ID задачи
- `source_message_id` - ссылка на исходное сообщение
- `status` - статус задачи
- `assignee_user_id` - кому назначена (модератор)
- `tg_card_message_id` - ID карточки в Telegram
- `error_message` - текст ошибки
- `reminder_count` - счетчик напоминаний (v0.2+)
- `created_at`, `updated_at` - даты
- `answered_at` - время ответа

**Статусы**:
- `open` - открыта, ожидает ответа
- `answered` - отвечена
- `muted` - заглушена (DND режим)
- `error` - ошибка при отправке

---

### Таблица: replies

Ответы модератора на задачи.

```sql
CREATE TABLE replies (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    generated_by VARCHAR(50) NOT NULL DEFAULT 'human', -- 'human' | 'llm'
    llm_confidence FLOAT, -- уверенность LLM (0.0 - 1.0), если generated_by = 'llm'
    confirmed BOOLEAN NOT NULL DEFAULT false,
    posted_at TIMESTAMP, -- время успешной отправки
    platform_ref TEXT, -- JSON с информацией о постинге: {"platform": "discord", "message_id": "123"}
    edit_of BIGINT REFERENCES replies(id), -- ссылка на оригинальный ответ (если это редактирование)
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_replies_task_id ON replies(task_id);
CREATE INDEX idx_replies_generated_by ON replies(generated_by);
CREATE INDEX idx_replies_confirmed ON replies(confirmed);
CREATE INDEX idx_replies_edit_of ON replies(edit_of);
```

**Поля**:
- `id` - внутренний ID ответа
- `task_id` - ссылка на задачу
- `content` - текст ответа
- `generated_by` - кто сгенерировал ('human' или 'llm')
- `llm_confidence` - уверенность LLM (опционально, v0.2+)
- `confirmed` - подтвержден ли ответ модератором
- `posted_at` - время успешной отправки
- `platform_ref` - JSON с информацией о постинге: `{"platform": "discord", "message_id": "123456", "channel_id": "789"}`
- `edit_of` - ссылка на оригинальный reply (для истории редактирования, v1.0+)

---

### Таблица: settings

Настройки модератора.

```sql
CREATE TABLE settings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    dnd_enabled BOOLEAN NOT NULL DEFAULT false,
    dnd_schedule_json TEXT, -- JSON с расписанием DND
    reminders_enabled BOOLEAN NOT NULL DEFAULT false, -- v0.2+
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_settings_user_id ON settings(user_id);
```

**Поля**:
- `id` - внутренний ID настроек
- `user_id` - ссылка на users.id (один пользователь = одна запись)
- `dnd_enabled` - включен ли DND режим
- `dnd_schedule_json` - расписание DND (JSON)
- `reminders_enabled` - включены ли напоминания (v0.2+)

**Пример dnd_schedule_json**:
```json
{
  "intervals": [
    {
      "days": [1, 2, 3, 4, 5],
      "start_time": "22:00",
      "end_time": "08:00"
    },
    {
      "days": [6, 7],
      "start_time": "00:00",
      "end_time": "23:59"
    }
  ]
}
```
- `days`: 1=Monday, 7=Sunday
- `start_time`, `end_time`: HH:MM формат

---

### Таблица: audit_log

Аудит-лог всех действий в системе.

```sql
CREATE TABLE audit_log (
    id BIGSERIAL PRIMARY KEY,
    kind VARCHAR(100) NOT NULL, -- тип события
    user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
    payload_json TEXT NOT NULL, -- JSON с деталями события
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_kind ON audit_log(kind);
CREATE INDEX idx_audit_log_user_id ON audit_log(user_id);
CREATE INDEX idx_audit_log_created_at ON audit_log(created_at);
```

**Поля**:
- `id` - внутренний ID записи
- `kind` - тип события
- `user_id` - кто совершил действие
- `payload_json` - детали (JSON)
- `created_at` - время события

**Типы событий (kind)**:
- `message_received` - получено сообщение
- `task_created` - создана задача
- `reply_sent` - отправлен ответ
- `reply_edited` - отредактирован ответ (v1.0+)
- `setting_changed` - изменена настройка
- `allowlist_updated` - обновлен allowlist
- `discord_connected` - подключение к Discord Gateway
- `discord_disconnected` - отключение от Discord Gateway
- `error_occurred` - произошла ошибка

**Пример payload_json**:
```json
{
  "action": "reply_sent",
  "task_id": 123,
  "reply_id": 456,
  "platform": "discord",
  "channel_id": "789012345",
  "success": true
}
```

---

## ER-диаграмма (текстовая)

```
users (1) ─── (M) platform_accounts
  │
  ├── (1) discord_connection
  │
  ├── (1) settings
  │
  └── (M) tasks
         │
         ├── (1) messages (source_message_id)
         │      │
         │      └── (M) attachments
         │
         └── (M) replies
                │
                └── (1) replies (edit_of) [self-reference]

channels_allowlist (независимая таблица)

audit_log (независимая таблица, опциональная ссылка на users)
```

---

## Индексы и производительность

### Основные индексы

Все индексы указаны в определениях таблиц выше.

### Композитные индексы (опционально, для оптимизации)

```sql
-- Для быстрого поиска открытых задач модератора
CREATE INDEX idx_tasks_assignee_status ON tasks(assignee_user_id, status);

-- Для быстрого поиска сообщений по каналу и дате
CREATE INDEX idx_messages_channel_created ON messages(channel_id, created_at DESC);

-- Для поиска по автору и дате
CREATE INDEX idx_messages_author_created ON messages(author_id, created_at DESC);
```

---

## Политики хранения данных

### Срок хранения: 90 дней

Все данные хранятся 90 дней, затем автоматически удаляются.

### Cron-задача для очистки

Выполняется ежедневно в 03:00 UTC:

```sql
-- Удаление старых сообщений
DELETE FROM messages WHERE created_at < NOW() - INTERVAL '90 days';

-- Удаление старых задач
DELETE FROM tasks WHERE created_at < NOW() - INTERVAL '90 days';

-- Удаление старых ответов
DELETE FROM replies WHERE created_at < NOW() - INTERVAL '90 days';

-- Удаление старых audit logs
DELETE FROM audit_log WHERE created_at < NOW() - INTERVAL '90 days';

-- Вложения удаляются каскадно при удалении messages
```

### Каскадное удаление

При удалении родительской записи автоматически удаляются дочерние:
- `users` → `platform_accounts`, `discord_connection`, `tasks`, `settings`
- `messages` → `attachments`
- `tasks` → `replies`

---

## Шифрование данных

### Зашифрованные поля

1. **discord_connection.user_token_encrypted**
   - Алгоритм: AES-256-CBC
   - Ключ хранится в переменной окружения: `ENCRYPTION_KEY`

2. **platform_accounts.meta_encrypted**
   - Алгоритм: AES-256-CBC
   - Используется для хранения чувствительных метаданных

### Пример шифрования/дешифрования (псевдокод)

```python
from cryptography.fernet import Fernet
import os

# Генерация ключа (один раз при инициализации)
# key = Fernet.generate_key()
# Сохранить в .env: ENCRYPTION_KEY=<key>

# Использование
cipher = Fernet(os.getenv('ENCRYPTION_KEY'))

# Шифрование
encrypted_token = cipher.encrypt(user_token.encode())

# Дешифрование
decrypted_token = cipher.decrypt(encrypted_token).decode()
```

---

## Миграции

### Управление версиями схемы

Рекомендуется использовать инструменты миграций:
- **Python**: Alembic (SQLAlchemy)
- **Node.js**: Prisma Migrate или Knex.js

### Пример структуры миграций

```
migrations/
├── 001_initial_schema.sql
├── 002_add_discord_connection.sql
├── 003_add_llm_fields.sql (v0.2)
└── 004_add_search_indexes.sql (v1.0)
```

---

## Резервное копирование

### Политика бэкапов

**ВАЖНО**: По решению заказчика бэкапы БД отсутствуют.

Если в будущем потребуется:
- pg_dump ежедневно
- Хранение 7 дней локально
- S3 или аналог для долгосрочного хранения

---

## Размер БД (прогноз)

### Расчет на 90 дней

Допущения:
- 300 событий/сутки
- Средний размер сообщения: 500 байт
- 10% сообщений с изображениями (только ссылки, сами файлы не хранятся)

```
Сообщения: 300 * 90 = 27,000 записей
  27,000 * 1 KB (с индексами) ≈ 27 MB

Задачи: 27,000 записей ≈ 10 MB

Ответы: 27,000 записей ≈ 15 MB

Attachments: 2,700 записей ≈ 1 MB

Audit log: ~50,000 записей ≈ 20 MB

ИТОГО: ~75-100 MB для 90 дней данных
```

При 1000 событий/сутки: ~250-300 MB.

---

## Запросы для мониторинга

### Размер таблиц

```sql
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
```

### Количество записей

```sql
SELECT
    'messages' AS table_name, COUNT(*) AS count FROM messages
UNION ALL
SELECT 'tasks', COUNT(*) FROM tasks
UNION ALL
SELECT 'replies', COUNT(*) FROM replies
UNION ALL
SELECT 'audit_log', COUNT(*) FROM audit_log;
```

### Открытые задачи

```sql
SELECT
    status,
    COUNT(*) AS count,
    AVG(EXTRACT(EPOCH FROM (NOW() - created_at))/3600) AS avg_age_hours
FROM tasks
GROUP BY status;
```

---

## Оптимизация запросов

### Частые запросы

1. **Получение контекста для карточки** (последние N сообщений из канала)
```sql
SELECT * FROM messages
WHERE channel_id = $1 AND thread_id = $2
ORDER BY platform_created_at DESC
LIMIT 10;
```

2. **Открытые задачи модератора**
```sql
SELECT t.*, m.content, m.author_name
FROM tasks t
JOIN messages m ON t.source_message_id = m.id
WHERE t.assignee_user_id = $1 AND t.status = 'open'
ORDER BY t.created_at DESC;
```

3. **Проверка allowlist**
```sql
SELECT * FROM channels_allowlist
WHERE platform = $1
  AND (server_id = $2 OR server_id IS NULL)
  AND channel_id = $3
  AND enabled = true
LIMIT 1;
```

### EXPLAIN ANALYZE

Рекомендуется периодически проверять планы выполнения для медленных запросов:

```sql
EXPLAIN ANALYZE
SELECT ...;
```

---

## Безопасность БД

### Рекомендации

1. **Доступ**: только локальный или через VPN
2. **Пароли**: сильные пароли, rotация
3. **SSL**: включить для соединений
4. **Роли**: отдельные роли для чтения/записи
5. **Аудит**: логирование всех подключений

### Пример создания пользователя

```sql
-- Создание пользователя приложения
CREATE USER moderator_app WITH PASSWORD 'strong_password_here';

-- Права на схему
GRANT CONNECT ON DATABASE moderator_db TO moderator_app;
GRANT USAGE ON SCHEMA public TO moderator_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO moderator_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO moderator_app;

-- Для будущих таблиц
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO moderator_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO moderator_app;
```

---

## Тестовые данные

### Seed для разработки

```sql
-- Создание тестового пользователя
INSERT INTO users (tg_user_id, username) VALUES (123456789, 'test_moderator');

-- Настройки по умолчанию
INSERT INTO settings (user_id, dnd_enabled)
VALUES (1, false);

-- Тестовый канал в allowlist
INSERT INTO channels_allowlist (platform, server_id, channel_id, enabled)
VALUES ('discord', '111111111111111111', '222222222222222222', true);
```
