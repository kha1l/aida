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


def _is_start_message(event: TelegramObject) -> bool:
    """Проверяет, что событие является сообщением с командой `/start`."""
    if isinstance(event, Message):
        text = (event.text or "").strip()
        return text.startswith("/start")
    if isinstance(event, Update) and event.message:
        text = (event.message.text or "").strip()
        return text.startswith("/start")
    return False


def _is_callback_event(event: TelegramObject) -> bool:
    """Проверяет, что событие пришло от нажатия inline-кнопки."""
    if isinstance(event, CallbackQuery):
        return True
    return isinstance(event, Update) and event.callback_query is not None


def _needs_user_context(event: TelegramObject) -> bool:
    """Оставляем загрузку контекста только для `/start` и callback-событий."""
    return _is_start_message(event) or _is_callback_event(event)


def _event_chat_id(event: TelegramObject, data: Dict[str, Any]) -> int | None:
    """Возвращает chat_id из middleware data или самого события."""
    event_chat = data.get("event_chat")
    if event_chat is not None:
        return getattr(event_chat, "id", None)
    if isinstance(event, Message):
        return event.chat.id
    if isinstance(event, CallbackQuery) and event.message:
        return event.message.chat.id
    if isinstance(event, Update):
        if event.message:
            return event.message.chat.id
        if event.callback_query and event.callback_query.message:
            return event.callback_query.message.chat.id
    return None


def _event_topic_id(event: TelegramObject) -> int | None:
    """Возвращает message_thread_id для сообщений из топиков."""
    if isinstance(event, Message):
        return getattr(event, "message_thread_id", None)
    if isinstance(event, CallbackQuery) and event.message:
        return getattr(event.message, "message_thread_id", None)
    if isinstance(event, Update):
        if event.message:
            return getattr(event.message, "message_thread_id", None)
        if event.callback_query and event.callback_query.message:
            return getattr(event.callback_query.message, "message_thread_id", None)
    return None


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
        if not _needs_user_context(event):
            return await handler(event, data)

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
            logger.bind(
                chat_id=_event_chat_id(event, data),
                user_id=tg_user.id,
                telegram_id=tg_user.id,
                topic_id=_event_topic_id(event),
            ).warning("Пользователь не найден в базе данных")
            await _send_authorization_required(event, _, user_name=tg_user.full_name)
            return None

        # Кладём контекст в FSM, чтобы не ходить в БД каждый раз
        logger.bind(
            chat_id=_event_chat_id(event, data),
            user_id=ctx.get("user_id") or tg_user.id,
            telegram_id=tg_user.id,
            topic_id=_event_topic_id(event),
        ).success("Пользователь успешно загружен из базы данных")
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
