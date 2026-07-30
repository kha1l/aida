from typing import Callable, Awaitable, Dict, Any
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
from database.requests.users import get_user_context
from aiogram.fsm.context import FSMContext
from bot.keyboards.info import new_account
from bot.dialogs.texts import MenuTexts
from security_logging import SERVICE_NAME, emit_security_event
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
            is_auth_attempt = _is_start_message(event)
            emit_security_event(
                "auth_failed" if is_auth_attempt else "access_denied",
                service=SERVICE_NAME,
                source="telegram",
                actor=tg_user.id,
                object_name="bot_session",
                result="failure" if is_auth_attempt else "denied",
                reason_code=(
                    "user_not_registered"
                    if is_auth_attempt
                    else "user_context_missing"
                ),
                request_id=data.get("request_id"),
                trace_id=data.get("trace_id"),
            )
            await _send_authorization_required(event, _, user_name=tg_user.full_name)
            return None

        # Успешную проверку пишем только при создании новой bot-session через
        # `/start`. Для callback-событий и уже закешированного FSM-контекста
        # отдельный audit-log не нужен: это убирает дубли и сохраняет сигнал.
        if _is_start_message(event):
            emit_security_event(
                "auth_succeeded",
                service=SERVICE_NAME,
                source="telegram",
                actor=tg_user.id,
                object_name="bot_session",
                result="success",
                reason_code="user_context_verified",
                request_id=data.get("request_id"),
                trace_id=data.get("trace_id"),
            )

        # Кладём контекст в FSM, чтобы не ходить в БД каждый раз.
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
