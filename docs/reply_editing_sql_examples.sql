-- ============================================================================
-- SQL Examples for Reply Editing Feature
-- ============================================================================

-- SCENARIO 1: Проверка, что reply можно редактировать
-- ----------------------------------------------------------------------------
-- Этот запрос повторяет логику метода can_edit_reply()

SELECT
    r.id,
    r.task_id,
    r.content,
    r.posted_at,
    t.assignee_user_id,
    m.platform,
    m.channel_id,
    -- Вычисление часов с момента публикации
    EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 AS hours_since_posted,
    -- Проверки
    CASE
        WHEN r.posted_at IS NULL THEN 'not_posted'
        WHEN t.assignee_user_id != 1 THEN 'permission_denied'  -- заменить 1 на user_id
        WHEN EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 > 48 THEN 'time_expired'
        ELSE 'can_edit'
    END AS edit_status
FROM replies r
INNER JOIN tasks t ON r.task_id = t.id
INNER JOIN messages m ON t.source_message_id = m.id
WHERE r.id = 123;  -- заменить на нужный reply_id


-- SCENARIO 2: Получение всех replies, которые можно редактировать для пользователя
-- ----------------------------------------------------------------------------

SELECT
    r.id,
    r.content,
    r.posted_at,
    m.platform,
    m.channel_id,
    EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 AS hours_since_posted,
    48 - EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 AS hours_remaining
FROM replies r
INNER JOIN tasks t ON r.task_id = t.id
INNER JOIN messages m ON t.source_message_id = m.id
WHERE
    t.assignee_user_id = 1  -- user_id
    AND r.posted_at IS NOT NULL
    AND EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 <= 48
ORDER BY r.posted_at DESC;


-- SCENARIO 3: История редактирования конкретного reply
-- ----------------------------------------------------------------------------
-- Использует рекурсивный CTE как в методе get_reply_history()

WITH RECURSIVE reply_versions AS (
    -- Базовый случай: оригинальный reply
    SELECT
        id,
        task_id,
        content,
        posted_at,
        edit_of,
        created_at,
        1 AS version_number
    FROM replies
    WHERE id = 123  -- исходный reply_id

    UNION ALL

    -- Рекурсивный случай: все редакции
    SELECT
        r.id,
        r.task_id,
        r.content,
        r.posted_at,
        r.edit_of,
        r.created_at,
        rv.version_number + 1
    FROM replies r
    INNER JOIN reply_versions rv ON r.edit_of = rv.id
)
SELECT
    version_number,
    id,
    LEFT(content, 50) || '...' AS content_preview,
    posted_at,
    created_at,
    EXTRACT(EPOCH FROM (created_at - LAG(created_at) OVER (ORDER BY created_at)))/3600 AS hours_since_previous
FROM reply_versions
ORDER BY created_at ASC;


-- SCENARIO 4: Audit log для редактирования replies
-- ----------------------------------------------------------------------------

-- Получить все события редактирования за последние 7 дней
SELECT
    id,
    kind,
    user_id,
    payload_json,
    created_at
FROM audit_log
WHERE
    kind = 'reply.edit_started'
    AND created_at >= NOW() - INTERVAL '7 days'
ORDER BY created_at DESC;

-- Детальная информация из payload
SELECT
    id,
    created_at,
    payload_json->>'original_reply_id' AS original_reply_id,
    payload_json->>'new_reply_id' AS new_reply_id,
    payload_json->>'task_id' AS task_id,
    payload_json->>'user_id' AS user_id,
    payload_json->>'platform' AS platform,
    payload_json->>'hours_since_posted' AS hours_since_posted
FROM audit_log
WHERE kind = 'reply.edit_started'
ORDER BY created_at DESC
LIMIT 20;


-- SCENARIO 5: Статистика редактирований
-- ----------------------------------------------------------------------------

-- Подсчет редактирований по пользователям
SELECT
    u.id,
    u.tg_username,
    COUNT(*) AS edit_count,
    AVG((payload_json->>'hours_since_posted')::float) AS avg_hours_until_edit,
    MIN(al.created_at) AS first_edit,
    MAX(al.created_at) AS last_edit
FROM audit_log al
INNER JOIN users u ON al.user_id = u.id
WHERE al.kind = 'reply.edit_started'
GROUP BY u.id, u.tg_username
ORDER BY edit_count DESC;


-- SCENARIO 6: Replies с несколькими версиями
-- ----------------------------------------------------------------------------

-- Найти replies, которые редактировались более 1 раза
SELECT
    r_original.id AS original_reply_id,
    COUNT(r_edits.id) AS edit_count,
    MAX(r_edits.created_at) AS last_edit_time
FROM replies r_original
LEFT JOIN replies r_edits ON r_edits.edit_of = r_original.id
WHERE r_original.edit_of IS NULL  -- только оригиналы
GROUP BY r_original.id
HAVING COUNT(r_edits.id) > 0
ORDER BY edit_count DESC;


-- SCENARIO 7: Проверка целостности данных
-- ----------------------------------------------------------------------------

-- Проверить, что все edited replies ссылаются на существующие оригиналы
SELECT
    r.id,
    r.edit_of,
    r.created_at
FROM replies r
WHERE
    r.edit_of IS NOT NULL
    AND NOT EXISTS (
        SELECT 1
        FROM replies r2
        WHERE r2.id = r.edit_of
    );
-- Должен вернуть пустой результат


-- SCENARIO 8: Test data для локального тестирования
-- ----------------------------------------------------------------------------

-- Создать тестовые данные (ТОЛЬКО для разработки!)
/*
BEGIN;

-- Создать тестового пользователя
INSERT INTO users (tg_id, tg_username, tg_chat_id, role, created_at)
VALUES (12345, 'test_moderator', 67890, 'moderator', NOW())
RETURNING id;  -- запомнить user_id

-- Создать тестовое сообщение
INSERT INTO messages (platform, ext_message_id, channel_id, author_id, author_name, content, created_at)
VALUES ('discord', 'msg_123', 'channel_456', 'author_789', 'Test User', 'Test question?', NOW())
RETURNING id;  -- запомнить message_id

-- Создать тестовый таск
INSERT INTO tasks (source_message_id, status, assignee_user_id, created_at)
VALUES (1, 'answered', 1, NOW())  -- заменить message_id и user_id
RETURNING id;  -- запомнить task_id

-- Создать тестовый reply (опубликованный 10 часов назад)
INSERT INTO replies (
    task_id,
    content,
    generated_by,
    confirmed,
    posted_at,
    platform_ref,
    created_at
)
VALUES (
    1,  -- task_id
    'Original reply content',
    'human',
    true,
    NOW() - INTERVAL '10 hours',
    '{"platform": "discord", "message_id": "reply_999", "channel_id": "channel_456"}',
    NOW() - INTERVAL '10 hours'
)
RETURNING id;  -- запомнить reply_id

COMMIT;
*/


-- SCENARIO 9: Cleanup - удаление тестовых данных
-- ----------------------------------------------------------------------------

/*
-- ВНИМАНИЕ: Удалит все связанные данные через CASCADE!
DELETE FROM users WHERE tg_username = 'test_moderator';
*/


-- SCENARIO 10: Мониторинг производительности
-- ----------------------------------------------------------------------------

-- Анализ времени выполнения запросов редактирования
EXPLAIN ANALYZE
SELECT
    r.id,
    r.task_id,
    r.content,
    r.posted_at,
    t.assignee_user_id,
    m.platform,
    m.channel_id,
    EXTRACT(EPOCH FROM (NOW() - r.posted_at))/3600 AS hours_since_posted
FROM replies r
INNER JOIN tasks t ON r.task_id = t.id
INNER JOIN messages m ON t.source_message_id = m.id
WHERE r.id = 123;

-- Проверить использование индексов
-- Должны использоваться:
-- - idx_replies_task_id (для JOIN с tasks)
-- - idx_tasks_source_message_id (для JOIN с messages)
