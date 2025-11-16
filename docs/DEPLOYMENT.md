# Развертывание и операции

## Обзор

Система развертывается через Docker Compose и состоит из следующих сервисов:
- **backend** - основное приложение
- **db** - PostgreSQL база данных
- **redis** (v0.2+) - кеш и очереди

## Требования к системе

### Минимальные

- **CPU**: 1 core
- **RAM**: 512 MB
- **Disk**: 5 GB
- **OS**: Linux (Ubuntu 20.04+, Debian 11+)

### Рекомендуемые

- **CPU**: 2 cores
- **RAM**: 2 GB
- **Disk**: 20 GB (SSD)
- **OS**: Ubuntu 22.04 LTS

## Установка Docker

### Ubuntu/Debian

```bash
# Обновление пакетов
sudo apt update
sudo apt upgrade -y

# Установка зависимостей
sudo apt install -y apt-transport-https ca-certificates curl software-properties-common

# Добавление Docker GPG key
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# Добавление репозитория
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Установка Docker
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Проверка
sudo docker --version
sudo docker compose version
```

### Добавление пользователя в группу docker

```bash
sudo usermod -aG docker $USER
newgrp docker
```

## Структура проекта

```
moderator/
├── backend/
│   ├── src/
│   │   ├── discord/
│   │   ├── telegram/
│   │   ├── llm/
│   │   ├── models/
│   │   └── main.py
│   ├── requirements.txt (Python) или package.json (Node.js)
│   ├── Dockerfile
│   └── .env.example
├── migrations/
│   └── *.sql
├── docker-compose.yml
├── .env
└── README.md
```

## Dockerfile (пример для Python)

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование кода
COPY backend/src /app/src

# Переменные окружения
ENV PYTHONUNBUFFERED=1

CMD ["python", "src/main.py"]
```

## docker-compose.yml

```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: moderator_db
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${DB_NAME:-moderator_db}
      POSTGRES_USER: ${DB_USER:-moderator}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${DB_USER:-moderator}"]
      interval: 10s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: .
      dockerfile: backend/Dockerfile
    container_name: moderator_backend
    restart: unless-stopped
    depends_on:
      db:
        condition: service_healthy
    environment:
      # Database
      DB_HOST: db
      DB_PORT: 5432
      DB_NAME: ${DB_NAME:-moderator_db}
      DB_USER: ${DB_USER:-moderator}
      DB_PASSWORD: ${DB_PASSWORD}

      # Telegram
      TELEGRAM_BOT_TOKEN: ${TELEGRAM_BOT_TOKEN}
      MODERATOR_TG_USER_ID: ${MODERATOR_TG_USER_ID}

      # Discord (загружается из БД)
      ENCRYPTION_KEY: ${ENCRYPTION_KEY}

      # LLM (v0.2+)
      LLM_PROVIDER: ${LLM_PROVIDER:-openai}
      OPENAI_API_KEY: ${OPENAI_API_KEY}
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      LLM_MODEL: ${LLM_MODEL:-gpt-4-turbo}

      # Other
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      ALERT_CHAT_ID: ${ALERT_CHAT_ID}
    volumes:
      - ./backend/src:/app/src  # Для разработки (убрать в production)
    ports:
      - "127.0.0.1:8000:8000"  # API порт (опционально)

  # Redis для очередей (v0.2+)
  redis:
    image: redis:7-alpine
    container_name: moderator_redis
    restart: unless-stopped
    ports:
      - "127.0.0.1:6379:6379"
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
```

## Переменные окружения (.env)

Создайте файл `.env` в корне проекта:

```bash
# Database
DB_NAME=moderator_db
DB_USER=moderator
DB_PASSWORD=your_secure_password_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
MODERATOR_TG_USER_ID=987654321

# Encryption (для хранения Discord токена)
# Генерировать: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
ENCRYPTION_KEY=your_fernet_key_here

# LLM (v0.2+)
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
LLM_MODEL=gpt-4-turbo

# Alerts
ALERT_CHAT_ID=987654321  # Telegram ID для алертов

# Logging
LOG_LEVEL=INFO
```

### Генерация ENCRYPTION_KEY

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Или:

```bash
openssl rand -base64 32
```

## Миграции базы данных

### Создание начальной схемы

`migrations/001_initial_schema.sql`:

```sql
-- Содержимое из DATABASE.md
CREATE TABLE users (...);
CREATE TABLE platform_accounts (...);
-- ... и т.д.
```

При первом запуске Docker Compose выполнит все `.sql` файлы из `migrations/`.

### Применение миграций вручную

```bash
docker exec -i moderator_db psql -U moderator -d moderator_db < migrations/002_add_feature.sql
```

## Развертывание

### 1. Клонирование репозитория

```bash
git clone https://github.com/your-org/moderator.git
cd moderator
```

### 2. Настройка переменных окружения

```bash
cp .env.example .env
nano .env  # Заполнить все значения
```

### 3. Запуск сервисов

```bash
# Сборка образов
docker compose build

# Запуск в фоне
docker compose up -d

# Просмотр логов
docker compose logs -f backend

# Проверка статуса
docker compose ps
```

### 4. Инициализация

Подключиться к боту в Telegram и выполнить:

```
/start
/setup_discord
```

Следовать инструкциям для настройки Discord токена.

### 5. Настройка allowlist

```
/allow_channel 111111111111111111 222222222222222222
```

Где:
- `111111111111111111` - Discord guild ID
- `222222222222222222` - Discord channel ID

## Управление сервисами

### Остановка

```bash
docker compose stop
```

### Перезапуск

```bash
docker compose restart backend
```

### Просмотр логов

```bash
# Все сервисы
docker compose logs -f

# Только backend
docker compose logs -f backend

# Последние 100 строк
docker compose logs --tail=100 backend
```

### Обновление кода

```bash
git pull
docker compose build backend
docker compose up -d backend
```

### Очистка

```bash
# Остановка и удаление контейнеров
docker compose down

# С удалением volumes (ВНИМАНИЕ: удалит БД!)
docker compose down -v
```

## Бэкапы

**По ТЗ бэкапы отсутствуют**, но если потребуется:

### Ручной бэкап БД

```bash
# Создание бэкапа
docker exec moderator_db pg_dump -U moderator moderator_db | gzip > backup_$(date +%Y%m%d_%H%M%S).sql.gz

# Восстановление
gunzip < backup_20251116_120000.sql.gz | docker exec -i moderator_db psql -U moderator -d moderator_db
```

### Автоматический бэкап (cron)

```bash
# Добавить в crontab
crontab -e

# Ежедневно в 03:00
0 3 * * * cd /path/to/moderator && docker exec moderator_db pg_dump -U moderator moderator_db | gzip > /backups/moderator_$(date +\%Y\%m\%d).sql.gz

# Очистка старых бэкапов (> 7 дней)
0 4 * * * find /backups -name "moderator_*.sql.gz" -mtime +7 -delete
```

## Мониторинг

### Healthcheck

Добавить endpoint в backend (опционально):

```python
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "discord": get_discord_status(),
        "database": check_db_connection(),
        "timestamp": datetime.now().isoformat()
    }
```

Проверка:

```bash
curl http://localhost:8000/health
```

### Docker healthcheck

```yaml
# В docker-compose.yml для backend
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### Мониторинг логов

```bash
# Поиск ошибок
docker compose logs backend | grep ERROR

# Статистика по событиям
docker compose logs backend | grep "MESSAGE_CREATE" | wc -l
```

## Алерты

### Настройка алертов в Telegram

Алерты отправляются в приватный чат (указать ID в `ALERT_CHAT_ID`).

Типы алертов:
- Ошибки подключения к Discord Gateway
- Ошибки постинга
- Падения сервисов
- Критические ошибки БД

### Пример отправки алерта

```python
def send_alert(message: str):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": ALERT_CHAT_ID,
            "text": f"🚨 ALERT\n\n{message}",
            "disable_web_page_preview": true
        }
    )
```

## Обновления

### Версионирование

Использовать semantic versioning: `v0.1.0`, `v0.2.0`, `v1.0.0`

### Процесс обновления

1. **Остановка сервисов**:
   ```bash
   docker compose stop backend
   ```

2. **Бэкап БД** (если нужен):
   ```bash
   docker exec moderator_db pg_dump -U moderator moderator_db > backup_before_update.sql
   ```

3. **Обновление кода**:
   ```bash
   git fetch
   git checkout v0.2.0
   ```

4. **Миграции БД** (если есть):
   ```bash
   docker exec -i moderator_db psql -U moderator -d moderator_db < migrations/003_v0.2_features.sql
   ```

5. **Пересборка образов**:
   ```bash
   docker compose build backend
   ```

6. **Запуск**:
   ```bash
   docker compose up -d backend
   ```

7. **Проверка**:
   ```bash
   docker compose logs -f backend
   ```

## Troubleshooting

### Backend не стартует

Проверить логи:
```bash
docker compose logs backend
```

Проверить переменные окружения:
```bash
docker compose exec backend env | grep -E "DB_|TELEGRAM_"
```

### БД недоступна

Проверить статус:
```bash
docker compose ps db
docker compose logs db
```

Подключиться к БД:
```bash
docker exec -it moderator_db psql -U moderator -d moderator_db
```

### Discord не подключается

1. Проверить токен (через `/test_connection` в боте)
2. Проверить логи на ошибки Gateway
3. Обновить super properties (могли устареть)

### Telegram бот не отвечает

1. Проверить `TELEGRAM_BOT_TOKEN`
2. Проверить long polling работает:
   ```bash
   curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"
   ```
3. Проверить нет ли активного webhook:
   ```bash
   curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getWebhookInfo"
   ```
   Если есть - удалить:
   ```bash
   curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/deleteWebhook"
   ```

### Высокое использование ресурсов

Проверить использование:
```bash
docker stats
```

Ограничить ресурсы в docker-compose.yml:
```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '1.0'
          memory: 1G
        reservations:
          cpus: '0.5'
          memory: 512M
```

## Безопасность

### Firewall

```bash
# Разрешить только SSH и HTTP/HTTPS
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

### Обновление системы

```bash
sudo apt update
sudo apt upgrade -y
```

### Ограничение доступа к БД

В docker-compose.yml БД доступна только локально:
```yaml
ports:
  - "127.0.0.1:5432:5432"
```

### Secrets management

Использовать Docker secrets (опционально):

```yaml
secrets:
  db_password:
    file: ./secrets/db_password.txt
  telegram_bot_token:
    file: ./secrets/telegram_bot_token.txt

services:
  backend:
    secrets:
      - db_password
      - telegram_bot_token
```

## Production checklist

- [ ] `.env` файл защищен (chmod 600)
- [ ] Все пароли сгенерированы случайно
- [ ] ENCRYPTION_KEY уникален
- [ ] Логи настроены
- [ ] Алерты работают
- [ ] Discord токен настроен
- [ ] Allowlist каналов заполнен
- [ ] Бот отвечает на команды
- [ ] Firewall настроен
- [ ] Cron для очистки старых данных (90 дней)

## Автоматизация

### Systemd service (альтернатива docker-compose daemon)

`/etc/systemd/system/moderator.service`:

```ini
[Unit]
Description=Moderator Console
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/moderator
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Активация:
```bash
sudo systemctl enable moderator.service
sudo systemctl start moderator.service
```

### Cron для очистки БД

```bash
# /etc/cron.daily/moderator-cleanup
#!/bin/bash
docker exec moderator_db psql -U moderator -d moderator_db -c "
DELETE FROM messages WHERE created_at < NOW() - INTERVAL '90 days';
DELETE FROM tasks WHERE created_at < NOW() - INTERVAL '90 days';
DELETE FROM replies WHERE created_at < NOW() - INTERVAL '90 days';
DELETE FROM audit_log WHERE created_at < NOW() - INTERVAL '90 days';
"
```

Сделать исполняемым:
```bash
sudo chmod +x /etc/cron.daily/moderator-cleanup
```

## Заключение

Развертывание через Docker обеспечивает:
- Изоляцию сервисов
- Простоту обновлений
- Воспроизводимость окружения
- Легкость переноса на другие сервера
