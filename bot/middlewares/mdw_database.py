from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from database.requests.users import get_user_context
from loguru import logger
from aiogram.fsm.context import FSMContext
from bot.keyboards.info import new_account


class DBSessionMiddleware(BaseMiddleware):
    """Создаёт AsyncSession и кладёт его в data для всех хендлеров."""
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        """Сохраняет фабрику сессий для последующего создания AsyncSession."""
        self.session_maker = session_maker

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Открывает сессию БД на время обработки одного события."""
        async with self.session_maker() as session:
            data["session"] = session
            return await handler(event, data)


class UserDBMiddleware(BaseMiddleware):
    """Подгружает данные пользователя из БД и сохраняет в FSM."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        """Заполняет контекст пользователя или показывает онбординг."""

        session: AsyncSession = data["session"]
        state: FSMContext = data.get("state")

        if not state:
            return await handler(event, data)

        fsm_data = await state.get_data()
        ctx = fsm_data.get("ctx")

        # Если контекст уже есть в FSM — используем его повторно
        if ctx:
            data["ctx"] = ctx
            return await handler(event, data)

        tg_user = data.get("event_from_user")
        if not tg_user:
            return await handler(event, data)

        # Загружаем контекст пользователя (аккаунты, заведения и т.д.)
        ctx = await get_user_context(session, tg_user)
        value = data.get("i18n_gettext") or data.get("_")
        _ = value if callable(value) else (lambda s: s)
        settings = data.get("settings")

        # Если пользователя нет в БД — показываем онбординг с кнопками
        if not ctx:
            logger.warning(
                "Пользователь не найден в базе данных",
                telegram_id=tg_user.id,
            )
            if isinstance(event, Message):
                return await event.answer(
                    text=_(
                        f'Привет, {tg_user.full_name}\n\n'
                        f'Я - Aida. Помогаю удаленно управлять рестораном '
                        f'или сетью ресторанов Dodo Brands и принимать '
                        f'правильные управленческие решения. 🗃️'
                    ),
                    reply_markup=new_account(_)
                )
            if isinstance(event, CallbackQuery) and event.message:
                return await event.message.answer(
                    text=_(
                        f'Привет, {tg_user.full_name}\n\n'
                        f'Я - Aida. Помогаю удаленно управлять рестораном '
                        f'или сетью ресторанов Dodo Brands и принимать '
                        f'правильные управленческие решения. 🗃️'
                    ),
                    reply_markup=new_account(_)
                )
            return await handler(event, data)

        # Кладём контекст в FSM, чтобы не ходить в БД каждый раз
        logger.success(
            "Пользователь успешно загружен из базы данных",
            telegram_id=tg_user.id,
            user_id=ctx.get("user_id"),
        )
        await state.update_data(
            ctx=ctx,
            settings=settings
        )

        return await handler(event, data)
