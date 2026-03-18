# Aida3

`Aida3` — Telegram-бот для управления меню подписок, отчётов и уведомлений по ресторанам Dodo Brands.  
Приложение построено на `aiogram 3`, использует `aiogram_dialog` для сценариев меню и хранит пользовательский контекст, настройки и подписки в PostgreSQL.

## Что умеет бот

- открывать диалоговое меню с разделами уведомлений, отчётов, оперативных данных и настроек;
- сохранять подписки по чатам, аккаунтам и заведениям в таблице `aida.orders`;
- выбирать язык интерфейса на уровне конкретного чата;
- получать входящие сообщения из RabbitMQ и пересылать их в Telegram;
- использовать Redis для хранения FSM-состояния и кеша диалогов.

## Стек

- Python 3.12
- `aiogram`
- `aiogram_dialog`
- `SQLAlchemy` + `asyncpg`
- `redis`
- `aio-pika`
- `loguru`

## Зависимости окружения

Для локального запуска нужны:

- PostgreSQL
- Redis
- RabbitMQ

Сейчас RabbitMQ не является опциональным: listener запускается при старте приложения и ожидает валидный `RABBIT_URL`.

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Переменные окружения

Конфигурация читается через `environs`, обычно из `.env`.

```env
TOKEN=telegram_bot_token

DBASE_NAME=postgres_db_name
DBASE_USER=postgres_user
DBASE_PASSWORD=postgres_password
DBASE_HOST=postgres_host

REDIS_HOST=redis_host
REDIS_PORT=6379

RABBIT_URL=amqp://guest:guest@localhost/
RABBIT_QUEUE=aida
```

## Запуск

Локально:

```bash
python3 main.py
```

В Docker:

```bash
docker build -t aida3 .
docker run --env-file .env aida3
```

## Как устроен проект

| Путь | Назначение |
| --- | --- |
| `main.py` | Точка входа: инициализация бота, storage, middleware, роутеров и фонового listener |
| `config.py` | Загрузка конфигурации из переменных окружения |
| `logger.py` | Настройка JSON-логов в stdout и файл |
| `bot/dialogs/` | Состояния, окна, геттеры, тексты и обработчики меню |
| `bot/handlers/` | `/start` и глобальный обработчик ошибок Telegram API |
| `bot/middlewares/` | Логирование, БД-сессия, локализация, загрузка контекста пользователя |
| `database/models.py` | SQLAlchemy-модели схем `special` и `aida` |
| `database/requests/` | Функции для чтения и обновления пользовательских данных, настроек и подписок |
| `services/i18n.py` | gettext-локализация и fallback-переводы |
| `services/cache.py` | Инициализация Redis-клиента |
| `services/rabbitmq.py` | Чтение сообщений из RabbitMQ и отправка их в Telegram |

## Данные и поведение

- Язык интерфейса берётся из `special.settings.country` с привязкой к `chat_id`.
- Контекст пользователя собирается из таблиц `special.users`, `special.user_account`, `special.accounts`, `special.tokens` и `special.subscribes`.
- Подписки на отчёты и уведомления хранятся в `aida.orders`.
- Логи пишутся в stdout и в файл `logs/aida.log`.
