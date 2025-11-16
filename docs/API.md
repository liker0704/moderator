# API и интеграции

## Внутренние API компонентов

### 1. Ingest API

#### Discord Ingest
Обрабатывает события из Discord Gateway.

**Внутренний метод**:
```python
def handle_message_create(event: DiscordMessageEvent) -> Task:
    """
    Обработка события MESSAGE_CREATE из Discord Gateway

    Args:
        event: событие из Gateway

    Returns:
        Task: созданная задача для модератора
    """
    # 1. Проверить allowlist
    if not is_channel_allowed(event.channel_id, event.guild_id):
        return None

    # 2. Сохранить message
    message = store_message(event)

    # 3. Создать task
    task = create_task(message)

    # 4. Отправить карточку в TG
    send_card_to_telegram(task)

    return task
```

#### Telegram Ingest
Обрабатывает входящие сообщения в Telegram.

**Webhook endpoint**:
```
POST /webhook/telegram
Content-Type: application/json

{
  "update_id": 123456,
  "message": {
    "message_id": 789,
    "from": {"id": 987654, "username": "user"},
    "chat": {"id": 987654, "type": "private"},
    "text": "Hello"
  }
}
```

**Response**: 200 OK

---

### 2. Poster API

#### Discord Poster
Отправка сообщений в Discord через User API.

**Внутренний метод**:
```python
def post_to_discord(
    channel_id: str,
    content: str,
    thread_id: Optional[str] = None,
    reply_to: Optional[str] = None
) -> dict:
    """
    Отправка сообщения в Discord

    Args:
        channel_id: ID канала
        content: текст сообщения (plain text)
        thread_id: ID треда (опционально)
        reply_to: ID сообщения для reply (опционально)

    Returns:
        dict: {"success": bool, "message_id": str, "error": str}
    """
```

**Discord REST API**:
```
POST https://discord.com/api/v9/channels/{channel_id}/messages
Authorization: {user_token}
Content-Type: application/json

{
  "content": "Reply text here",
  "message_reference": {
    "message_id": "original_message_id"
  }
}
```

**Response**:
```json
{
  "id": "new_message_id",
  "channel_id": "channel_id",
  "content": "Reply text here",
  "timestamp": "2025-11-16T12:00:00.000000+00:00"
}
```

#### Telegram Poster
Отправка сообщений через Telegram Bot API.

**Метод**:
```python
def post_to_telegram(
    chat_id: int,
    text: str,
    reply_to_message_id: Optional[int] = None
) -> dict:
    """
    Отправка сообщения в Telegram

    Args:
        chat_id: ID чата
        text: текст (plain text)
        reply_to_message_id: ID для reply

    Returns:
        dict: {"success": bool, "message_id": int, "error": str}
    """
```

**Telegram Bot API**:
```
POST https://api.telegram.org/bot{token}/sendMessage
Content-Type: application/json

{
  "chat_id": 123456789,
  "text": "Reply text",
  "reply_to_message_id": 987,
  "disable_web_page_preview": true
}
```

---

### 3. Card Service API

Формирование и отправка карточек в Telegram.

**Метод создания карточки**:
```python
def create_card(task: Task) -> TelegramMessage:
    """
    Создание карточки для задачи

    Args:
        task: задача с источником сообщения

    Returns:
        TelegramMessage: отправленное сообщение
    """
    # 1. Получить контекст (~10 сообщений)
    context = get_context(task.source_message, limit=10)

    # 2. Форматировать карточку
    card_text = format_card(task, context)

    # 3. Создать кнопки
    keyboard = create_keyboard(task)

    # 4. Отправить в TG
    return send_telegram_message(
        chat_id=task.assignee.tg_user_id,
        text=card_text,
        reply_markup=keyboard
    )
```

**Формат карточки**:
```
Discord • Server Name • #channel-name • @author • 12:34

Context (last 10 messages):
[10:00] user1: Message 1
[10:15] user2: Message 2
...
[12:34] author: Current message

[Reply] [Show More] [DND]
```

**Кнопки (Inline Keyboard)**:
```python
keyboard = {
    "inline_keyboard": [
        [
            {"text": "Ответить", "callback_data": f"reply_{task_id}"},
            {"text": "Показать больше", "callback_data": f"more_{task_id}"}
        ],
        [
            {"text": "DND", "callback_data": "toggle_dnd"}
        ]
    ]
}
```

---

### 4. LLM Service API (v0.2+)

Генерация вариантов ответов.

**Метод**:
```python
def generate_variants(
    task_id: int,
    num_variants: int = 2
) -> List[dict]:
    """
    Генерация вариантов ответа

    Args:
        task_id: ID задачи
        num_variants: количество вариантов

    Returns:
        List[dict]: варианты с confidence
    """
```

**LLM Prompt**:
```
System: You are a moderator responding to community messages. Be concise, neutral, and helpful.

Context (conversation history):
[10:00] user1: Previous message...
[10:15] user2: Another message...
[12:34] author: Current message requiring response...

Generate {num_variants} response variants. Be natural and context-aware.
```

**Response**:
```json
{
  "variants": [
    {
      "text": "Response variant 1",
      "confidence": 0.85
    },
    {
      "text": "Response variant 2",
      "confidence": 0.78
    }
  ]
}
```

**Метод "Смягчить"**:
```python
def soften_text(text: str) -> dict:
    """
    Перефразировать текст в вежливый тон

    Args:
        text: исходный текст

    Returns:
        dict: {"text": str, "confidence": float}
    """
```

**LLM Prompt для "Смягчить"**:
```
Rephrase the following text to be more polite and neutral while keeping the same meaning:

Original: {text}

Softened version:
```

---

### 5. Context Service API

Получение истории сообщений.

**Метод**:
```python
def get_context(
    message: Message,
    limit: int = 10,
    offset: int = 0
) -> List[Message]:
    """
    Получить контекст (историю) для сообщения

    Args:
        message: исходное сообщение
        limit: количество сообщений
        offset: смещение (для пагинации)

    Returns:
        List[Message]: список сообщений
    """
    return db.query(Message).filter(
        Message.channel_id == message.channel_id,
        Message.thread_id == message.thread_id,
        Message.platform_created_at <= message.platform_created_at
    ).order_by(
        Message.platform_created_at.desc()
    ).offset(offset).limit(limit).all()
```

---

### 6. DND Service API

Управление режимом "Не беспокоить".

**Методы**:
```python
def is_dnd_active(user_id: int) -> bool:
    """Проверить активен ли DND"""
    settings = get_user_settings(user_id)

    if not settings.dnd_enabled:
        return False

    # Проверить расписание
    return is_in_dnd_schedule(settings.dnd_schedule_json)

def toggle_dnd(user_id: int) -> bool:
    """Переключить DND (вкл/выкл)"""
    settings = get_user_settings(user_id)
    settings.dnd_enabled = not settings.dnd_enabled
    save_settings(settings)
    return settings.dnd_enabled

def update_dnd_schedule(user_id: int, schedule: dict) -> None:
    """Обновить расписание DND"""
    settings = get_user_settings(user_id)
    settings.dnd_schedule_json = json.dumps(schedule)
    save_settings(settings)
```

---

## Внешние API

### Discord Gateway (WebSocket)

**Подключение**:
```
wss://gateway.discord.gg/?v=9&encoding=json
```

**Authenticate (Op 2)**:
```json
{
  "op": 2,
  "d": {
    "token": "user_token_here",
    "properties": {
      "$os": "linux",
      "$browser": "Chrome",
      "$device": "desktop"
    },
    "presence": {
      "status": "online",
      "afk": false
    }
  }
}
```

**События (Op 0)**:
```json
{
  "op": 0,
  "t": "MESSAGE_CREATE",
  "d": {
    "id": "message_id",
    "channel_id": "channel_id",
    "guild_id": "guild_id",
    "author": {
      "id": "author_id",
      "username": "username"
    },
    "content": "message text",
    "timestamp": "2025-11-16T12:00:00.000000+00:00",
    "attachments": [],
    "embeds": []
  }
}
```

**Heartbeat (Op 1)**:
```json
{
  "op": 1,
  "d": null
}
```

Подробнее см. [DISCORD_INTEGRATION.md](DISCORD_INTEGRATION.md)

---

### Discord REST API

**Base URL**: `https://discord.com/api/v9`

**Headers**:
```
Authorization: {user_token}
Content-Type: application/json
```

**Endpoints**:
- `POST /channels/{channel_id}/messages` - отправка сообщения
- `PATCH /channels/{channel_id}/messages/{message_id}` - редактирование (v1.0+)
- `GET /channels/{channel_id}/messages` - получение истории
- `GET /guilds/{guild_id}/channels` - список каналов

---

### Telegram Bot API

**Base URL**: `https://api.telegram.org/bot{token}`

**Основные методы**:

#### getUpdates (Long Polling)
```
GET /bot{token}/getUpdates?offset={offset}&timeout=30
```

#### sendMessage
```
POST /bot{token}/sendMessage
{
  "chat_id": 123456,
  "text": "Message text",
  "reply_markup": {inline_keyboard},
  "disable_web_page_preview": true
}
```

#### editMessageText
```
POST /bot{token}/editMessageText
{
  "chat_id": 123456,
  "message_id": 789,
  "text": "Updated text",
  "reply_markup": {inline_keyboard}
}
```

#### answerCallbackQuery
```
POST /bot{token}/answerCallbackQuery
{
  "callback_query_id": "query_id",
  "text": "Action completed"
}
```

Подробнее см. [TELEGRAM_INTEGRATION.md](TELEGRAM_INTEGRATION.md)

---

### LLM API (v0.2+)

#### OpenAI API
```
POST https://api.openai.com/v1/chat/completions
Authorization: Bearer {api_key}
Content-Type: application/json

{
  "model": "gpt-4",
  "messages": [
    {"role": "system", "content": "You are a moderator..."},
    {"role": "user", "content": "Context + request"}
  ],
  "temperature": 0.7,
  "max_tokens": 500
}
```

#### Anthropic Claude API
```
POST https://api.anthropic.com/v1/messages
x-api-key: {api_key}
Content-Type: application/json

{
  "model": "claude-3-sonnet-20240229",
  "max_tokens": 500,
  "messages": [
    {"role": "user", "content": "Context + request"}
  ],
  "system": "You are a moderator..."
}
```

Подробнее см. [LLM_INTEGRATION.md](LLM_INTEGRATION.md)

---

## Команды Telegram Bot

### Пользовательские команды

#### /setup_discord
Настройка параметров подключения к Discord.

**Запрос**:
```
/setup_discord
```

**Ответ**:
```
Пожалуйста, отправьте ваш Discord User Token.
Как получить токен: [инструкция]
```

**Диалог**:
1. Пользователь отправляет токен
2. Бот сохраняет токен (зашифрованный)
3. Бот пытается подключиться к Gateway
4. Бот отправляет результат

---

#### /test_connection
Проверка подключения к Discord Gateway.

**Запрос**:
```
/test_connection
```

**Ответ**:
```
✅ Подключение к Discord активно
Подключено к 3 серверам
Последнее сообщение: 2 минуты назад
```

или

```
❌ Ошибка подключения
Причина: Invalid token
```

---

#### /discord_status
Статус подключения к Discord.

**Запрос**:
```
/discord_status
```

**Ответ**:
```
Discord Connection Status:
- Status: connected
- Session ID: abc123...
- Last heartbeat: 30s ago
- Servers: 3
- Channels in allowlist: 5
```

---

#### /status
Общий статус системы.

**Запрос**:
```
/status
```

**Ответ**:
```
System Status:
- Open tasks: 12
- Tasks today: 47
- DND: OFF
- Discord: ✅ Connected
- Database: ✅ OK
```

---

#### /dnd [on|off]
Управление режимом DND.

**Запросы**:
```
/dnd on
/dnd off
/dnd
```

**Ответы**:
```
DND mode: ON
Карточки не будут приходить до выключения.
```

```
Настройки DND:
[Включить] [Выключить]
[Настроить расписание]
```

---

#### /allow_channel {server_id} {channel_id}
Добавить канал в allowlist.

**Запрос**:
```
/allow_channel 111111111111111111 222222222222222222
```

**Ответ**:
```
✅ Канал #general добавлен в allowlist
Server: My Discord Server
```

---

#### /unallow_channel {channel_id}
Удалить канал из allowlist.

**Запрос**:
```
/unallow_channel 222222222222222222
```

**Ответ**:
```
✅ Канал #general удален из allowlist
```

---

#### /settings
Просмотр и изменение настроек.

**Запрос**:
```
/settings
```

**Ответ**:
```
Settings:
- DND: OFF
- Reminders: ON (v0.2+)
- Allowlist channels: 5

[Edit Settings]
```

---

#### /help
Справка по командам.

**Запрос**:
```
/help
```

**Ответ**:
```
Available Commands:

Setup & Status:
/setup_discord - Configure Discord connection
/test_connection - Test Discord connection
/discord_status - Discord connection status
/status - System status

DND:
/dnd [on|off] - Toggle DND mode

Allowlist (v0.2+):
/allow_channel {server_id} {channel_id} - Add channel
/unallow_channel {channel_id} - Remove channel

Other:
/settings - View/edit settings
/help - This message
```

---

#### /stats (v1.0+)
Статистика и метрики.

**Запрос**:
```
/stats
```

**Ответ**:
```
Statistics (last 7 days):
- Total tasks: 234
- Avg response time: 15 min
- Open tasks >24h: 3

Top channels:
1. #general - 87 messages
2. #support - 56 messages
3. #bugs - 34 messages
```

---

## Callback Query Handlers

Обработка нажатий на кнопки в карточках.

### reply_{task_id}
Начать ввод ответа на задачу.

**Callback Data**: `reply_123`

**Обработчик**:
```python
def handle_reply_button(task_id: int, user_id: int):
    # Установить состояние "ожидание ответа"
    set_user_state(user_id, f"awaiting_reply_{task_id}")

    # Запросить текст ответа
    send_message(user_id, "Введите ваш ответ:")
```

---

### more_{task_id}
Загрузить больше контекста.

**Callback Data**: `more_123`

**Обработчик**:
```python
def handle_more_button(task_id: int, message_id: int):
    # Получить следующий батч
    current_offset = get_current_offset(task_id)
    next_batch = get_context(task.source_message, offset=current_offset, limit=10)

    # Обновить карточку
    update_card(message_id, append_context=next_batch)
```

---

### confirm_{reply_id}
Подтвердить отправку ответа.

**Callback Data**: `confirm_456`

**Обработчик**:
```python
def handle_confirm_button(reply_id: int):
    reply = get_reply(reply_id)

    # Постинг
    result = post_reply(reply)

    if result.success:
        # Обновить статус
        reply.confirmed = True
        reply.posted_at = now()
        task.status = 'answered'
        save()

        # Обновить карточку
        update_card_status(task, "✅ Отправлено")
    else:
        # Показать ошибку
        update_card_status(task, f"❌ Ошибка: {result.error}")
```

---

### retry_{task_id}
Повторить отправку при ошибке.

**Callback Data**: `retry_123`

**Обработчик**:
```python
def handle_retry_button(task_id: int):
    task = get_task(task_id)
    last_reply = task.replies.last()

    # Повторная попытка
    result = post_reply(last_reply)

    # Обновить статус карточки
```

---

### toggle_dnd
Переключить DND режим.

**Callback Data**: `toggle_dnd`

**Обработчик**:
```python
def handle_toggle_dnd(user_id: int):
    new_state = toggle_dnd(user_id)

    send_message(user_id, f"DND mode: {'ON' if new_state else 'OFF'}")
```

---

### llm_variant_{variant_num} (v0.2+)
Выбрать вариант ответа от LLM.

**Callback Data**: `llm_variant_1`

**Обработчик**:
```python
def handle_llm_variant(task_id: int, variant_num: int):
    variant = get_llm_variant(task_id, variant_num)

    # Создать reply с текстом варианта
    reply = create_reply(task_id, variant.text, generated_by='llm')

    # Показать кнопку подтверждения
    show_confirmation(reply)
```

---

### llm_more (v0.2+)
Сгенерировать еще варианты.

**Callback Data**: `llm_more`

**Обработчик**:
```python
def handle_llm_more(task_id: int):
    # Генерация новых вариантов
    variants = generate_variants(task_id, num_variants=2)

    # Обновить карточку с новыми вариантами
    update_card_with_variants(task_id, variants)
```

---

### llm_soften (v0.2+)
Смягчить текст ответа.

**Callback Data**: `llm_soften`

**Обработчик**:
```python
def handle_llm_soften(task_id: int, original_text: str):
    # Перефразировать
    softened = soften_text(original_text)

    # Показать результат с кнопкой подтверждения
    show_softened_text(task_id, softened)
```

---

## Rate Limits и очереди (v0.2+)

### Discord Rate Limits

Discord API использует bucket-based rate limiting.

**Лимиты**:
- Глобальный: 50 запросов/сек
- Per-route: зависит от endpoint
- Per-channel messages: ~5 сообщений/5 сек

**Обработка**:
```python
class RateLimiter:
    def __init__(self):
        self.buckets = {}

    def acquire(self, route: str) -> bool:
        bucket = self.get_bucket(route)

        if bucket.is_rate_limited():
            # Ждем
            sleep(bucket.reset_after)

        bucket.consume()
        return True
```

### Очереди (BullMQ / Celery)

**Типы задач**:
- `ingest.discord` - обработка Discord событий
- `ingest.telegram` - обработка Telegram сообщений
- `post.discord` - постинг в Discord
- `post.telegram` - постинг в Telegram
- `llm.generate` - генерация вариантов (v0.2+)

**Приоритеты**:
- High: ответы модератора
- Normal: инжест сообщений
- Low: генерация вариантов

---

## Форматы данных

### Карточка (plain text)

```
Discord • My Server • #general • @username • 12:34:56

Context:
[12:30] user1: Previous message
[12:32] user2: Another message
[12:34] username: Current message text here

Reply: (none)
Status: open

[Ответить] [Показать больше] [DND]
```

### Ошибки

Стандартный формат ошибок:

```json
{
  "error": {
    "code": "DISCORD_POST_FAILED",
    "message": "Failed to post message to Discord",
    "details": {
      "channel_id": "123",
      "reason": "Missing Access"
    }
  }
}
```

**Коды ошибок**:
- `DISCORD_CONNECTION_FAILED` - не удалось подключиться к Gateway
- `DISCORD_POST_FAILED` - ошибка постинга в Discord
- `TELEGRAM_POST_FAILED` - ошибка постинга в Telegram
- `INVALID_TOKEN` - невалидный токен
- `CHANNEL_NOT_ALLOWED` - канал не в allowlist
- `LLM_TIMEOUT` - таймаут LLM
- `DATABASE_ERROR` - ошибка БД

---

## Webhooks

### Telegram Webhook (опционально)

Вместо long polling можно использовать webhook.

**Setup**:
```
POST https://api.telegram.org/bot{token}/setWebhook
{
  "url": "https://your-domain.com/webhook/telegram",
  "allowed_updates": ["message", "callback_query"]
}
```

**Endpoint**:
```
POST /webhook/telegram
```

**Payload**: Telegram Update object

---

## Мониторинг API

### Health Check

```
GET /health

Response:
{
  "status": "ok",
  "discord": "connected",
  "database": "ok",
  "timestamp": "2025-11-16T12:00:00Z"
}
```

### Metrics (опционально, v1.0+)

```
GET /metrics

Response (Prometheus format):
moderator_tasks_total{status="open"} 12
moderator_tasks_total{status="answered"} 235
moderator_messages_processed_total{platform="discord"} 1523
moderator_messages_processed_total{platform="telegram"} 89
```
