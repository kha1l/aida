from typing import Callable, Awaitable, Any, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from services.i18n import get_translator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from database.requests.settings import (
    get_chat_language,
    get_default_user_language,
    get_user_settings,
)
from loguru import logger


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

        try:
            # Сначала смотрим язык, закрепленный за текущим chat_id.
            # Это позволяет разным чатам/топикам жить на разных языках независимо
            # от персональных настроек пользователя.
            chat_language = await get_chat_language(session, chat_id) if chat_id is not None else None

            # Настройки пользователя дополнительно оставляем в middleware data —
            # они еще нужны другим частям интерфейса.
            settings = await get_user_settings(session, tg_user)

            if chat_language:
                language = chat_language
            else:
                # Если для текущего чата язык еще не сохранен, в личке и при первом
                # контакте берем дефолт из доступов пользователя (`io` -> `ru`, `com` -> `en`).
                language = await get_default_user_language(session, tg_user)
        except SQLAlchemyError as exc:
            logger.warning(
                "Не удалось загрузить язык чата из БД, используем ru по умолчанию",
                chat_id=chat_id,
                telegram_id=tg_user.id,
                error=str(exc),
            )
            language = "ru"
            settings = None
        gettext_fn = get_translator(language=language)
        data["_"] = gettext_fn
        data["i18n_gettext"] = gettext_fn
        data["settings"] = settings

        return await handler(event, data)
