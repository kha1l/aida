"""Точка входа Telegram-бота Aida3."""

import asyncio
import contextlib
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import Config, load_config
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.base import DefaultKeyBuilder
from aiogram.fsm.storage.redis import RedisStorage
from aiogram_dialog import setup_dialogs
from services.rabbitmq import rabbit_listener
from bot.middlewares.mdw_logging import LoggingMiddleware
from bot.middlewares.mdw_database import UserDBMiddleware, DBSessionMiddleware
from bot.middlewares.mdw_locale import I18nMiddleware
from logger import setup_logging
from database.engine import session_maker
from services.cache import RedisCache
from bot.handlers import start_handlers
from bot.handlers import error_handlers
from bot.handlers import report_actions
from bot.dialogs import menu_dialog


setup_logging("aida")  # Настройка логирования приложения


async def main() -> None:
    """Запускает бота, middleware, диалоги и фоновые задачи."""

    cfg: Config = load_config()  # Читаем конфигурацию из переменных окружения

    # Инициализация бота и парсинга HTML
    bot = Bot(
        token=cfg.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Хранилище FSM в Redis (сейчас не используется, но готово к включению)
    storage = RedisStorage(
        redis=RedisCache(db=0).get_redis(),
        key_builder=DefaultKeyBuilder(with_destiny=True),
        state_ttl=3600,
        data_ttl=3600
    )
    dp = Dispatcher(storage=storage)

    # Глобальные middleware (логирование, БД, локализация, загрузка пользователя)
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(DBSessionMiddleware(session_maker))
    dp.update.middleware(I18nMiddleware())
    dp.update.middleware(UserDBMiddleware())

    # Listener RabbitMQ живет рядом с polling и мягко останавливается в finally.
    rabbit_task = asyncio.create_task(
        rabbit_listener(
            bot=bot,
            rabbit_url=cfg.rabbit.url,
            queue_name=cfg.rabbit.queue,
        ),
        name="rabbit_listener",
    )
    # Роутеры
    dp.include_router(error_handlers.router)   # обработчики ошибок
    dp.include_router(start_handlers.router)   # /start и базовые команды
    dp.include_router(report_actions.router)   # inline-действия по отчетам
    dp.include_router(menu_dialog)             # диалоги меню
    # Инициализация aiogram-dialog
    setup_dialogs(dp)

    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, config=cfg)
    finally:
        # При остановке сначала гасим фоновые задачи, затем закрываем внешние ресурсы.
        rabbit_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await rabbit_task
        with contextlib.suppress(Exception):
            await storage.close()
        with contextlib.suppress(Exception):
            await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
