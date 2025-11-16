# Интеграция с Telegram

## Обзор

Система использует официальный Telegram Bot API для:
1. Приема личных сообщений модератору
2. Отправки карточек задач
3. Приема ответов модератора
4. Управления настройками через команды

## Создание бота

### 1. Регистрация бота через BotFather

1. Найти [@BotFather](https://t.me/botfather) в Telegram
2. Отправить `/newbot`
3. Указать имя бота: `Moderator Console`
4. Указать username: `moderator_console_bot` (должен заканчиваться на `bot`)
5. Получить Bot Token: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`

### 2. Настройка бота

```
/setdescription - Moderator console for Discord and Telegram
/setabouttext - Unified moderation console
/setcommands - настроить список команд
```

**Список команд**:
```
setup_discord - Configure Discord connection
test_connection - Test Discord connection
discord_status - Discord connection status
status - System status
dnd - Toggle DND mode
allow_channel - Add channel to allowlist
unallow_channel - Remove channel from allowlist
settings - View/edit settings
help - Show help
```

### 3. Отключение Privacy Mode (опционально)

Если бот будет в группах (не в MVP):
```
/setprivacy - Disabled
```

## Получение обновлений

### Метод 1: Long Polling (рекомендуется для MVP)

**Endpoint**: `https://api.telegram.org/bot{token}/getUpdates`

**Parameters**:
- `offset` - ID последнего обработанного update + 1
- `timeout` - long polling timeout (сек), рекомендуется 30
- `allowed_updates` - массив типов: `["message", "callback_query"]`

**Example**:
```
GET /bot123456:ABC/getUpdates?offset=100&timeout=30&allowed_updates=["message","callback_query"]
```

**Response**:
```json
{
  "ok": true,
  "result": [
    {
      "update_id": 100,
      "message": {
        "message_id": 123,
        "from": {
          "id": 987654321,
          "is_bot": false,
          "first_name": "John",
          "username": "john_doe"
        },
        "chat": {
          "id": 987654321,
          "type": "private"
        },
        "date": 1700000000,
        "text": "Hello bot"
      }
    }
  ]
}
```

**Цикл обработки**:
```python
import requests

BOT_TOKEN = "123456:ABC"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
offset = 0

while True:
    response = requests.get(
        f"{BASE_URL}/getUpdates",
        params={
            "offset": offset,
            "timeout": 30,
            "allowed_updates": ["message", "callback_query"]
        }
    )
    data = response.json()

    if data['ok']:
        for update in data['result']:
            process_update(update)
            offset = update['update_id'] + 1
```

### Метод 2: Webhook (опционально, для production)

**Setup**:
```
POST /bot{token}/setWebhook
{
  "url": "https://your-domain.com/webhook/telegram",
  "allowed_updates": ["message", "callback_query"]
}
```

**Endpoint** на вашем сервере:
```python
from flask import Flask, request

app = Flask(__name__)

@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    update = request.json
    process_update(update)
    return '', 200
```

**Требования**:
- HTTPS
- Валидный SSL сертификат
- Порт 443, 80, 88 или 8443

**Удаление webhook** (для возврата к long polling):
```
POST /bot{token}/deleteWebhook
```

## Обработка входящих сообщений

### Фильтрация по типу чата

Принимаем только личные сообщения (DM):

```python
def process_update(update):
    if 'message' in update:
        message = update['message']
        chat = message['chat']

        if chat['type'] != 'private':
            return  # Игнорируем группы

        handle_private_message(message)
```

### Структура Message

```json
{
  "message_id": 123,
  "from": {
    "id": 987654321,
    "is_bot": false,
    "first_name": "John",
    "username": "john_doe"
  },
  "chat": {
    "id": 987654321,
    "type": "private"
  },
  "date": 1700000000,
  "text": "Message text",
  "photo": [
    {
      "file_id": "AgACAgIAAxkBAAI...",
      "file_unique_id": "AQADh...",
      "file_size": 12345,
      "width": 800,
      "height": 600
    }
  ]
}
```

### Обработка текста

```python
def handle_private_message(message):
    user_id = message['from']['id']
    text = message.get('text', '')

    # Проверка авторизации
    if user_id != MODERATOR_TG_USER_ID:
        send_message(user_id, "Unauthorized")
        return

    # Обработка команд
    if text.startswith('/'):
        handle_command(message)
    else:
        # Проверка состояния (ожидание ответа на задачу?)
        state = get_user_state(user_id)

        if state and state.startswith('awaiting_reply_'):
            task_id = int(state.split('_')[-1])
            handle_reply_text(task_id, text)
        else:
            # Обычное входящее сообщение
            create_task_from_telegram(message)
```

### Обработка изображений

```python
if 'photo' in message:
    # Telegram присылает массив размеров, берем самый большой
    photo = message['photo'][-1]
    file_id = photo['file_id']

    # Получить URL файла
    file_info = get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info['file_path']}"

    # Сохранить в attachments
    save_attachment(message_id, 'image', file_url)
```

## Отправка сообщений

### sendMessage

**Endpoint**: `POST /bot{token}/sendMessage`

**Parameters**:
- `chat_id` (required) - ID чата
- `text` (required) - текст сообщения (max 4096 chars)
- `reply_to_message_id` (optional) - ID сообщения для reply
- `reply_markup` (optional) - клавиатура
- `disable_web_page_preview` (optional) - отключить превью ссылок (true)

**Example**:
```json
{
  "chat_id": 987654321,
  "text": "Hello from bot!",
  "disable_web_page_preview": true
}
```

**Response**:
```json
{
  "ok": true,
  "result": {
    "message_id": 124,
    "from": {
      "id": 123456789,
      "is_bot": true,
      "first_name": "Moderator Console"
    },
    "chat": {
      "id": 987654321,
      "type": "private"
    },
    "date": 1700000100,
    "text": "Hello from bot!"
  }
}
```

### Inline Keyboard

Кнопки под сообщением:

```python
keyboard = {
    "inline_keyboard": [
        [
            {"text": "Ответить", "callback_data": "reply_123"},
            {"text": "Показать больше", "callback_data": "more_123"}
        ],
        [
            {"text": "DND", "callback_data": "toggle_dnd"}
        ]
    ]
}

send_message(
    chat_id=987654321,
    text="Card text...",
    reply_markup=keyboard
)
```

**Ограничения**:
- callback_data: max 64 bytes
- Количество кнопок: макс 100 в сумме

### editMessageText

Обновление текста сообщения:

```json
{
  "chat_id": 987654321,
  "message_id": 124,
  "text": "Updated text",
  "reply_markup": {...}
}
```

### answerCallbackQuery

Ответ на нажатие кнопки:

```json
{
  "callback_query_id": "query_id_from_update",
  "text": "Action completed!",
  "show_alert": false
}
```

**show_alert**:
- `false` - всплывающее уведомление (default)
- `true` - модальное окно

## Обработка Callback Queries

### Структура CallbackQuery

```json
{
  "update_id": 101,
  "callback_query": {
    "id": "query_id_123",
    "from": {
      "id": 987654321,
      "first_name": "John"
    },
    "message": {
      "message_id": 124,
      "chat": {
        "id": 987654321
      },
      "text": "Card text..."
    },
    "data": "reply_123"
  }
}
```

### Обработчик

```python
def process_update(update):
    if 'callback_query' in update:
        query = update['callback_query']
        data = query['data']
        user_id = query['from']['id']
        message_id = query['message']['message_id']
        chat_id = query['message']['chat']['id']

        # Проверка авторизации
        if user_id != MODERATOR_TG_USER_ID:
            answer_callback_query(query['id'], "Unauthorized")
            return

        # Роутинг по callback_data
        if data.startswith('reply_'):
            task_id = int(data.split('_')[1])
            handle_reply_button(task_id, user_id)
        elif data.startswith('more_'):
            task_id = int(data.split('_')[1])
            handle_more_button(task_id, message_id, chat_id)
        elif data == 'toggle_dnd':
            handle_dnd_toggle(user_id)
        elif data.startswith('confirm_'):
            reply_id = int(data.split('_')[1])
            handle_confirm(reply_id, message_id, chat_id)

        # Ответить на query
        answer_callback_query(query['id'], "OK")
```

## Команды бота

### Регистрация команд

Через BotFather:
```
/setcommands
```

Или через API:
```
POST /bot{token}/setMyCommands
{
  "commands": [
    {"command": "setup_discord", "description": "Configure Discord connection"},
    {"command": "status", "description": "System status"},
    {"command": "dnd", "description": "Toggle DND mode"},
    {"command": "help", "description": "Show help"}
  ]
}
```

### Обработка команд

```python
def handle_command(message):
    text = message['text']
    user_id = message['from']['id']

    if text == '/start':
        send_message(user_id, "Welcome to Moderator Console!\nUse /help for commands.")
    elif text == '/help':
        send_help(user_id)
    elif text == '/status':
        send_status(user_id)
    elif text.startswith('/dnd'):
        parts = text.split()
        if len(parts) > 1:
            handle_dnd_command(user_id, parts[1])  # /dnd on|off
        else:
            show_dnd_settings(user_id)
    elif text == '/setup_discord':
        start_discord_setup(user_id)
    # ... другие команды
```

## Форматирование текста

Telegram поддерживает несколько режимов:
- HTML
- Markdown
- MarkdownV2

**Для plain text**: не указывать parse_mode (или использовать `disable_web_page_preview: true` для ссылок без превью).

**Экранирование спецсимволов**:

Если используется Markdown, нужно экранировать: `_`, `*`, `[`, `]`, `(`, `)`, `~`, `` ` ``, `>`, `#`, `+`, `-`, `=`, `|`, `{`, `}`, `.`, `!`

Для plain text экранирование не требуется.

## Работа с файлами

### Получение файла

```python
def get_file(file_id):
    response = requests.get(f"{BASE_URL}/getFile", params={"file_id": file_id})
    return response.json()['result']

# Example
file_info = get_file(photo['file_id'])
# file_info = {"file_id": "...", "file_path": "photos/file_123.jpg", "file_size": 12345}

file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info['file_path']}"
```

### Отправка изображения (если нужно переслать из Telegram в Discord)

```python
def send_photo(chat_id, photo_url):
    requests.post(
        f"{BASE_URL}/sendPhoto",
        json={
            "chat_id": chat_id,
            "photo": photo_url,
            "caption": "Image description"
        }
    )
```

## Rate Limits

### Telegram Bot API лимиты

- **Глобальный**: 30 сообщений/сек
- **На один чат**: 1 сообщение/сек (для групп)
- **Для приватных чатов**: более мягкие ограничения

### Обработка ошибок

**Error 429 (Too Many Requests)**:
```json
{
  "ok": false,
  "error_code": 429,
  "description": "Too Many Requests: retry after 5",
  "parameters": {
    "retry_after": 5
  }
}
```

**Решение**: ждать `retry_after` секунд.

## Безопасность

### Проверка авторизации

```python
MODERATOR_TG_USER_ID = 987654321  # Из переменной окружения

def is_authorized(user_id):
    return user_id == MODERATOR_TG_USER_ID

def process_update(update):
    if 'message' in update:
        user_id = update['message']['from']['id']
        if not is_authorized(user_id):
            send_message(user_id, "You are not authorized to use this bot.")
            return
    # ... обработка
```

### Webhook Secret Token (для webhook)

```python
@app.route('/webhook/telegram', methods=['POST'])
def telegram_webhook():
    # Проверка секретного заголовка
    secret = request.headers.get('X-Telegram-Bot-Api-Secret-Token')
    if secret != os.getenv('TELEGRAM_WEBHOOK_SECRET'):
        return '', 403

    update = request.json
    process_update(update)
    return '', 200
```

Установка при setWebhook:
```json
{
  "url": "https://your-domain.com/webhook/telegram",
  "secret_token": "your_random_secret_here"
}
```

## Пример реализации (Python)

### Полный цикл с long polling

```python
import requests
import time
import os

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
MODERATOR_ID = int(os.getenv('MODERATOR_TG_USER_ID'))
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def get_updates(offset=0, timeout=30):
    response = requests.get(
        f"{BASE_URL}/getUpdates",
        params={
            "offset": offset,
            "timeout": timeout,
            "allowed_updates": ["message", "callback_query"]
        },
        timeout=timeout + 5
    )
    return response.json()

def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True
    }
    if reply_markup:
        data['reply_markup'] = reply_markup

    response = requests.post(f"{BASE_URL}/sendMessage", json=data)
    return response.json()

def answer_callback_query(query_id, text="OK"):
    requests.post(
        f"{BASE_URL}/answerCallbackQuery",
        json={"callback_query_id": query_id, "text": text}
    )

def process_update(update):
    if 'message' in update:
        message = update['message']
        user_id = message['from']['id']

        if user_id != MODERATOR_ID:
            send_message(user_id, "Unauthorized")
            return

        if message['chat']['type'] != 'private':
            return

        text = message.get('text', '')

        if text.startswith('/'):
            handle_command(message)
        else:
            handle_text_message(message)

    elif 'callback_query' in update:
        query = update['callback_query']
        if query['from']['id'] != MODERATOR_ID:
            answer_callback_query(query['id'], "Unauthorized")
            return

        handle_callback(query)
        answer_callback_query(query['id'])

def handle_command(message):
    text = message['text']
    user_id = message['from']['id']

    if text == '/start' or text == '/help':
        send_message(user_id, "Help text...")
    elif text == '/status':
        send_message(user_id, "Status: OK")
    # ... другие команды

def handle_text_message(message):
    # Создать задачу из входящего сообщения
    create_task_from_telegram(message)

def handle_callback(query):
    data = query['data']
    message_id = query['message']['message_id']
    chat_id = query['message']['chat']['id']

    if data.startswith('reply_'):
        task_id = int(data.split('_')[1])
        # Установить состояние ожидания ответа
        set_user_state(MODERATOR_ID, f"awaiting_reply_{task_id}")
        send_message(chat_id, "Enter your reply:")

    elif data == 'toggle_dnd':
        toggle_dnd(MODERATOR_ID)
        send_message(chat_id, "DND toggled")

    # ... другие callback

def main():
    offset = 0
    print("Bot started")

    while True:
        try:
            data = get_updates(offset)

            if data['ok']:
                for update in data['result']:
                    process_update(update)
                    offset = update['update_id'] + 1
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main()
```

## Troubleshooting

### "Unauthorized" (401)

**Причина**: неверный Bot Token

**Решение**: проверить токен в переменных окружения

### "Bad Request: chat not found"

**Причина**: неверный chat_id или бот не может написать пользователю

**Решение**: пользователь должен первым написать боту (`/start`)

### "Bad Request: message is not modified"

**Причина**: пытаетесь обновить сообщение тем же текстом

**Решение**: игнорировать ошибку или проверять изменения

### Webhook не работает

**Причины**:
- Невалидный SSL
- Неправильный URL
- Порт не 443/80/88/8443

**Решение**: проверить логи, использовать getWebhookInfo

```
GET /bot{token}/getWebhookInfo
```

## Ограничения

1. **Размер сообщения**: 4096 символов
2. **Размер файла**: 50 MB (для ботов), 20 MB (для фото)
3. **callback_data**: 64 байта
4. **Rate limits**: см. выше

## Лучшие практики

1. **Использовать long polling для dev**, webhook для prod
2. **Всегда отвечать на callback queries** (answerCallbackQuery)
3. **Обрабатывать ошибки** и логировать
4. **Использовать disable_web_page_preview** для plain text
5. **Проверять авторизацию** для каждого update

## Заключение

Интеграция с Telegram - официальная и стабильная, использует Bot API без нарушения ToS.
