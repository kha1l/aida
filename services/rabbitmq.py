"""Фоновый consumer RabbitMQ для доставки готовых payload в Telegram."""

import asyncio
import contextlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone

import aio_pika
from aiogram import Bot
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.report_actions import build_report_keyboard
from config import Config
from database.requests.orders import get_order_account_id_for_unit
from database.requests.settings import get_chat_language, get_default_chat_language
from services.i18n import get_translator
from services.webapp_links import ReportLinkParams, build_report_url, new_request_id


WEBAPP_ACTIONS_BY_POST = {
    "couriers": ("waiting", "later", "certificates", "sectors", "longers"),
    "stationary": ("later_rest", "assembly_rest", "drink_rest"),
}


@dataclass(slots=True)
class RabbitPayload:
    """Нормализованный payload из очереди, который бот отправляет в Telegram."""

    chat_id: int
    text: str
    topic_id: int | None
    post: str | None
    unit_uuid: str | None

    @classmethod
    def from_bytes(cls, raw_body: bytes) -> "RabbitPayload":
        """Декодирует JSON из RabbitMQ и приводит его к удобной структуре."""
        raw_payload = json.loads(raw_body.decode())
        return cls(
            chat_id=raw_payload["chat_id"],
            text=raw_payload["text"],
            topic_id=raw_payload.get("topic_id"),
            post=raw_payload.get("post"),
            unit_uuid=raw_payload.get("unit_uuid") or raw_payload.get("uuid"),
        )


async def _resolve_chat_translator(
    session_maker: async_sessionmaker[AsyncSession] | None,
    chat_id: int,
):
    """Подбирает переводчик для чата по языку, сохраненному в БД."""
    if session_maker is None:
        return lambda message: message

    async with session_maker() as session:
        language = await get_chat_language(session, chat_id)
        if not language:
            language = await get_default_chat_language(session, chat_id)
    return get_translator(language=language or "ru")


async def _build_webapp_urls_by_action(
    payload: RabbitPayload,
    *,
    session_maker: async_sessionmaker[AsyncSession] | None,
    config: Config | None,
) -> dict[str, str]:
    """Готовит Direct Link URLs, чтобы кнопки сразу открывали Telegram Mini App."""
    actions = WEBAPP_ACTIONS_BY_POST.get(payload.post or "")
    if not actions or not payload.unit_uuid or session_maker is None or config is None:
        return {}

    if not config.webapp.report_url or not config.webapp.signing_secret:
        return {}

    async with session_maker() as session:
        account_id = await get_order_account_id_for_unit(
            session,
            chat_id=payload.chat_id,
            post=payload.post or "",
            unit_uuid=payload.unit_uuid,
            topic_id=payload.topic_id,
        )

    if account_id is None:
        logger.bind(
            chat_id=payload.chat_id,
            topic_id=payload.topic_id,
            post=payload.post,
            unit_uuid=payload.unit_uuid,
        ).warning("WebApp links skipped: account_id was not found for report payload")
        return {}

    message_date = datetime.now(timezone.utc).isoformat()
    urls: dict[str, str] = {}
    for action in actions:
        url = build_report_url(
            base_url=config.webapp.report_url,
            direct_link_url=config.webapp.direct_link_url,
            signing_secret=config.webapp.signing_secret,
            ttl_seconds=config.webapp.link_ttl_seconds,
            params=ReportLinkParams(
                request_id=new_request_id(),
                report_type=action,
                unit_uuid=payload.unit_uuid,
                account_id=int(account_id),
                message_date=message_date,
            ),
        )
        if url:
            urls[action] = url
    return urls


async def rabbit_listener(
    bot: Bot,
    rabbit_url: str,
    queue_name: str,
    session_maker: async_sessionmaker[AsyncSession] | None = None,
    config: Config | None = None,
):
    """Слушает очередь RabbitMQ и пересылает сообщения в Telegram."""
    connection = None
    channel = None
    queue = None
    consumer_tag = None

    async def on_message(message: aio_pika.IncomingMessage) -> None:
        payload: RabbitPayload | None = None
        # message.process() сам управляет ack/nack, если внутри не произошло исключение.
        async with message.process():
            try:
                # Формат сообщения:
                # {"chat_id": ..., "text": ..., "topic_id": ..., "post": ..., "unit_uuid": ...}
                payload = RabbitPayload.from_bytes(message.body)
                translate = await _resolve_chat_translator(session_maker, payload.chat_id)
                webapp_urls_by_action = await _build_webapp_urls_by_action(
                    payload,
                    session_maker=session_maker,
                    config=config,
                )
                # Клавиатура подмешивается на стороне бота, чтобы payload из очереди оставался простым.
                keyboard = build_report_keyboard(
                    payload.post,
                    payload.unit_uuid,
                    webapp_urls_by_action=webapp_urls_by_action,
                    translate=translate,
                )

                if payload.post in WEBAPP_ACTIONS_BY_POST and not payload.unit_uuid:
                    logger.bind(
                        chat_id=payload.chat_id,
                        topic_id=payload.topic_id,
                        queue=queue_name,
                        post=payload.post,
                    ).warning("Keyboard skipped: unit_uuid is missing in payload")

                await bot.send_message(
                    chat_id=payload.chat_id,
                    text=payload.text,
                    message_thread_id=payload.topic_id,
                    reply_markup=keyboard,
                )

                logger.bind(
                    chat_id=payload.chat_id,
                    topic_id=payload.topic_id,
                    queue=queue_name,
                    post=payload.post,
                    unit_uuid=payload.unit_uuid,
                ).info(
                    "Message sent successfully",
                    text=payload.text[:200]
                )

            except Exception:
                logger.bind(
                    chat_id=payload.chat_id if payload else None,
                    topic_id=payload.topic_id if payload else None,
                    queue=queue_name,
                    post=payload.post if payload else None,
                    unit_uuid=payload.unit_uuid if payload else None,
                ).exception("Failed to send message")

    try:
        connection = await aio_pika.connect_robust(rabbit_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=15)
        queue = await channel.declare_queue(queue_name, durable=True)
        consumer_tag = await queue.consume(on_message)

        # Держим coroutine живой, пока приложение не пришлет CancelledError.
        await asyncio.Future()
    except asyncio.CancelledError:
        logger.info("Rabbit listener stopped")
        raise
    finally:
        if queue is not None and consumer_tag is not None:
            with contextlib.suppress(Exception):
                await queue.cancel(consumer_tag)
        if channel is not None:
            with contextlib.suppress(Exception):
                await channel.close()
        if connection is not None:
            with contextlib.suppress(Exception):
                await connection.close()
