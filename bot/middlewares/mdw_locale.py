from typing import Callable, Awaitable, Any, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject, CallbackQuery
from services.i18n import get_translator
from sqlalchemy.ext.asyncio import AsyncSession
from database.requests.settings import get_user_settings


class I18nMiddleware(BaseMiddleware):
    """
    Определяет язык по настройкам пользователя и добавляет функцию перевода в data.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Подкладывает переводчик и настройки языка в middleware data."""
        session: AsyncSession = data["session"]

        # Пользователь Telegram (если нет — используем ru по умолчанию)
        tg_user = data.get("event_from_user")
        if not tg_user:
            gettext_fn = get_translator(language="ru")
            data["_"] = gettext_fn
            data["i18n_gettext"] = gettext_fn
            return await handler(event, data)

        event_chat = data.get("event_chat")
        chat_id = event_chat.id if event_chat else None

        # Настройки пользователя из БД (там хранится язык для конкретного chat_id)
        settings = await get_user_settings(session, tg_user)

        country = None
        if settings and chat_id is not None:
            for st in settings:
                st_chat = st.get("chat_id")
                if st_chat == chat_id:
                    country = st.get("country")
                    break
        language = country if country is not None else "ru"
        gettext_fn = get_translator(language=language)
        data["_"] = gettext_fn
        data["i18n_gettext"] = gettext_fn
        data["settings"] = settings

        return await handler(event, data)
