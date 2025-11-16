# Интеграция с LLM

## Обзор

Версия v0.2+ включает интеграцию с Large Language Models для:
- Генерации вариантов ответов
- Функции "Смягчить" (перефраз в вежливый тон)
- Помощи модератору в формулировке ответов

**Важно**: Все варианты требуют обязательного подтверждения модератором перед отправкой.

## Поддерживаемые модели

### OpenAI GPT

- **gpt-4-turbo** - рекомендуется
- **gpt-4** - более качественно, дороже
- **gpt-3.5-turbo** - быстрее, дешевле

### Anthropic Claude

- **claude-3-opus** - максимальное качество
- **claude-3-sonnet** - баланс качества и скорости (рекомендуется)
- **claude-3-haiku** - быстро и дешево

### Выбор модели

Определяется переменной окружения:
```
LLM_PROVIDER=openai  # или anthropic
LLM_MODEL=gpt-4-turbo  # или claude-3-sonnet-20240229
```

## OpenAI API

### Конфигурация

```python
import openai

openai.api_key = os.getenv('OPENAI_API_KEY')
```

### Генерация вариантов

**Endpoint**: `POST https://api.openai.com/v1/chat/completions`

**Request**:
```python
def generate_variants_openai(context: List[Message], num_variants: int = 2):
    # Формируем историю
    messages = [
        {
            "role": "system",
            "content": "You are a helpful moderator responding to community messages. Be concise, neutral, and professional."
        }
    ]

    # Добавляем контекст (последние N сообщений)
    for msg in context:
        messages.append({
            "role": "user" if msg.author_id != MODERATOR_ID else "assistant",
            "content": f"[{msg.author_name}]: {msg.content}"
        })

    # Добавляем инструкцию
    messages.append({
        "role": "user",
        "content": f"Generate {num_variants} different response variants to the last message. Each variant should be concise (1-3 sentences) and professional."
    })

    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=messages,
        temperature=0.7,
        max_tokens=500,
        n=num_variants  # Количество вариантов
    )

    variants = []
    for choice in response['choices']:
        variants.append({
            "text": choice['message']['content'].strip(),
            "confidence": 1.0 - (choice.get('finish_reason') != 'stop') * 0.3
        })

    return variants
```

**Response**:
```json
{
  "id": "chatcmpl-123",
  "object": "chat.completion",
  "created": 1700000000,
  "model": "gpt-4-turbo",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "Response variant 1..."
      },
      "finish_reason": "stop"
    },
    {
      "index": 1,
      "message": {
        "role": "assistant",
        "content": "Response variant 2..."
      },
      "finish_reason": "stop"
    }
  ],
  "usage": {
    "prompt_tokens": 123,
    "completion_tokens": 45,
    "total_tokens": 168
  }
}
```

### Функция "Смягчить"

```python
def soften_text_openai(text: str):
    messages = [
        {
            "role": "system",
            "content": "You are an expert at rephrasing text to be more polite and professional while keeping the same meaning."
        },
        {
            "role": "user",
            "content": f"Rephrase this text to be more polite and neutral:\n\n{text}"
        }
    ]

    response = openai.ChatCompletion.create(
        model="gpt-4-turbo",
        messages=messages,
        temperature=0.5,
        max_tokens=300
    )

    return {
        "text": response['choices'][0]['message']['content'].strip(),
        "confidence": 0.9  # Высокая уверенность для простой задачи
    }
```

## Anthropic Claude API

### Конфигурация

```python
import anthropic

client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
```

### Генерация вариантов

**Endpoint**: `POST https://api.anthropic.com/v1/messages`

**Request**:
```python
def generate_variants_claude(context: List[Message], num_variants: int = 2):
    # System prompt
    system = "You are a helpful moderator responding to community messages. Be concise, neutral, and professional."

    # Формируем контекст
    context_text = "\n".join([
        f"[{msg.author_name}]: {msg.content}"
        for msg in context
    ])

    # Основной промпт
    prompt = f"""Context (conversation history):
{context_text}

Generate {num_variants} different response variants to the last message. Each variant should be:
- Concise (1-3 sentences)
- Professional and neutral
- Helpful and clear

Format: List variants as "Variant 1: ...", "Variant 2: ...", etc."""

    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=500,
        temperature=0.7,
        system=system,
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    # Парсинг вариантов
    text = response.content[0].text
    variants = []

    for i in range(1, num_variants + 1):
        pattern = f"Variant {i}:\\s*(.+?)(?=Variant {i+1}:|$)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            variants.append({
                "text": match.group(1).strip(),
                "confidence": 0.85
            })

    return variants
```

### Функция "Смягчить"

```python
def soften_text_claude(text: str):
    system = "You are an expert at rephrasing text to be more polite and professional while keeping the same meaning."

    response = client.messages.create(
        model="claude-3-sonnet-20240229",
        max_tokens=300,
        temperature=0.5,
        system=system,
        messages=[
            {
                "role": "user",
                "content": f"Rephrase this text to be more polite and neutral:\n\n{text}"
            }
        ]
    )

    return {
        "text": response.content[0].text.strip(),
        "confidence": 0.9
    }
```

## System Prompts

### Базовый промпт для модератора

```
You are a helpful moderator for a Discord/Telegram community. Your role is to:

1. Respond professionally and neutrally to user messages
2. Be concise and clear (1-3 sentences preferred)
3. Maintain a friendly but professional tone
4. Avoid escalation or heated responses
5. Provide helpful information or guidance

Do not:
- Use overly formal or robotic language
- Make promises about specific features or timelines
- Engage in arguments or debates
- Use emojis or excessive punctuation

Context will be provided as a conversation history. Generate responses that fit naturally into the conversation.
```

### Промпт для "Смягчить"

```
You are an expert at rephrasing text to be more polite, professional, and neutral while preserving the original meaning and intent.

Guidelines:
- Replace harsh words with softer alternatives
- Add polite phrasing where appropriate
- Maintain the core message
- Keep it concise
- Avoid over-politeness (no excessive "please" or apologies)

Rephrase the provided text following these guidelines.
```

## Обработка контекста

### Формирование истории

```python
def get_llm_context(task: Task, max_messages: int = 20):
    """
    Получить контекст для LLM

    Args:
        task: задача с исходным сообщением
        max_messages: макс. количество сообщений в контексте

    Returns:
        List[Message]: список сообщений для контекста
    """
    source = task.source_message

    # Получаем историю из того же канала
    messages = db.query(Message).filter(
        Message.channel_id == source.channel_id,
        Message.thread_id == source.thread_id,
        Message.platform_created_at <= source.platform_created_at
    ).order_by(
        Message.platform_created_at.desc()
    ).limit(max_messages).all()

    # Реверс (от старых к новым)
    return list(reversed(messages))
```

### Ограничения контекста

**Token limits**:
- GPT-4 Turbo: 128k tokens (~96k слов)
- Claude 3 Sonnet: 200k tokens (~150k слов)

Для MVP достаточно 20-30 сообщений (~2-3k tokens).

### Сжатие контекста (опционально)

Если история слишком большая:

```python
def compress_context(messages: List[Message], max_tokens: int = 2000):
    """Сжать контекст, оставив важные сообщения"""

    # Стратегия: последние N + первые M
    recent = messages[-10:]  # Последние 10
    initial = messages[:5]   # Первые 5

    return initial + ["..."] + recent
```

## Определение уверенности

### Метрики уверенности

LLM не всегда возвращает явную метрику уверенности. Используем эвристики:

```python
def calculate_confidence(response_text: str, finish_reason: str = "stop") -> float:
    """
    Оценка уверенности модели

    Args:
        response_text: текст ответа
        finish_reason: причина завершения ('stop', 'length', 'content_filter')

    Returns:
        float: confidence score (0.0 - 1.0)
    """
    confidence = 1.0

    # Штрафы
    if finish_reason != "stop":
        confidence -= 0.3  # Не завершено естественно

    if len(response_text) < 10:
        confidence -= 0.2  # Слишком короткий ответ

    # Признаки неуверенности в тексте
    uncertainty_phrases = [
        "I'm not sure",
        "I don't know",
        "might be",
        "possibly",
        "unclear"
    ]

    for phrase in uncertainty_phrases:
        if phrase.lower() in response_text.lower():
            confidence -= 0.15
            break

    return max(0.0, min(1.0, confidence))
```

### Отображение низкой уверенности

Если `confidence < 0.7`:

```
⚠️ Модель не уверена в этом ответе

[Вариант 1]
[Вариант 2]
```

## Обработка ошибок и таймаутов

### Таймауты

```python
import requests

def generate_variants_with_timeout(context, num_variants=2, timeout=30):
    try:
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            json={...},
            timeout=timeout
        )
        return parse_variants(response.json())

    except requests.Timeout:
        # Вернуть пустой список или ошибку
        return {
            "error": "LLM_TIMEOUT",
            "message": "Timeout waiting for LLM response",
            "variants": []
        }

    except requests.RequestException as e:
        return {
            "error": "LLM_ERROR",
            "message": str(e),
            "variants": []
        }
```

### Fallback стратегия

Если LLM недоступен:

```python
def generate_variants_with_fallback(context, num_variants=2):
    try:
        return generate_variants_openai(context, num_variants)
    except Exception as e:
        logger.error(f"LLM error: {e}")

        # Fallback: пустые варианты
        return []

    # Или использовать резервную модель:
    # return generate_variants_claude(context, num_variants)
```

## Стоимость и оптимизация

### Примерная стоимость (на ноябрь 2025)

**OpenAI GPT-4 Turbo**:
- Input: $10 / 1M tokens
- Output: $30 / 1M tokens

**Claude 3 Sonnet**:
- Input: $3 / 1M tokens
- Output: $15 / 1M tokens

### Расчет стоимости

Средний запрос:
- Контекст: ~1000 tokens
- Ответ: ~100 tokens
- **1 генерация 2 вариантов**: ~$0.004 (GPT-4 Turbo)

При 100 задач/день: ~$0.40/день = $12/месяц.

### Оптимизация

1. **Кеширование**: не генерировать варианты повторно для той же задачи
2. **Сжатие контекста**: ограничить историю 20 сообщениями
3. **Выбор модели**: использовать Sonnet вместо Opus для обычных случаев
4. **Батчинг** (если возможно): группировать запросы

```python
# Кеширование
llm_cache = {}

def generate_variants_cached(task_id, context, num_variants=2):
    cache_key = f"task_{task_id}_variants"

    if cache_key in llm_cache:
        return llm_cache[cache_key]

    variants = generate_variants(context, num_variants)
    llm_cache[cache_key] = variants

    return variants
```

## UI для вариантов LLM

### Карточка с вариантами

```
Discord • Server • #channel • @user • 12:34

Context:
[12:30] user1: Message 1
[12:34] user: Current message

AI Suggestions:

Variant 1: [Generated response 1]
Variant 2: [Generated response 2]

[Select Variant 1] [Select Variant 2]
[More Variants] [Soften...] [Manual Reply]
```

### Callback data

```python
keyboard = {
    "inline_keyboard": [
        [
            {"text": "Вариант 1", "callback_data": f"llm_variant_{task_id}_1"},
            {"text": "Вариант 2", "callback_data": f"llm_variant_{task_id}_2"}
        ],
        [
            {"text": "Ещё варианты", "callback_data": f"llm_more_{task_id}"},
            {"text": "Смягчить...", "callback_data": f"llm_soften_{task_id}"}
        ],
        [
            {"text": "Ответить вручную", "callback_data": f"reply_{task_id}"}
        ]
    ]
}
```

### Обработка выбора варианта

```python
def handle_llm_variant_selection(task_id, variant_num):
    # Получить вариант из кеша
    variants = llm_cache.get(f"task_{task_id}_variants", [])

    if variant_num > len(variants):
        return {"error": "Invalid variant"}

    variant = variants[variant_num - 1]

    # Создать reply
    reply = Reply(
        task_id=task_id,
        content=variant['text'],
        generated_by='llm',
        llm_confidence=variant['confidence'],
        confirmed=False
    )
    db.add(reply)
    db.commit()

    # Показать подтверждение
    show_confirmation_card(task_id, reply.id)
```

## Безопасность и этика

### Фильтрация токсичности

По требованию ТЗ: **не фильтруем токсичность** - модератор видит всё как есть.

Но можно добавить опционально:

```python
def check_toxicity(text: str) -> float:
    """
    Проверка токсичности через Perspective API (опционально)

    Returns:
        float: toxicity score (0.0 - 1.0)
    """
    # Интеграция с Perspective API
    # https://perspectiveapi.com/
    pass
```

### Privacy

- Не отправлять в LLM чувствительные данные (токены, пароли)
- Логировать все запросы к LLM для аудита
- Периодически проверять использование API ключей

### Audit

```python
def log_llm_request(task_id, prompt_tokens, completion_tokens, model):
    """Логирование запроса к LLM"""
    audit_log.create(
        kind='llm_request',
        payload_json=json.dumps({
            "task_id": task_id,
            "model": model,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "cost": calculate_cost(prompt_tokens, completion_tokens, model)
        })
    )
```

## Тестирование

### Unit тесты

```python
def test_generate_variants():
    context = [
        Message(author_name="user1", content="Hello"),
        Message(author_name="user2", content="Hi, how can I help?")
    ]

    variants = generate_variants(context, num_variants=2)

    assert len(variants) == 2
    assert all('text' in v and 'confidence' in v for v in variants)
    assert all(0.0 <= v['confidence'] <= 1.0 for v in variants)

def test_soften_text():
    harsh = "This is wrong and you need to fix it now."
    softened = soften_text(harsh)

    assert softened['text'] != harsh
    assert len(softened['text']) > 10
    assert 'please' in softened['text'].lower() or 'could' in softened['text'].lower()
```

### Mock LLM для тестов

```python
class MockLLM:
    def generate(self, prompt, **kwargs):
        return {
            "choices": [
                {"message": {"content": "Mock variant 1"}},
                {"message": {"content": "Mock variant 2"}}
            ]
        }

# В тестах
llm_client = MockLLM()
```

## Мониторинг

### Метрики

- Количество запросов к LLM/день
- Среднее время ответа LLM
- Частота использования вариантов vs ручной ввод
- Стоимость/день

```python
def track_llm_usage():
    today = datetime.now().date()

    count = db.query(Reply).filter(
        Reply.generated_by == 'llm',
        Reply.created_at >= today
    ).count()

    print(f"LLM generated replies today: {count}")
```

### Алерты

Отправлять алерт если:
- LLM недоступен > 5 минут
- Стоимость/день > $10
- Время ответа > 30 сек (p95)

## Заключение

Интеграция с LLM добавляет автоматизацию и помощь модератору, но требует:
- API ключей и оплаты
- Обработки ошибок и таймаутов
- Мониторинга стоимости
- Обязательного подтверждения всех вариантов модератором
