from typing import Any
from aiogram.types import TelegramObject
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from dataclasses import dataclass

from database.models import User, UserAccount, Account, Token, Subscribe


@dataclass
class UserData:
    tg_user: TelegramObject
    session: AsyncSession

    async def _get_user_id(self) -> int | None:
        stmt = select(User.id).where(
            User.platform == "telegram",
            User.platform_id == self.tg_user.id,
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user_data(self) -> dict[str, Any] | None:
        user_id = await self._get_user_id()
        if not user_id:
            return None

        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.accounts)
                .selectinload(UserAccount.account)
                .selectinload(Account.tokens)
                .selectinload(Token.subscribes)
                .selectinload(Subscribe.unit),
            )
        )

        result = await self.session.execute(stmt)
        user: User = result.scalar_one()

        accounts = []
        properties = []
        units = []

        for ua in user.accounts:
            acc = ua.account
            if not acc or not acc.active:
                continue

            accounts.append({
                "id": acc.id,
                "name": acc.name,
            })

            if acc.properties:
                properties.append(acc.properties)

            for token in acc.tokens:
                for sub in token.subscribes:
                    if sub.unit:
                        units.append({
                            "uuid": sub.unit.uuid,
                            "name": sub.unit.name,
                            "country": sub.unit.country,
                        })

        return {
            "user_id": user.id,
            "accounts": accounts,
            "properties": properties,
            "units": units,
        }

    async def get_user_settings(self) -> list[dict[str, Any]] | None:
        user_id = await self._get_user_id()
        if not user_id:
            return None

        stmt = (
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.settings))
        )

        result = await self.session.execute(stmt)
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
