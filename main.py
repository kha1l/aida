import asyncio
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import Config, load_config
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from services.rabbitmq import rabbit_listener
from middlewares.mdw_logging import LoggingMiddleware
from middlewares.mdw_database import UserDBMiddleware, DBSessionMiddleware
from middlewares.mdw_locale import I18nMiddleware
from logger import setup_logging
from database.engine import session_maker
from services.cache import RedisCache
from handlers import start_handlers


setup_logging("aida")

async def main() -> None:

    cfg: Config = load_config()

    bot = Bot(
        token=cfg.bot.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    storage = RedisStorage(
        redis=RedisCache(db=0).get_redis(),
        state_ttl=3600,
        data_ttl=3600
    )
    dp = Dispatcher(storage=storage)

    dp.update.middleware(LoggingMiddleware())

    start_handlers.router.message.middleware(DBSessionMiddleware(session_maker))
    start_handlers.router.message.middleware(I18nMiddleware())
    start_handlers.router.message.middleware(
        UserDBMiddleware()
    )

    asyncio.create_task(
        rabbit_listener(
            bot=bot,
            rabbit_url=cfg.rabbit.url,
            queue_name=cfg.rabbit.queue,
        )
    )
    dp.include_router(start_handlers.router)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())