"""CRUD-запросы к таблице `aida.orders`."""
from typing import Iterable, List

from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Orders, Settings
from loguru import logger
from security_logging import pseudonymize


def _optional_eq(column, value):
    return column.is_(None) if value is None else column == value


def _merge_uuids(left: list[str] | None, right: list[str] | None) -> list[str]:
    """Объединяет uuid без дублей, сохраняя исходный порядок."""
    result: list[str] = []
    seen: set[str] = set()
    for value in [*(left or []), *(right or [])]:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


async def get_orders_by_post(
    session: AsyncSession,
    chat_id: int,
    post: str,
    topic_id: int | None = None,
) -> List[Orders]:
    """Получает подписки по типу отчёта (post) и чату."""
    stmt = select(Orders).where(Orders.chat_id == chat_id, Orders.post == post)
    stmt = stmt.where(Orders.topic_id == topic_id) if topic_id is not None else stmt.where(Orders.topic_id.is_(None))
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_order_account_id_for_unit(
    session: AsyncSession,
    *,
    chat_id: int,
    post: str,
    unit_uuid: str,
    topic_id: int | None = None,
) -> int | None:
    """Находит account_id подписки, через которую пришел отчет по заведению."""
    stmt = (
        select(Orders.account_id)
        .where(
            Orders.chat_id == chat_id,
            Orders.post == post,
            Orders.uuids.any(unit_uuid),
            Orders.account_id.is_not(None),
        )
        .limit(1)
    )
    stmt = stmt.where(Orders.topic_id == topic_id) if topic_id is not None else stmt.where(Orders.topic_id.is_(None))
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert_order(
    session: AsyncSession,
    chat_id: int,
    post: str,
    account_id: int | None,
    topic_id: int | None,
    uuids: list[str],
    params: str | None = None,
) -> None:
    """Создаёт или обновляет подписку на отчёт для аккаунта."""
    stmt = select(Orders.id).where(Orders.chat_id == chat_id, Orders.post == post, Orders.account_id == account_id)
    stmt = stmt.where(Orders.topic_id == topic_id) if topic_id is not None else stmt.where(Orders.topic_id.is_(None))
    result = await session.execute(stmt)
    order_id = result.scalar_one_or_none()

    if order_id:
        upd = (
            update(Orders)
            .where(Orders.id == order_id)
            .values(uuids=uuids, params=params, topic_id=topic_id)
        )
        await session.execute(upd)
    else:
        session.add(
            Orders(
                chat_id=chat_id,
                post=post,
                account_id=account_id,
                topic_id=topic_id,
                uuids=uuids,
                params=params,
            )
        )
    await session.commit()
    logger.info(
        "orders upsert",
        chat_hash=pseudonymize(chat_id),
        object=f"subscription:{post}",
    )


async def delete_order(
    session: AsyncSession,
    chat_id: int,
    post: str,
    account_id: int | None,
    topic_id: int | None,
) -> None:
    """Удаляет подписку для указанного аккаунта."""
    stmt = delete(Orders).where(Orders.chat_id == chat_id, Orders.post == post, Orders.account_id == account_id)
    stmt = stmt.where(Orders.topic_id == topic_id) if topic_id is not None else stmt.where(Orders.topic_id.is_(None))
    await session.execute(stmt)
    await session.commit()
    logger.info(
        "orders delete",
        chat_hash=pseudonymize(chat_id),
        object=f"subscription:{post}",
    )


async def delete_orders_for_chat(session: AsyncSession, chat_id: int) -> int:
    """Удаляет все подписки недоступного чата, чтобы не получать повторные delivery errors."""
    result = await session.execute(delete(Orders).where(Orders.chat_id == chat_id))
    await session.commit()
    deleted = result.rowcount or 0
    logger.info(
        "orders delete for unavailable chat",
        chat_hash=pseudonymize(chat_id),
        status=deleted,
    )
    return deleted


async def migrate_orders_chat(session: AsyncSession, old_chat_id: int, new_chat_id: int) -> tuple[int, int]:
    """Переносит подписки Telegram-чата после миграции группы в supergroup."""
    rows = (
        await session.execute(
            select(Orders)
            .where(Orders.chat_id == old_chat_id)
            .order_by(Orders.id)
        )
    ).scalars().all()

    migrated = 0
    merged = 0
    for order in rows:
        target = (
            await session.execute(
                select(Orders)
                .where(
                    Orders.chat_id == new_chat_id,
                    Orders.post == order.post,
                    _optional_eq(Orders.account_id, order.account_id),
                    _optional_eq(Orders.topic_id, order.topic_id),
                )
                .limit(1)
            )
        ).scalar_one_or_none()

        if target is not None:
            target.uuids = _merge_uuids(target.uuids, order.uuids)
            if target.params is None and order.params is not None:
                target.params = order.params
            await session.delete(order)
            merged += 1
        else:
            order.chat_id = new_chat_id
            migrated += 1

    await session.execute(
        update(Settings)
        .where(Settings.chat_id == old_chat_id)
        .values(chat_id=new_chat_id)
    )
    await session.commit()
    logger.info(
        "orders migrate chat",
        source_hash=pseudonymize(old_chat_id),
        chat_hash=pseudonymize(new_chat_id),
        status=migrated + merged,
    )
    return migrated, merged
