# aida3

`aida3` — Telegram-бот на `aiogram 3`, который показывает меню подписок, принимает действия по inline-кнопкам, запускает manual jobs в `aida_functions` через Dagster GraphQL и отправляет пользователю готовые сообщения из RabbitMQ.

## Что умеет бот

- открывать диалоговое меню по заведениям и отчетам;
- хранить пользовательский контекст и подписки в PostgreSQL;
- слушать RabbitMQ и доставлять payload в Telegram;
- запускать manual-отчеты по кнопкам прямо из чата;
- показывать дополнительный выбор порога для отчетов, где он нужен;
- использовать Redis для FSM и `aiogram_dialog`.

## Основные сценарии

### 1. Daily-отчеты

1. `aida_functions` кладет payload в RabbitMQ.
2. `aida3` забирает payload из очереди.
3. Бот отправляет сообщение в Telegram и достраивает inline-клавиатуру на своей стороне.

### 2. Manual-отчеты

1. Пользователь нажимает кнопку в сообщении.
2. `aida3` собирает `unit_uuid`, `account_id`, `chat_id`, `topic_id`, `message_date`.
3. Бот запускает соответствующий Dagster job через GraphQL.
4. Готовый результат приходит обратно через RabbitMQ.

## Ключевые директории

| Путь | Назначение |
| --- | --- |
| `main.py` | Точка входа: bot, dispatcher, middleware, polling и Rabbit listener |
| `config.py` | Конфигурация приложения из env |
| `bot/dialogs/` | Диалоги меню на `aiogram_dialog` |
| `bot/handlers/` | `/start`, inline-actions, обработка ошибок |
| `bot/keyboards/` | Inline-клавиатуры для отчетов и порогов |
| `bot/middlewares/` | Логирование, БД-сессия, локализация и загрузка user context |
| `database/` | SQLAlchemy engine и модели |
| `services/rabbitmq.py` | Consumer очереди и отправка сообщений в Telegram |
| `services/dagster.py` | Запуск Dagster jobs через GraphQL |
| `services/cache.py` | Подключение к Redis |
| `services/i18n.py` | Локализация и переводы |

## Зависимости

- PostgreSQL
- Redis
- RabbitMQ

Дополнительно для manual-отчетов нужен доступ к Dagster GraphQL endpoint.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Основные переменные окружения

### Telegram

- `TOKEN`

### PostgreSQL

- `DBASE_NAME`
- `DBASE_USER`
- `DBASE_PASSWORD`
- `DBASE_HOST`

### Redis

- `REDIS_HOST`
- `REDIS_PORT`

### RabbitMQ

- `RABBIT_URL`
- `RABBIT_QUEUE`

### Dagster GraphQL

- `DAGSTER_GRAPHQL_URL`
- `DAGSTER_REPOSITORY_LOCATION`
- `DAGSTER_REPOSITORY_NAME`
- `DAGSTER_AUTH_HEADER_NAME`
- `DAGSTER_AUTH_HEADER_VALUE`
- `DAGSTER_REQUEST_TIMEOUT_SECONDS`

## Локальный запуск

```bash
python3 main.py
```

Если manual-отчеты должны запускаться локально, рядом нужно поднять `aida_functions`:

```bash
cd ../aida_functions
source .venv/bin/activate
dagster dev -m defs
```

## Что важно знать

- Rabbit listener стартует вместе с ботом и ожидает рабочий `RABBIT_URL`.
- Inline-клавиатуры для payload строятся в `aida3`, а не в `aida_functions`.
- Для некоторых отчетов бот сначала показывает клавиатуру выбора порога, а job запускается только после второго клика.
- Для `certificates`, `later`, `waiting`, `sectors`, `longers`, `later_rest`, `assembly_rest`, `drink_rest` после отправки отчета доступна кнопка `Скрыть отчет`.
