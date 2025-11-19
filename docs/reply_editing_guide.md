# Reply Editing Guide

Этот документ описывает новые методы для редактирования replies в системе модерации.

## Новые методы в ReplyDAO

### 1. `can_edit_reply()` - Проверка возможности редактирования

Проверяет, может ли пользователь редактировать конкретный reply.

#### Проверки:
1. Reply существует
2. Reply уже опубликован (posted_at IS NOT NULL)
3. Пользователь владеет reply (через task.assignee_user_id)
4. Не превышен лимит времени (по умолчанию 48 часов с момента публикации)

#### Сигнатура:
```python
async def can_edit_reply(
    conn: asyncpg.Connection,
    reply_id: int,
    user_id: int,
    time_limit_hours: int = 48
) -> Dict[str, Any]
```

#### Возвращаемое значение:
```python
{
    'can_edit': bool,              # Может ли редактировать
    'reason': str,                 # Причина (если can_edit=False)
    'reply': Dict,                 # Данные reply (если существует)
    'hours_since_posted': float    # Часы с момента публикации
}
```

#### Возможные причины отказа:
- `'not_found'` - Reply не существует
- `'not_posted'` - Reply еще не опубликован
- `'time_expired'` - Превышен лимит времени на редактирование
- `'permission_denied'` - Пользователь не владеет reply

#### Пример использования:
```python
async with pool.acquire() as conn:
    # Проверка возможности редактирования
    result = await ReplyDAO.can_edit_reply(
        conn=conn,
        reply_id=123,
        user_id=1,
        time_limit_hours=48
    )

    if result['can_edit']:
        print(f"✓ Можно редактировать (прошло {result['hours_since_posted']:.1f} часов)")
    else:
        print(f"✗ Нельзя редактировать: {result['reason']}")
        if result['reason'] == 'time_expired':
            print(f"  Прошло {result['hours_since_posted']:.1f} часов (лимит: 48)")
```

---

### 2. `create_edited_reply()` - Создание отредактированной версии

Создает новую запись reply как редакцию оригинала.

#### Что делает:
1. Валидирует возможность редактирования (использует `can_edit_reply`)
2. Создает новую запись в таблице replies с `edit_of = original_reply_id`
3. Создает audit log с событием `'reply.edit_started'`
4. **НЕ публикует** на платформу - это делает вызывающий код

#### Сигнатура:
```python
async def create_edited_reply(
    conn: asyncpg.Connection,
    original_reply_id: int,
    new_content: str,
    user_id: int
) -> int
```

#### Возвращает:
- `int` - ID новой отредактированной reply

#### Выбрасывает:
- `ValueError` - если валидация не прошла (с информативным сообщением)

#### Пример использования:
```python
async with pool.acquire() as conn:
    try:
        # Создание отредактированной версии
        new_reply_id = await ReplyDAO.create_edited_reply(
            conn=conn,
            original_reply_id=123,
            new_content='Исправленный текст ответа',
            user_id=1
        )

        print(f"✓ Создана новая версия reply: {new_reply_id}")

        # Теперь нужно опубликовать на платформу
        # (это делает вызывающий код)

    except ValueError as e:
        print(f"✗ Ошибка: {e}")
        # Пример ошибок:
        # - "Reply 123 does not exist"
        # - "Reply 123 has not been posted yet"
        # - "User 1 does not own reply 123"
        # - "Reply 123 edit time limit exceeded (50.3 hours since posting)"
```

---

## Audit Logging

При создании отредактированной reply автоматически создается audit log с:

### Event kind:
- `'reply.edit_started'`

### Payload (JSON):
```json
{
    "original_reply_id": 123,
    "new_reply_id": 456,
    "task_id": 789,
    "user_id": 1,
    "platform": "discord",
    "channel_id": "123456789",
    "original_content_length": 150,
    "new_content_length": 165,
    "hours_since_posted": 12.5
}
```

---

## Полный workflow редактирования

```python
async def edit_and_post_reply(reply_id: int, new_content: str, user_id: int):
    """Полный workflow редактирования и публикации reply"""

    async with pool.acquire() as conn:
        # 1. Проверка возможности редактирования
        check = await ReplyDAO.can_edit_reply(
            conn=conn,
            reply_id=reply_id,
            user_id=user_id
        )

        if not check['can_edit']:
            return {
                'success': False,
                'error': f"Cannot edit: {check['reason']}"
            }

        # 2. Создание отредактированной версии
        try:
            new_reply_id = await ReplyDAO.create_edited_reply(
                conn=conn,
                original_reply_id=reply_id,
                new_content=new_content,
                user_id=user_id
            )
        except ValueError as e:
            return {
                'success': False,
                'error': str(e)
            }

        # 3. Публикация на платформу
        original_reply = check['reply']
        platform = original_reply['platform']

        if platform == 'discord':
            # Отредактировать сообщение в Discord
            result = await edit_discord_message(
                channel_id=original_reply['channel_id'],
                message_id=json.loads(original_reply['platform_ref'])['message_id'],
                new_content=new_content
            )
        elif platform == 'telegram':
            # Отредактировать сообщение в Telegram
            result = await edit_telegram_message(...)

        # 4. Отметить новую reply как подтвержденную и опубликованную
        if result['success']:
            await ReplyDAO.mark_reply_confirmed(conn, new_reply_id)
            platform_ref = json.dumps({
                'platform': platform,
                'message_id': result['message_id'],
                'channel_id': original_reply['channel_id'],
                'edit_of': reply_id
            })
            await ReplyDAO.mark_reply_posted(conn, new_reply_id, platform_ref)

            # 5. Audit log для успешной публикации
            await AuditDAO.log_event(
                conn=conn,
                kind='reply.edit_posted',
                payload_json=json.dumps({
                    'original_reply_id': reply_id,
                    'new_reply_id': new_reply_id,
                    'platform': platform,
                    'user_id': user_id
                }),
                user_id=user_id
            )

        return {
            'success': result['success'],
            'new_reply_id': new_reply_id
        }
```

---

## Структура базы данных

### Таблица `replies`:
```sql
CREATE TABLE replies (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES tasks(id),
    content TEXT NOT NULL,
    generated_by VARCHAR(50) NOT NULL DEFAULT 'human',
    llm_confidence FLOAT,
    confirmed BOOLEAN NOT NULL DEFAULT false,
    posted_at TIMESTAMP,
    platform_ref TEXT,
    edit_of BIGINT REFERENCES replies(id),  -- ← Ссылка на оригинальный reply
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### История редактирования:
Используйте существующий метод `get_reply_history()` для получения всех версий:

```python
history = await ReplyDAO.get_reply_history(conn, reply_id=123)
# Вернет все версии (оригинал + все редакции) в хронологическом порядке
```

---

## Важные замечания

1. **Временной лимит**: По умолчанию 48 часов, но можно настроить через параметр `time_limit_hours`

2. **Новая reply не опубликована**: Метод `create_edited_reply()` создает запись в БД, но НЕ публикует на платформу. Это должен делать вызывающий код.

3. **Права доступа**: Редактировать может только владелец (assignee) таска.

4. **Audit logging**: Автоматически логируется начало редактирования. Успешную публикацию нужно логировать отдельно.

5. **Preserved fields**: При создании редакции сохраняются:
   - `generated_by` (human/llm)
   - `llm_confidence` (если был LLM)
   - `task_id` (привязка к таску)

6. **Reset fields**: При создании редакции сбрасываются:
   - `confirmed = False` (требует повторного подтверждения)
   - `posted_at = NULL` (еще не опубликовано)
   - `platform_ref = NULL` (будет заполнено после публикации)
