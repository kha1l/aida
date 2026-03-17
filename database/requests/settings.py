from typing import Any

from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import User
from database.requests.users import get_user_id
from database.models import Settings
from sqlalchemy import update


async def get_user_settings(session: AsyncSession, tg_user: TelegramObject) -> list[dict[str, Any]] | None:
    """Возвращает настройки пользователя (включая язык по chat_id)."""
    user_id = await get_user_id(session, tg_user)
    if not user_id:
        return None

    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.settings))
    )

    result = await session.execute(stmt)
    user: User = result.scalar_one()

    settings = []
    for st in user.settings:
        settings.append({
            "id": st.id,
            "country": st.country,
            "users": st.user_id,
            "chat_id": st.chat_id,
        })

    return settings


async def set_chat_language(session: AsyncSession, chat_id: int, country: str) -> None:
    """Обновляет язык (country) для конкретного чата."""
    stmt = (
        update(Settings)
        .where(Settings.chat_id == chat_id)
        .values(country=country)
    )
    await session.execute(stmt)
    await session.commit()
