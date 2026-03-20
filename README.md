# aida3

`aida3` — Telegram-бот на `aiogram 3`, который управляет подписками, запускает manual jobs в `aida_functions` через Dagster GraphQL и отправляет готовые payload из RabbitMQ в Telegram.

## Что умеет бот

- открывать диалоговое меню по заведениям и отчетам;
- хранить пользовательский контекст и подписки в PostgreSQL;
- слушать RabbitMQ и доставлять payload в Telegram;
- запускать manual-отчеты по кнопкам прямо из чата;
- запускать manual-отчеты из раздела `Оперативные данные` по выбранным заведениям;
- показывать дополнительный выбор порога для отчетов, где он нужен;
- использовать Redis для FSM и `aiogram_dialog`.

## Основные сценарии

### Плановые отчеты

1. `aida_functions` кладет payload в RabbitMQ.
2. `aida3` забирает payload из очереди.
3. Бот отправляет сообщение в Telegram и достраивает inline-клавиатуру на своей стороне.

### Manual-отчеты из сообщений

1. Пользователь нажимает кнопку в сообщении.
2. `aida3` собирает `unit_uuid`, `account_id`, `chat_id`, `topic_id`, `message_date` и, если нужно, порог.
3. Бот запускает соответствующий Dagster job через GraphQL.
4. Готовый результат приходит обратно через RabbitMQ.

### Оперативные данные

1. Пользователь открывает раздел `Оперативные данные`.
2. Выбирает сценарий: `Трекинг`, `Текущие метрики`, `Выручка по сети` или `Большие складские остатки`.
3. Выбирает одно или несколько заведений.
4. `aida3` запускает соответствующий manual job в Dagster.
5. Готовый отчет приходит в ту же очередь RabbitMQ и отправляется в чат.

## Ключевые директории

| Путь | Назначение |
| --- | --- |
| `main.py` | Точка входа: bot, dispatcher, middleware, polling и Rabbit listener |
| `config.py` | Конфигурация приложения из env |
| `bot/dialogs/` | Диалоги меню на `aiogram_dialog` |
| `bot/handlers/` | `/start`, inline-actions, обработка ошибок |
| `bot/keyboards/` | Inline-клавиатуры для отчетов и порогов |
| `bot/middlewares/` | Логирование, БД-сессия, локализация и загрузка user context |
| `database/` | SQLAlchemy engine, модели и запросы к подпискам |
| `services/rabbitmq.py` | Consumer очереди и отправка сообщений в Telegram |
| `services/dagster.py` | Запуск Dagster jobs через GraphQL |
| `services/cache.py` | Подключение к Redis |
| `services/i18n.py` | Локализация, fallback-переводы и helper-функции `get_translator`/`tr` |

## Меню подписок

### Уведомления

- дни рождения;
- стаж и годовщины;
- отмененные заказы;
- брак;
- стопы;
- тикеты.

### Отчеты

- выручка по сети;
- курьеры;
- ресторан;
- метрики;
- складские остатки;
- списания.

## Зависимости

- PostgreSQL
- Redis
- RabbitMQ
- Dagster GraphQL endpoint для manual-отчетов

## Установка и локальный запуск

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Если manual-отчеты должны запускаться локально, рядом нужно поднять `aida_functions`:

```bash
cd ../aida_functions
source .venv/bin/activate
dagster dev -m defs
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

## Что важно знать

- Rabbit listener стартует вместе с ботом и ожидает рабочий `RABBIT_URL`.
- Inline-клавиатуры для payload строятся в `aida3`, а не в `aida_functions`.
- Для некоторых отчетов бот сначала показывает клавиатуру выбора порога, а job запускается только после второго клика.
- Для отчетов из `Оперативных данных` бот сначала открывает список заведений, а потом запускает manual job по выбранным точкам.
- Для `certificates`, `later`, `waiting`, `sectors`, `longers`, `later_rest`, `assembly_rest`, `drink_rest` после отправки отчета доступна кнопка `Скрыть отчет`.
- Для payload без `unit_uuid` action-клавиатура не достраивается, но само сообщение все равно будет отправлено.
- Подписки в `aida.orders` создаются и обновляются из меню бота через `database/requests/orders.py`.

## Локализация

- Базовый язык интерфейса в коде — английский.
- Русские fallback-переводы собраны в `services/i18n.py`.
- В хендлерах и middleware для новых строк лучше использовать `tr(...)`, а не хардкодить русские тексты.
- Для меню и диалогов язык берется из пользовательских настроек чата.
- Для клавиатур под готовыми отчетами язык тоже определяется по настройкам чата в момент отправки из RabbitMQ.
