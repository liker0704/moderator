# Интеграция с Discord

## Обзор

Система использует **прямое подключение пользовательского аккаунта** к Discord Gateway для получения сообщений. Это **неофициальный метод**, нарушающий Discord Terms of Service.

⚠️ **ВАЖНО**: Использование на свой риск. Возможна блокировка аккаунта Discord.

## Получение User Token

### Метод 1: Через DevTools браузера

1. Открыть Discord Web (https://discord.com/app)
2. Войти в аккаунт
3. Открыть DevTools (F12)
4. Перейти в Console
5. Выполнить код:

```javascript
(webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m).find(m=>m?.exports?.default?.getToken!==void 0).exports.default.getToken()
```

6. Скопировать токен

### Метод 2: Через Network Inspector

1. Открыть Discord Web
2. DevTools → Network
3. Фильтр: XHR/Fetch
4. Отправить любое сообщение в Discord
5. Найти запрос к `https://discord.com/api/v9/...`
6. Скопировать значение заголовка `Authorization`

**Формат токена**: `EXAMPLE.TOKEN.HERE_DO_NOT_USE_REAL_TOKEN` (пример формата)

## Super Properties

Super Properties - технические параметры клиента Discord, необходимые для аутентификации.

### Получение

Через DevTools Console:

```javascript
JSON.parse(atob(
  (webpackChunkdiscord_app.push([[''],{},e=>{m=[];for(let c in e.c)m.push(e.c[c])}]),m)
  .find(m=>m?.exports?.default?.getSuperPropertiesBase64!==void 0)
  .exports.default.getSuperPropertiesBase64()
))
```

### Пример Super Properties

```json
{
  "os": "Windows",
  "browser": "Chrome",
  "device": "",
  "system_locale": "en-US",
  "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
  "browser_version": "120.0.0.0",
  "os_version": "10",
  "referrer": "",
  "referring_domain": "",
  "referrer_current": "",
  "referring_domain_current": "",
  "release_channel": "stable",
  "client_build_number": 261053,
  "client_event_source": null
}
```

**Важные поля**:
- `client_build_number` - обновляется при обновлении Discord
- `os`, `browser` - должны соответствовать реальному окружению

## Discord Gateway

### Подключение к WebSocket

**URL**: `wss://gateway.discord.gg/?v=9&encoding=json`

**Версия протокола**: 9 (актуально на 2025)

### Последовательность подключения

#### 1. Hello (Op 10)

После подключения Discord отправляет Hello:

```json
{
  "op": 10,
  "d": {
    "heartbeat_interval": 41250
  }
}
```

#### 2. Identify (Op 2)

Отправляем аутентификацию:

```json
{
  "op": 2,
  "d": {
    "token": "YOUR_USER_TOKEN",
    "properties": {
      "$os": "Windows",
      "$browser": "Chrome",
      "$device": "desktop"
    },
    "compress": false,
    "presence": {
      "status": "online",
      "since": null,
      "activities": [],
      "afk": false
    },
    "intents": 32767
  }
}
```

**Intents** (32767 = все биты):
- GUILDS (1 << 0)
- GUILD_MESSAGES (1 << 9)
- DIRECT_MESSAGES (1 << 12)
- MESSAGE_CONTENT (1 << 15) ⚠️ Требуется для чтения контента

#### 3. Ready (Op 0, t: READY)

Discord отвечает Ready:

```json
{
  "op": 0,
  "t": "READY",
  "d": {
    "v": 9,
    "user": {...},
    "guilds": [...],
    "session_id": "abc123...",
    ...
  }
}
```

Сохраняем `session_id` для reconnection.

#### 4. Heartbeat (Op 1)

Каждые `heartbeat_interval` мс отправляем:

```json
{
  "op": 1,
  "d": null
}
```

Discord отвечает:

```json
{
  "op": 11
}
```

## Прием событий

### MESSAGE_CREATE

Основное событие для получения сообщений:

```json
{
  "op": 0,
  "t": "MESSAGE_CREATE",
  "s": 123,
  "d": {
    "id": "1234567890123456789",
    "channel_id": "9876543210987654321",
    "guild_id": "1111111111111111111",
    "author": {
      "id": "222222222222222222",
      "username": "username",
      "discriminator": "1234",
      "avatar": "hash"
    },
    "content": "Message text",
    "timestamp": "2025-11-16T12:00:00.000000+00:00",
    "attachments": [
      {
        "id": "333333333333333333",
        "filename": "image.png",
        "url": "https://cdn.discordapp.com/attachments/.../image.png",
        "proxy_url": "...",
        "size": 12345,
        "width": 800,
        "height": 600
      }
    ],
    "embeds": [],
    "mentions": [],
    "mention_everyone": false,
    "pinned": false,
    "type": 0
  }
}
```

**Фильтрация**:
1. Проверить `guild_id` + `channel_id` по allowlist
2. Опционально проверить `thread_id` (если сообщение в треде)
3. Сохранить в БД

### Треды

Сообщения в тредах:

```json
{
  "d": {
    "id": "...",
    "channel_id": "thread_channel_id", // ID треда
    "guild_id": "guild_id",
    ...
  }
}
```

Для получения информации о треде использовать REST API.

## Отправка сообщений

### REST API

**Endpoint**: `POST https://discord.com/api/v9/channels/{channel_id}/messages`

**Headers**:
```
Authorization: YOUR_USER_TOKEN
Content-Type: application/json
User-Agent: Mozilla/5.0 (compatible)
```

**Body**:
```json
{
  "content": "Message text (plain text only)",
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
  "author": {...},
  "content": "Message text",
  "timestamp": "2025-11-16T12:00:00.000000+00:00"
}
```

### Отправка в тред

Используется тот же endpoint, где `channel_id` = `thread_id`.

### Errors

**Коды ошибок**:
- 401 Unauthorized - неверный токен
- 403 Forbidden - нет доступа к каналу
- 404 Not Found - канал не существует
- 429 Too Many Requests - rate limit

**Rate Limit Response**:
```json
{
  "message": "You are being rate limited.",
  "retry_after": 0.250,
  "global": false
}
```

## Reconnection

### Resume (Op 6)

При обрыве соединения использовать Resume вместо Identify:

```json
{
  "op": 6,
  "d": {
    "token": "YOUR_USER_TOKEN",
    "session_id": "saved_session_id",
    "seq": last_sequence_number
  }
}
```

**Sequence number** (`s`) - из последнего полученного события.

### Стратегия reconnect

1. Попытка Resume (если есть session_id)
2. Если Resume failed → полный Identify
3. Exponential backoff при ошибках:
   - 1-я попытка: сразу
   - 2-я: 2 сек
   - 3-я: 4 сек
   - 4-я: 8 сек
   - и т.д., макс 60 сек

## Обработка Rate Limits

### Global Rate Limit

50 запросов в секунду (на весь API).

### Per-Route Rate Limit

Зависит от endpoint. Например:
- POST /channels/{id}/messages: ~5 req/5 sec

### X-RateLimit Headers

```
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 4
X-RateLimit-Reset: 1700000000.123
X-RateLimit-Reset-After: 5.000
X-RateLimit-Bucket: abc123...
```

### Bucket System (v0.2+)

Каждый route имеет свой bucket:

```python
buckets = {
  'POST /channels/{id}/messages': RateLimiter(limit=5, window=5),
  'GET /channels/{id}/messages': RateLimiter(limit=50, window=1),
  ...
}

def post_message(channel_id, content):
    bucket = buckets[f'POST /channels/{channel_id}/messages']
    bucket.acquire()  # Ждет если нужно
    return api_call(...)
```

## Получение истории

### GET /channels/{channel_id}/messages

**Query Parameters**:
- `limit` (1-100): количество сообщений
- `before` (message_id): сообщения ДО этого ID
- `after` (message_id): сообщения ПОСЛЕ этого ID

**Example**:
```
GET /channels/123/messages?limit=50&before=456
```

**Response**: массив сообщений (от новых к старым)

## Эмуляция человеческого поведения

Для минимизации риска блокировки:

1. **Delays между действиями**: 1-3 сек между сообщениями
2. **Случайные интервалы**: не отправлять каждые ровно N секунд
3. **Typing indicator** (опционально):
   ```
   POST /channels/{id}/typing
   ```
   Перед отправкой сообщения

4. **User-Agent**: использовать реальный браузерный UA
5. **Не спамить**: не отправлять массово сразу

## Мониторинг подключения

### Heartbeat ACK

Если не получен ACK (Op 11) в течение `heartbeat_interval + 5 sec`, соединение мертво.

### Reconnect (Op 7)

Discord может послать:

```json
{
  "op": 7,
  "d": null
}
```

Нужно немедленно reconnect с Resume.

### Invalid Session (Op 9)

```json
{
  "op": 9,
  "d": false
}
```

`false` = session не возобновляема, нужен полный Identify.

## Пример кода (Python)

```python
import websocket
import json
import time

class DiscordGateway:
    def __init__(self, token):
        self.token = token
        self.ws = None
        self.session_id = None
        self.seq = None
        self.heartbeat_interval = None

    def connect(self):
        self.ws = websocket.WebSocketApp(
            "wss://gateway.discord.gg/?v=9&encoding=json",
            on_message=self.on_message,
            on_open=self.on_open,
            on_error=self.on_error,
            on_close=self.on_close
        )
        self.ws.run_forever()

    def on_open(self, ws):
        print("Connected to Discord Gateway")

    def on_message(self, ws, message):
        data = json.loads(message)
        op = data['op']
        d = data.get('d')
        t = data.get('t')
        self.seq = data.get('s', self.seq)

        if op == 10:  # Hello
            self.heartbeat_interval = d['heartbeat_interval']
            self.send_identify()
            self.start_heartbeat()
        elif op == 0:  # Dispatch
            if t == 'READY':
                self.session_id = d['session_id']
                print(f"Ready! Session: {self.session_id}")
            elif t == 'MESSAGE_CREATE':
                self.handle_message(d)

    def send_identify(self):
        payload = {
            "op": 2,
            "d": {
                "token": self.token,
                "properties": {
                    "$os": "linux",
                    "$browser": "Chrome",
                    "$device": "desktop"
                },
                "intents": 32767
            }
        }
        self.ws.send(json.dumps(payload))

    def start_heartbeat(self):
        def heartbeat():
            while True:
                time.sleep(self.heartbeat_interval / 1000)
                self.ws.send(json.dumps({"op": 1, "d": self.seq}))

        import threading
        thread = threading.Thread(target=heartbeat, daemon=True)
        thread.start()

    def handle_message(self, data):
        # Фильтрация по allowlist
        if is_allowed(data['channel_id'], data.get('guild_id')):
            store_message(data)
            create_task(data)

    def on_error(self, ws, error):
        print(f"Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("Connection closed, reconnecting...")
        time.sleep(2)
        self.connect()
```

## Безопасность

### Хранение токена

1. **Шифрование**: AES-256 в БД
2. **Переменные окружения**: не в коде
3. **Rotation**: менять токен при подозрении на компрометацию

### Защита от блокировки

1. **Не использовать множество аккаунтов** с одного IP
2. **Не массовые операции**: избегать спама
3. **Резервные аккаунты**: иметь 1-2 запасных
4. **Мониторинг**: отслеживать изменения в протоколе Discord

### Изменения в протоколе

Discord регулярно обновляет:
- `client_build_number` в super properties
- Версию Gateway API
- Intents requirements

**Решение**: периодически обновлять параметры вручную.

## Troubleshooting

### Ошибка: "Invalid Session"

**Причины**:
- Неверный token
- Устаревший session_id при Resume
- Изменился client_build_number

**Решение**: полный Identify заново

### Ошибка: "Missing Access"

**Причины**:
- Нет доступа к каналу (приватный канал)
- Пользователь не на сервере

**Решение**: проверить права доступа аккаунта

### Connection timeout

**Причины**:
- Проблемы с сетью
- Discord Gateway down

**Решение**: reconnect с exponential backoff

### Rate Limited

**Решение**: ждать `retry_after` секунд

## Ограничения

1. **User Token нестабилен**: может инвалидироваться
2. **Нарушение ToS**: риск блокировки
3. **Нет официальной поддержки**: при проблемах некуда обращаться
4. **Изменения протокола**: требуется ручное обновление

## Альтернативы (не рекомендуются для этого проекта)

1. **Bot Token**: не видит все сообщения, требует MESSAGE_CONTENT intent
2. **OAuth2**: не подходит для автоматизации
3. **Selfbot библиотеки**: устаревшие, против ToS

## Заключение

Интеграция с Discord через User Token - единственный способ получать все сообщения для данного проекта, но он нарушает ToS и требует постоянного мониторинга и обновлений.
