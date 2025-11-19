# Reply Editing - Implementation Summary

## Выполнено

### 1. Добавлены новые методы в ReplyDAO

Файл: `/home/user/moderator/backend/src/database/dao/reply_dao.py`

#### Метод 1: `can_edit_reply()` (строки 445-553)
- **Назначение**: Проверка возможности редактирования reply
- **Проверки**:
  1. Reply существует
  2. Reply уже опубликован (posted_at IS NOT NULL)
  3. Пользователь владеет reply (через task.assignee_user_id)
  4. Не превышен лимит времени (по умолчанию 48 часов)
- **SQL**: JOIN с tables tasks и messages для получения полной информации
- **Возвращает**: Dict с полями can_edit, reason, reply, hours_since_posted

#### Метод 2: `create_edited_reply()` (строки 555-655)
- **Назначение**: Создание новой версии reply как редакции
- **Действия**:
  1. Валидация через can_edit_reply()
  2. INSERT новой записи с edit_of = original_reply_id
  3. Создание audit log (kind='reply.edit_started')
- **Особенности**:
  - Сохраняет generated_by и llm_confidence из оригинала
  - Устанавливает confirmed=False (требует подтверждения)
  - НЕ публикует на платформу (делает caller)
- **Audit payload**: Содержит original_reply_id, new_reply_id, task_id, user_id, platform, channel_id, content lengths, hours_since_posted

### 2. Обновлен импорт

Добавлен `import json` в начало файла (строка 11)

### 3. Обновлены тесты

Файл: `/home/user/moderator/tests/test_dao.py` (строки 46-51)
- Добавлены проверки наличия новых методов
- Добавлены проверки callable для новых методов

### 4. Создана документация

#### Файл: `/home/user/moderator/docs/reply_editing_guide.md`
- Подробное описание методов
- Примеры использования
- Полный workflow редактирования
- Структура audit logging
- Важные замечания и best practices

#### Файл: `/home/user/moderator/docs/reply_editing_sql_examples.sql`
- 10 SQL сценариев для тестирования
- Примеры запросов для проверки функциональности
- Тестовые данные для разработки
- Мониторинг производительности

## Технические детали

### SQL Query в can_edit_reply()

```sql
SELECT
    r.id, r.task_id, r.content, r.generated_by, r.llm_confidence,
    r.confirmed, r.posted_at, r.platform_ref, r.edit_of, r.created_at,
    t.assignee_user_id,
    m.platform,
    m.channel_id,
    EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 AS hours_since_posted
FROM replies r
INNER JOIN tasks t ON r.task_id = t.id
INNER JOIN messages m ON t.source_message_id = m.id
WHERE r.id = $1
```

### Audit Log Payload Example

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

### Error Handling

Метод `create_edited_reply()` выбрасывает `ValueError` с информативными сообщениями:
- `"Reply {id} does not exist"`
- `"Reply {id} has not been posted yet"`
- `"User {id} does not own reply {id}"`
- `"Reply {id} edit time limit exceeded ({hours} hours since posting)"`

## Интеграция с существующим кодом

### Используемые существующие методы:
- `ReplyDAO.get_reply_by_id()` - не используется напрямую, данные получаются через can_edit_reply()
- `AuditDAO.log_event()` - используется для создания audit log

### Используемые индексы:
- `idx_replies_task_id` - для JOIN с tasks
- `idx_tasks_source_message_id` - для JOIN с messages (если есть)

### Поля таблицы replies:
Используются все поля, ключевое новое использование:
- `edit_of` - ссылка на оригинальный reply (NULL для оригиналов)

## Примеры использования

### Быстрая проверка:
```python
result = await ReplyDAO.can_edit_reply(conn, reply_id=123, user_id=1)
if result['can_edit']:
    print(f"OK: {result['hours_since_posted']:.1f}h since posting")
else:
    print(f"ERROR: {result['reason']}")
```

### Создание редакции:
```python
try:
    new_id = await ReplyDAO.create_edited_reply(
        conn, original_reply_id=123,
        new_content='Updated text', user_id=1
    )
    print(f"Created edited reply: {new_id}")
except ValueError as e:
    print(f"Cannot edit: {e}")
```

## Проверка

### Синтаксис:
```bash
python3 -m py_compile backend/src/database/dao/reply_dao.py
# ✓ Успешно (без ошибок)
```

### Тесты:
```bash
pytest tests/test_dao.py::test_reply_dao_methods_exist -v
# Проверяет наличие can_edit_reply и create_edited_reply
```

## Статистика изменений

- **Строк добавлено**: ~210
- **Новых методов**: 2
- **Обновлено файлов**: 2 (reply_dao.py, test_dao.py)
- **Создано документации**: 2 файла
- **SQL запросов**: 1 сложный SELECT с 2 JOINs, 1 INSERT

## TODO для интеграции

1. **Telegram/Discord handlers**: Добавить обработчики команд редактирования
2. **API endpoints**: Создать REST API для редактирования replies (если нужно)
3. **UI**: Добавить кнопки "Edit" в Telegram карточках
4. **Rate limiting**: Ограничить количество редактирований (опционально)
5. **Notifications**: Уведомления при редактировании replies (опционально)
6. **Второй audit log**: Добавить событие 'reply.edit_posted' после успешной публикации

## Безопасность

✓ SQL injection защита: Используются параметризованные запросы ($1, $2, etc)
✓ Валидация прав: Проверка assignee_user_id
✓ Временной лимит: 48 часов по умолчанию
✓ Audit logging: Полное логирование всех действий

## Производительность

- JOIN с 2 таблицами (tasks, messages)
- Использование существующих индексов
- Вычисление hours_since_posted на уровне SQL
- Нет N+1 queries

## Обратная совместимость

✓ Не меняет существующие методы
✓ Не меняет схему БД (использует существующее поле edit_of)
✓ Не ломает существующий код
✓ Опциональная функциональность
