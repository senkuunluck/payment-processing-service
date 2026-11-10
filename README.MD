
# Payment Processing Service

Асинхронный микросервис обработки платежей.

## Технологии

- Python 3.12
- FastAPI
- Pydantic v2
- SQLAlchemy 2 Async
- PostgreSQL
- RabbitMQ
- FastStream
- Alembic
- Docker Compose
- Pytest
- Ruff
- Mypy

## Архитектура

Сервис состоит из двух самостоятельных приложений:

- API — принимает запросы на создание платежей и предоставляет информацию о платежах.
- Consumer — получает события из RabbitMQ, обрабатывает платежи и отправляет webhook.

Для надёжной публикации событий используется Transactional Outbox.

## Основные возможности

- Создание платежей.
- Получение информации о платеже.
- Идемпотентность по Idempotency-Key.
- Авторизация через X-API-Key.
- Асинхронная обработка через RabbitMQ.
- Симуляция обработки платежа от 2 до 5 секунд.
- Вероятность успешной обработки — 90%.
- Отправка webhook после обработки.
- Повторные попытки обработки.
- Dead Letter Queue.
- Transactional Outbox.

## Запуск через Docker Compose

Создайте локальный файл `.env` на основе `.env.example`.

Укажите собственный API_KEY.

Запустите:

```bash
docker compose up -d --build
```

Посмотрите состояние контейнеров:

```bash
docker compose ps
```

Посмотрите логи API:

```bash
docker compose logs -f api
```

Посмотрите логи Consumer:

```bash
docker compose logs -f consumer
```

Посмотрите логи RabbitMQ:

```bash
docker compose logs -f rabbitmq
```

Остановка:

```bash
docker compose down
```

Данные PostgreSQL и RabbitMQ сохраняются в Docker volumes.

## Локальный запуск

Запустите PostgreSQL и RabbitMQ.

Активируйте виртуальное окружение и установите проект:

```bash
pip install -e ".[dev]"
```

Примените миграции:

```bash
alembic upgrade head
```

Запустите API:

```bash
uvicorn app.main:app --reload
```

В отдельном терминале запустите Consumer:

```bash
python -m app.consumer
```

## API

### Авторизация

Для всех API-запросов требуется заголовок:

```http
X-API-Key: your-secret-api-key
```

### Создание платежа

```http
POST /api/v1/payments
```

Заголовки:

```http
Content-Type: application/json
X-API-Key: your-secret-api-key
Idempotency-Key: unique-payment-key-001
```

Тело запроса:

```json
{
  "amount": "100.00",
  "currency": "RUB",
  "description": "Test payment",
  "metadata": {
    "order_id": "12345"
  },
  "webhook_url": "https://example.com/webhook"
}
```

Ожидаемый HTTP-статус: 202 Accepted.

### Получение платежа

```http
GET /api/v1/payments/{payment_id}
```

### Проверка состояния сервиса

```http
GET /health
```

### Swagger

После запуска API:

http://localhost:8000/docs

## RabbitMQ Management

Панель управления RabbitMQ:

http://localhost:15672

Пользователь и пароль задаются через Docker Compose.

Основная очередь:

- payments.new

Очереди повторных попыток и DLQ используются для обработки ошибок.

## Тестирование

Запуск всех тестов:

```bash
pytest -v
```

Проверка Ruff:

```bash
ruff check app tests
```

Форматирование:

```bash
ruff format app tests
```

Проверка типов:

```bash
mypy app
```

## Миграции

Создание миграции:

```bash
alembic revision --autogenerate -m "migration description"
```

Применение миграций:

```bash
alembic upgrade head
```

Просмотр текущей версии:

```bash
alembic current
```
