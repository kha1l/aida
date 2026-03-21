from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from database.requests.users import get_user_context
from loguru import logger
from aiogram.fsm.context import FSMContext
from bot.keyboards.info import new_account
from bot.dialogs.texts import MenuTexts
from services.i18n import get_translator, tr


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
        _ = get_translator(data)
        settings = data.get("settings")

        # Если пользователя нет в БД — не пускаем дальше в /start и сразу
        # показываем понятное сообщение с кнопкой авторизации.
        if not ctx:
            logger.warning(
                "Пользователь не найден в базе данных",
                telegram_id=tg_user.id,
            )
            await _send_authorization_required(event, _, user_name=tg_user.full_name)
            return None

        # Кладём контекст в FSM, чтобы не ходить в БД каждый раз
        logger.success(
            "Пользователь успешно загружен из базы данных",
            telegram_id=tg_user.id,
            user_id=ctx.get("user_id"),
        )
        # Контекст нужен не только для следующих апдейтов из FSM,
        # но и прямо для текущего handler (`/start` и другие entry-point'ы).
        data["ctx"] = ctx
        if settings is not None:
            data["settings"] = settings
        await state.update_data(
            ctx=ctx,
            settings=settings
        )

        return await handler(event, data)


async def _send_authorization_required(
    event: TelegramObject,
    _: Callable[[str], str],
    *,
    user_name: str,
) -> None:
    """Отправляет сообщение о необходимости авторизации для message/callback/update."""
    text = tr(_, MenuTexts.AUTH_REQUIRED_MESSAGE, user_name=user_name)
    keyboard = new_account(_)

    if isinstance(event, Message):
        await event.answer(text=text, reply_markup=keyboard)
        return

    if isinstance(event, CallbackQuery):
        target_message = event.message
        if target_message:
            await target_message.answer(text=text, reply_markup=keyboard)
        else:
            await event.answer()
        return

    if isinstance(event, Update):
        if event.message:
            await event.message.answer(text=text, reply_markup=keyboard)
            return
        if event.callback_query and event.callback_query.message:
            await event.callback_query.message.answer(text=text, reply_markup=keyboard)
            return
