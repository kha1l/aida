import asyncio
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import Config, load_config
from aiogram import Bot, Dispatcher
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
from bot.dialogs import menu_dialog


setup_logging("aida")  # Настройка логирования приложения

async def main() -> None:

    cfg: Config = load_config()  # Читаем конфигурацию из переменных окружения

    # Инициализация бота и парсинга HTML
    bot = Bot(
        token=cfg.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # Хранилище FSM в Redis (сейчас не используется, но готово к включению)
    storage = RedisStorage(
        redis=RedisCache(db=0).get_redis(),
        state_ttl=3600,
        data_ttl=3600
    )
    # dp = Dispatcher(storage=storage)
    dp = Dispatcher()

    # Глобальные middleware (логирование, БД, локализация, загрузка пользователя)
    dp.update.middleware(LoggingMiddleware())
    dp.update.middleware(DBSessionMiddleware(session_maker))
    dp.update.middleware(I18nMiddleware())
    dp.update.middleware(UserDBMiddleware())

    # asyncio.create_task(
    #     rabbit_listener(
    #         bot=bot,
    #         rabbit_url=cfg.rabbit.url,
    #         queue_name=cfg.rabbit.queue,
    #     )
    # )
    # Роутеры
    dp.include_router(error_handlers.router)   # обработчики ошибок
    dp.include_router(start_handlers.router)   # /start и базовые команды
    dp.include_router(menu_dialog)             # диалоги меню
    # Инициализация aiogram-dialog
    setup_dialogs(dp)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
