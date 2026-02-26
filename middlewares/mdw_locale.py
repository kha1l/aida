from typing import Callable, Awaitable, Any, Dict
from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject
from services.i18n import setup_i18n
from sqlalchemy.ext.asyncio import AsyncSession
from database.requests.user_data import UserData


class I18nMiddleware(BaseMiddleware):
    """
    По сохранённым настройкам получает функцию перевода для текстов.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        message: Message,
        data: Dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]

        tg_user = data.get("event_from_user")
        if not tg_user:
            return await handler(message, data)
        chat_id = message.chat.id

        user_data = UserData(tg_user, session)
        settings = await user_data.get_user_settings()

        country = None
        if settings:
            for st in settings:
                st_chat = st.get("chat_id")
                if st_chat == chat_id:
                    country = st.get("country")
                    break
        language = country if country is not None else 'ru'
        locales = setup_i18n(language=language)
        data['_'] = locales.gettext
        data["settings"] = settings

        return await handler(message, data)
