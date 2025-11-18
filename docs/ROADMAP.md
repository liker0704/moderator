# Roadmap

## Обзор

План разработки по версиям с оценкой времени и приоритетами.

## MVP v0.1 - Рабочий скелет

**Цель**: Минимальная работающая система с основными функциями.

**Срок**: 3-4 недели

### Backlog

#### 1. Инфраструктура (3 дня)
- [x] Настройка проекта (структура, git)
- [x] Docker Compose (backend, PostgreSQL)
- [x] Базовое логирование
- [x] .env конфигурация

#### 2. База данных (2 дня)
- [x] Создание схемы БД
- [x] Миграции (initial schema)
- [x] Seed данные для тестов
- [x] Шифрование (Fernet для токенов)

#### 3. Discord Integration (5 дней)
- [x] Discord Gateway клиент
  - [x] WebSocket подключение
  - [x] Identify/Resume
  - [x] Heartbeat
  - [x] Reconnection logic
- [x] MESSAGE_CREATE обработка
- [x] Сохранение сообщений в БД
- [x] Фильтрация по allowlist
- [x] Поддержка тредов

#### 4. Telegram Bot (4 дня)
- [x] Long Polling setup
- [x] Команды:
  - [x] /start, /help
  - [x] /setup_discord
  - [x] /test_connection
  - [x] /discord_status
  - [x] /status
  - [x] /dnd
  - [x] /allow_channel
  - [x] /unallow_channel
- [x] Обработка callback queries
- [x] Состояния пользователя (FSM)

#### 5. Карточки и контекст (3 дня)
- [x] Формирование карточек
- [x] Получение контекста (~10 сообщений)
- [x] "Показать больше" (пагинация)
- [x] Inline клавиатура (кнопки)

#### 6. Постинг ответов (4 дня)
- [x] Ввод ответа модератором
- [x] Подтверждение обязательное
- [x] Discord Poster (User API)
- [x] Telegram Poster (Bot API)
- [x] Обработка ошибок
- [x] Кнопка "Повторить"

#### 7. DND режим (2 дня)
- [x] Тумблер вкл/выкл
- [x] Расписание (JSON в БД)
- [x] Scheduler для проверки интервалов
- [x] Подавление карточек при DND

#### 8. Медиа (2 дня)
- [x] Парсинг изображений (Discord, Telegram)
- [x] Сохранение в attachments
- [x] Показ в карточках
- [x] Кликабельные ссылки (disable preview)

#### 9. Алерты (1 день)
- [x] Отправка в админ-чат
- [x] Алерты:
  - [x] Ошибки подключения Discord
  - [x] Падения сервисов
  - [x] Критические ошибки БД

#### 10. Тестирование и фиксы (3 дня)
- [x] Unit тесты (core функции)
- [x] Integration тесты (основные сценарии)
- [x] Manual тестирование
- [x] Фиксы багов

**Итого**: ~29 дней (4 недели)

---

## v0.2 - Удобство + AI

**Цель**: LLM варианты ответов, очереди, улучшенный UX.

**Срок**: 2-3 недели после v0.1

### Backlog

#### 1. LLM Integration (5 дней) ✅ COMPLETE
- [x] OpenAI API клиент
- [x] Anthropic Claude API клиент
- [x] Генерация вариантов (2+)
- [x] Функция "Смягчить"
- [x] Confidence score calculation
- [x] Кнопки выбора вариантов в карточках
- [x] "Ещё варианты"
- [x] Обработка таймаутов
- [x] Кеширование вариантов

#### 2. Система очередей (3 дня) ✅ COMPLETE (v0.2 Iteration 6)
- [x] Redis setup (Docker)
- [x] ARQ (Async Redis Queue)
- [x] Очереди:
  - [x] ingest.discord
  - [x] ingest.telegram
  - [x] post.discord
  - [x] post.telegram
  - [x] llm.generate
- [x] Workers (ARQ worker service)
- [x] Приоритеты (job priority support)

#### 3. Rate Limiting (2 дня) ✅ COMPLETE (v0.2 Iteration 6)
- [x] Bucket system для Discord API
- [x] Rate limiter (per-route)
- [x] Обработка X-RateLimit headers
- [x] Retry с exponential backoff
- [x] Global rate limit (50 req/sec)
- [x] Singleton pattern для shared state

#### 4. Напоминания (2 дня) ✅ COMPLETE (v0.2 Iteration 6)
- [x] Reminders worker (ReminderService class)
- [x] Сканирование open tasks (>30 мин)
- [x] Пинги (каждые 30 мин, макс 3)
- [x] Уважение DND
- [x] settings.reminders_enabled
- [x] Markdown formatting для напоминаний
- [x] Task age и interval фильтрация

#### 5. Команды управления allowlist (1 день) ✅ COMPLETE (v0.2 Iteration 7)
- [x] /unallow_channel с диалогом выбора (interactive mode)
- [x] /unallow_channel <channel_id> (legacy mode)
- [x] Список allowlist в /settings с действительными данными из БД
- [x] Confirmation flow для удаления каналов
- [x] Action buttons в /settings

#### 6. Улучшения UX (2 дня) ✅ COMPLETE (v0.2 Iteration 7)
- [x] Более информативные ошибки (error codes system, ERR-XXX-NNN)
- [x] Подтверждения действий (confirmation dialogs framework)
- [x] /help с категориями (5 категорий: setup, manage, cards, troubleshoot, ai)
- [x] Error recovery suggestions
- [x] Request ID tracking для ошибок
- [ ] Прогресс-бары (отложено)

#### 7. Мониторинг LLM (1 день) ✅ COMPLETE (v0.2 Iteration 6)
- [x] Логирование запросов к LLM (llm_requests table)
- [x] Подсчет стоимости (token-based cost calculation)
- [x] Алерты при превышении бюджета (budget alerts system)
- [x] Метрики использования (LLMMonitoringDAO с views)
- [x] Database schema (003_llm_monitoring.sql)
- [x] Tracking для OpenAI и Anthropic
- [x] Duration и error tracking

#### 8. Тестирование (3 дня)
- [ ] Тесты LLM (mock)
- [ ] Тесты очередей
- [ ] Тесты напоминаний
- [ ] Manual тесты
- [ ] Фиксы

**Итого**: ~19 дней (3 недели)

---

## v1.0 - Финальная версия

**Цель**: Полнофункциональная система с мультисерверностью, поиском, метриками.

**Срок**: 3-4 недели после v0.2

### Backlog

#### 1. Мультисерверность (4 дня)
- [ ] UI для выбора серверов
- [ ] UI для выбора каналов (диалог)
- [ ] Групповое управление allowlist
- [ ] Фильтры по серверам в карточках

#### 2. Редактирование отправленного (3 дня)
- [ ] Кнопка "Редактировать" в карточках
- [ ] Discord edit API
- [ ] Telegram editMessageText
- [ ] replies.edit_of (история)
- [ ] audit_log для правок

#### 3. Поиск по истории (5 дней)
- [ ] Команда /search
- [ ] Фильтры:
  - [ ] По автору
  - [ ] По каналу
  - [ ] По тексту (LIKE или full-text search)
  - [ ] По датам
- [ ] Pagination результатов
- [ ] UI для результатов

#### 4. Метрики и статистика (3 дня)
- [ ] Команда /stats
- [ ] Метрики:
  - [ ] Среднее время ответа
  - [ ] Нагрузка по каналам (топ N)
  - [ ] Незакрытые задачи >24ч
  - [ ] Использование LLM (запросы, стоимость)
- [ ] Графики (опционально, через библиотеку)

#### 5. Шаблоны быстрых ответов (2 дня)
- [ ] Хранение шаблонов (БД)
- [ ] Команды:
  - [ ] /templates list
  - [ ] /templates add
  - [ ] /templates delete
- [ ] Кнопки шаблонов в карточках
- [ ] Подстановка переменных (опционально)

#### 6. Анонимизация/экспорт (2 дня)
- [ ] Команда /export (экспорт данных в JSON)
- [ ] Ручная анонимизация (опционально)

#### 7. Health Check API (1 день)
- [ ] Endpoint /health
- [ ] Проверки:
  - [ ] Discord connection
  - [ ] Database
  - [ ] Redis
  - [ ] LLM API (опционально)

#### 8. Prometheus metrics (опционально, 2 дня)
- [ ] Endpoint /metrics
- [ ] Метрики:
  - [ ] Счетчики (tasks, messages)
  - [ ] Histograms (latency)
  - [ ] Gauges (open tasks)

#### 9. Улучшения безопасности (2 дня)
- [ ] Secrets management (Docker secrets)
- [ ] Rotation токенов (процедура)
- [ ] Audit log расширенный
- [ ] Дополнительная валидация

#### 10. Документация (2 дня)
- [ ] Обновление README
- [ ] API документация (Swagger/OpenAPI опционально)
- [ ] Видео-туториал (опционально)

#### 11. Тестирование (4 дня)
- [ ] Тесты поиска
- [ ] Тесты метрик
- [ ] Тесты редактирования
- [ ] Тесты мультисерверности
- [ ] End-to-end тесты
- [ ] Performance тесты
- [ ] Фиксы

**Итого**: ~30 дней (4 недели)

---

## Постоянные задачи (на всех этапах)

### Документация
- Обновление docs/ при изменениях
- Комментарии в коде
- Changelog

### Мониторинг и логи
- Регулярная проверка алертов
- Анализ логов
- Оптимизация производительности

### Обновления зависимостей
- Обновление Docker images
- Обновление библиотек (security patches)
- Обновление Discord client_build_number

### Бэклог улучшений
- Оптимизация запросов к БД
- Рефакторинг кода
- UI/UX улучшения

---

## Временная шкала

```
Месяц 1: MVP v0.1
├─ Неделя 1: Инфраструктура, БД, Discord Integration (50%)
├─ Неделя 2: Discord Integration (50%), Telegram Bot
├─ Неделя 3: Карточки, Постинг, DND
└─ Неделя 4: Медиа, Алерты, Тестирование

Месяц 2: v0.2
├─ Неделя 5: LLM Integration
├─ Неделя 6: Очереди, Rate Limiting, Напоминания
└─ Неделя 7: UX улучшения, Тестирование

Месяц 3: v1.0
├─ Неделя 8: Мультисерверность, Редактирование
├─ Неделя 9: Поиск, Метрики
├─ Неделя 10: Шаблоны, Health Check, Безопасность
└─ Неделя 11: Документация, Тестирование
```

**Итого**: ~11 недель (2.5 месяца)

---

## Риски и зависимости

### Риски

1. **Discord ToS нарушение**
   - Может потребоваться переделка на Bot API (потеря функциональности)
   - Mitigation: резервные аккаунты, мониторинг изменений

2. **Изменения в Discord Gateway протоколе**
   - Может сломать интеграцию
   - Mitigation: версионирование, быстрые фиксы

3. **LLM API стоимость**
   - Может превысить бюджет
   - Mitigation: мониторинг, лимиты, выбор модели

4. **Один разработчик**
   - Bus factor = 1
   - Mitigation: хорошая документация, код-ревью (если возможно)

### Зависимости

- **PostgreSQL 15+**
- **Redis 7+** (v0.2+)
- **Python 3.11+** или Node.js 18+
- **Discord User Token** (нестабильный)
- **Telegram Bot Token**
- **OpenAI/Anthropic API keys** (v0.2+)

---

## Приоритеты

### Must-have (критические)
- Discord integration (User Gateway)
- Telegram bot (команды, карточки)
- Постинг ответов с подтверждением
- DND режим
- Allowlist management

### Should-have (высокий приоритет)
- LLM варианты (v0.2)
- Очереди и rate limiting (v0.2)
- Мультисерверность (v1.0)
- Поиск (v1.0)

### Nice-to-have (желательно)
- Метрики (v1.0)
- Шаблоны (v1.0)
- Prometheus (опционально)
- Графики в /stats

---

## Критерии готовности версий

### MVP v0.1
- ✅ Discord подключение работает
- ✅ Карточки приходят в TG
- ✅ Ответы отправляются в Discord/Telegram
- ✅ DND работает
- ✅ Allowlist работает
- ✅ Ошибки показываются + "Повторить"
- ✅ Базовые тесты проходят
- ✅ Алерты работают

### v0.2
- ✅ Все из v0.1
- ✅ LLM варианты генерируются
- ✅ "Смягчить" работает
- ✅ Очереди обрабатывают нагрузку
- ✅ Rate limits уважаются
- ✅ Напоминания работают (опционально)
- ✅ Тесты LLM проходят

### v1.0
- ✅ Все из v0.2
- ✅ Мультисерверность работает
- ✅ Поиск находит сообщения
- ✅ /stats показывает метрики
- ✅ Редактирование работает
- ✅ Шаблоны работают
- ✅ Health check endpoint доступен
- ✅ Документация полная
- ✅ Performance тесты проходят

---

## Future (после v1.0)

Возможные улучшения для будущих версий:

### v1.1+
- [ ] Поддержка нескольких модераторов
- [ ] Webhook вместо long polling (Telegram)
- [ ] Webhooks для Discord (если Discord API добавит)
- [ ] Web UI (опционально)
- [ ] Mobile app (опционально)
- [ ] Интеграция с другими платформами (Slack, Matrix)

### v2.0
- [ ] Full Bot API (если Discord разрешит MESSAGE_CONTENT intent)
- [ ] Machine Learning для авто-категоризации
- [ ] Sentiment analysis
- [ ] Автоматические ответы (с одобрением)

---

## Заключение

Roadmap расписан на 3 основные версии с четкими целями и сроками. MVP v0.1 обеспечивает работающую систему, v0.2 добавляет AI и удобство, v1.0 - полнофункциональность.
