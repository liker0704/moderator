# Reply Editing - Quick Reference

## TL;DR

Добавлены 2 метода в ReplyDAO для редактирования опубликованных replies:

```python
# 1. Проверить возможность редактирования
result = await ReplyDAO.can_edit_reply(conn, reply_id, user_id)

# 2. Создать отредактированную версию (если можно)
new_reply_id = await ReplyDAO.create_edited_reply(conn, reply_id, new_content, user_id)
```

## API

### `can_edit_reply(conn, reply_id, user_id, time_limit_hours=48)`

**Возвращает:**
```python
{
    'can_edit': True/False,
    'reason': 'not_found' | 'not_posted' | 'time_expired' | 'permission_denied',
    'reply': {...},
    'hours_since_posted': 12.5
}
```

**Проверяет:**
- ✓ Reply существует
- ✓ Reply опубликован (posted_at not NULL)
- ✓ User владеет reply (assignee_user_id)
- ✓ Время < 48 часов

### `create_edited_reply(conn, original_reply_id, new_content, user_id)`

**Возвращает:**
- `int` - ID новой reply

**Raises:**
- `ValueError` - если нельзя редактировать

**Создает:**
1. Новую запись в replies (edit_of = original_id)
2. Audit log ('reply.edit_started')

**НЕ делает:**
- Не публикует на платформу (сделайте сами!)

## Workflow

```python
# Полный цикл редактирования
async def edit_reply_workflow(reply_id, new_text, user_id):
    # 1. Проверка
    check = await ReplyDAO.can_edit_reply(conn, reply_id, user_id)
    if not check['can_edit']:
        raise Error(check['reason'])

    # 2. Создание
    new_id = await ReplyDAO.create_edited_reply(
        conn, reply_id, new_text, user_id
    )

    # 3. Публикация на платформу (ваш код)
    await post_to_platform(new_id, new_text)

    # 4. Отметить как опубликованное
    await ReplyDAO.mark_reply_confirmed(conn, new_id)
    await ReplyDAO.mark_reply_posted(conn, new_id, platform_ref)

    return new_id
```

## Константы

```python
DEFAULT_EDIT_TIME_LIMIT = 48  # часов
AUDIT_EVENT_KIND = 'reply.edit_started'
```

## Проверки

```bash
# Синтаксис
python3 -m py_compile backend/src/database/dao/reply_dao.py

# Тесты
pytest tests/test_dao.py::test_reply_dao_methods_exist

# Импорт
python3 -c "from backend.src.database.dao.reply_dao import ReplyDAO; \
            print(hasattr(ReplyDAO, 'can_edit_reply'))"
```

## SQL Examples

```sql
-- Найти все replies, которые можно редактировать
SELECT r.id, r.content,
       EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 AS hours_ago
FROM replies r
JOIN tasks t ON r.task_id = t.id
WHERE t.assignee_user_id = 1
  AND r.posted_at IS NOT NULL
  AND EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 <= 48;

-- История редактирования reply
SELECT id, content, edit_of, created_at
FROM replies
WHERE id = 123 OR edit_of = 123
ORDER BY created_at;

-- Audit logs
SELECT * FROM audit_log
WHERE kind = 'reply.edit_started'
ORDER BY created_at DESC LIMIT 10;
```

## Error Messages

```
Reply 123 does not exist
Reply 123 has not been posted yet
User 1 does not own reply 123
Reply 123 edit time limit exceeded (50.3 hours since posting)
```

## Audit Payload

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

## DB Schema

```sql
replies (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT,
    content TEXT,
    edit_of BIGINT REFERENCES replies(id),  -- ← KEY FIELD
    posted_at TIMESTAMP,
    ...
)
```

## Files Changed

```
backend/src/database/dao/reply_dao.py  (+210 lines)
tests/test_dao.py                       (+4 lines)
```

## Files Created

```
docs/reply_editing_guide.md
docs/reply_editing_sql_examples.sql
docs/IMPLEMENTATION_SUMMARY.md
docs/reply_editing_quick_ref.md
```
