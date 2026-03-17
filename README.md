# Aida3

Telegram‑бот для удалённого управления ресторанами Dodo Brands.  
Меню и подписки реализованы через `aiogram_dialog`, данные и настройки берутся из БД.

**Возможности**
- Меню на `aiogram_dialog` с подписками на отчёты и уведомления.
- Хранение подписок в таблице `aida.orders`.
- Локализация (RU/EN) через `services/i18n.py` и настройки в таблице `special.settings`.
- Асинхронная работа с PostgreSQL, Redis и (опционально) RabbitMQ.

**Требования**
- Python 3.12+
- PostgreSQL
- Redis
- RabbitMQ (опционально, для входящих сообщений)

**Установка**
1. Создай виртуальное окружение и активируй его.
2. Установи зависимости:
```bash
pip install -r requirements.txt
```

**Переменные окружения**
Задаются через `.env` (или любым способом, который читает `environs`):
```env
TOKEN=...
DBASE_NAME=...
DBASE_USER=...
DBASE_PASSWORD=...
DBASE_HOST=...
REDIS_HOST=...
REDIS_PORT=6379
RABBIT_URL=amqp://...
RABBIT_QUEUE=aida
```

**Запуск**
```bash
python main.py
```

**Структура проекта**
| Путь | Назначение |
| --- | --- |
| `main.py` | Точка входа, подключение middleware и роутеров |
| `bot/dialogs/` | Окна меню, обработчики, состояния, геттеры |
| `bot/handlers/` | Команды и глобальные обработчики ошибок |
| `bot/middlewares/` | Логирование, БД‑сессии, локализация |
| `database/models.py` | SQLAlchemy модели |
| `database/requests/` | Логика запросов к БД |
| `services/i18n.py` | Локализация и fallback‑переводы |
| `services/cache.py` | Redis‑кеш |
| `services/rabbitmq.py` | RabbitMQ listener |

**Логи**
- Файл `logs/aida.log` (логгер `loguru`)

**Примечания**
- Язык берётся из `special.settings.country` для текущего `chat_id`.
- Подписки на отчёты хранятся в `aida.orders` по ключу `post + account_id + chat_id`.
