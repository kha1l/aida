import asyncio
import contextlib
import json
import aio_pika
from aiogram import Bot
from loguru import logger

from bot.keyboards.report_actions import build_report_keyboard


async def rabbit_listener(bot: Bot, rabbit_url: str, queue_name: str):
    """Слушает очередь RabbitMQ и пересылает сообщения в Telegram."""
    connection = None
    channel = None
    queue = None
    consumer_tag = None

    async def on_message(message: aio_pika.IncomingMessage) -> None:
        payload = {}
        async with message.process():
            try:
                # Формат сообщения:
                # {"chat_id": ..., "text": ..., "topic_id": ..., "post": ..., "unit_uuid": ...}
                payload = json.loads(message.body.decode())

                chat_id = payload["chat_id"]
                topic_id = payload.get("topic_id")
                post = payload.get("post")
                text = payload["text"]
                unit_uuid = payload.get("unit_uuid") or payload.get("uuid")
                keyboard = build_report_keyboard(post, unit_uuid)

                if post and not unit_uuid:
                    logger.bind(
                        chat_id=chat_id,
                        topic_id=topic_id,
                        queue=queue_name,
                        post=post,
                    ).warning("Keyboard skipped: unit_uuid is missing in payload")

                await bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    message_thread_id=topic_id,
                    reply_markup=keyboard,
                )

                logger.bind(
                    chat_id=chat_id,
                    topic_id=topic_id,
                    queue=queue_name,
                    post=post,
                    unit_uuid=unit_uuid,
                ).info(
                    "Message sent successfully",
                    text=text[:200]
                )

            except Exception:
                logger.bind(
                    chat_id=payload.get("chat_id"),
                    topic_id=payload.get("topic_id"),
                    queue=queue_name,
                    post=payload.get("post"),
                    unit_uuid=payload.get("unit_uuid") or payload.get("uuid"),
                ).exception("Failed to send message")

    try:
        connection = await aio_pika.connect_robust(rabbit_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=15)
        queue = await channel.declare_queue(queue_name, durable=True)
        consumer_tag = await queue.consume(on_message)

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
