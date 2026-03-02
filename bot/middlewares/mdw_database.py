from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from database.requests.user_data import UserData
from loguru import logger
from aiogram.fsm.context import FSMContext
from bot.keyboards.info import new_account


class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        self.session_maker = session_maker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        message: Message,
        data: Dict[str, Any],
    ) -> Any:
        async with self.session_maker() as session:
            data["session"] = session
            return await handler(message, data)


class UserDBMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        message: Message,
        data: Dict[str, Any]
    ) -> Any:

        session: AsyncSession = data["session"]
        state: FSMContext = data.get("state")

        if not state:
            return await handler(message, data)

        fsm_data = await state.get_data()
        ctx = fsm_data.get("ctx")

        if ctx:
            data["ctx"] = ctx
            return await handler(message, data)

        tg_user = data.get("event_from_user")
        if not tg_user:
            return await handler(message, data)

        user_data = UserData(tg_user, session)
        ctx = await user_data.get_user_data()
        _ = data.get("_")
        settings = data.get("settings")

        if not ctx:
            logger.warning(
                "Пользователь не найден в базе данных",
                telegram_id=tg_user.id,
            )
            return await message.answer(
                text=_(
                    f'Привет, {tg_user.full_name}\n\n'
                    f'Я - Aida. Помогаю удаленно управлять рестораном '
                    f'или сетью ресторанов Dodo Brands и принимать '
                    f'правильные управленческие решения. 🗃️'
                ),
                reply_markup=new_account(_)
            )

        logger.success(
            "Пользователь успешно загружен из базы данных",
            telegram_id=tg_user.id,
            user_id=ctx.get("user_id"),
        )
        await state.update_data(
            ctx=ctx,
            settings=settings
        )

        return await handler(message, data)
