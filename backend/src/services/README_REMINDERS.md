# Reminder Service

Автоматическая система напоминаний о неотвеченных задачах.

## Основные характеристики

- **Периодичность**: Проверка каждые 30 минут
- **Лимит**: Максимум 3 напоминания на задачу
- **Фильтрация**: Учитывает DND режим и настройки пользователя
- **Интеграция**: Работает с Telegram Bot API

## Константы

```python
REMINDER_INTERVAL_MINUTES = 30  # Интервал проверки
MAX_REMINDERS = 3               # Максимум напоминаний
MIN_TASK_AGE_MINUTES = 30       # Минимальный возраст задачи
```

## Логика проверок (_should_send_reminder)

Напоминание НЕ отправляется если:

1. ✅ **Max reminders reached**: `reminder_count >= 3`
2. ✅ **Task too new**: Задача создана менее 30 минут назад
3. ✅ **Not enough time passed**: С последнего обновления прошло < 30 минут
4. ✅ **User has reminders disabled**: `settings.reminders_enabled = FALSE`
5. ✅ **DND mode active**: Активен режим "Не беспокоить"

## Использование

### Инициализация и запуск

```python
from services.reminders import start_reminder_scheduler, stop_reminder_scheduler

# Запуск
reminder_service = await start_reminder_scheduler(telegram_bot)

# Остановка
await stop_reminder_scheduler()
```

### Получение инстанса

```python
from services.reminders import get_reminder_service

service = get_reminder_service()
if service:
    # Ручной запуск сканирования (для тестирования)
    await service.scan_and_send_reminders()
```

## Настройки пользователя

Включение/отключение напоминаний в БД:

```sql
-- Включить напоминания
UPDATE settings
SET reminders_enabled = TRUE
WHERE user_id = 1;

-- Отключить напоминания
UPDATE settings
SET reminders_enabled = FALSE
WHERE user_id = 1;
```

## Формат напоминания

```
🔔 Reminder

Task #42 has been open for 1h 30m

From: JohnDoe (discord)
Channel: 123456789

Message:
Hello, I need help with...

⚠️ Action Required: Please respond to this message or mute the task.
```

## Архитектура

```
ReminderService (Singleton)
├── start()                      # Запуск scheduler
├── stop()                       # Остановка scheduler
├── scan_and_send_reminders()    # Основная функция сканирования
├── _should_send_reminder()      # Проверка условий
├── _send_reminder()             # Отправка через Telegram
└── _build_reminder_text()       # Форматирование текста
```

## Зависимости

- `TaskDAO`: Работа с задачами
- `UserDAO`: Получение настроек пользователя
- `MessageDAO`: Получение данных сообщений
- `is_dnd_active()`: Проверка DND режима
- `TelegramBot.send_message()`: Отправка уведомлений

## Логирование

```python
# Информация о запуске/остановке
logger.info("Reminder service started")
logger.info("Reminder service stopped")

# Результаты сканирования
logger.info("Reminder scan complete: 5 sent, 10 skipped")

# Отправленные напоминания
logger.info("Sent reminder for task 42 (count: 1)")

# Пропущенные задачи
logger.debug("Skipping task 123: max reminders reached (3)")
```

## Тестирование

```bash
# Запустить тесты
pytest backend/tests/test_reminders.py -v

# Проверить покрытие
pytest backend/tests/test_reminders.py --cov=services.reminders
```

## Мониторинг

Метрики для отслеживания:

- Количество отправленных напоминаний за период
- Количество пропущенных задач (по каждой причине)
- Ошибки отправки через Telegram
- Время выполнения сканирования

## Troubleshooting

### Напоминания не отправляются

1. Проверьте `reminders_enabled` в `settings` таблице
2. Убедитесь что DND режим выключен
3. Проверьте возраст задачи (>30 минут)
4. Проверьте количество отправленных напоминаний (<3)
5. Посмотрите логи: `grep "Reminder" app.log`

### Ошибки Telegram

1. Проверьте токен бота
2. Убедитесь что бот запущен
3. Проверьте права доступа
4. Посмотрите ошибки в логах
