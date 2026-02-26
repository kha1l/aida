import json
import aio_pika
from aiogram import Bot
from loguru import logger


async def rabbit_listener(bot: Bot, rabbit_url: str, queue_name: str):
    connection = await aio_pika.connect_robust(rabbit_url)
    channel = await connection.channel()

    await channel.set_qos(prefetch_count=15)

    queue = await channel.declare_queue(queue_name, durable=True)

    async with queue.iterator() as queue_iter:
        async for message in queue_iter:
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())

                    chat_id = payload["chat_id"]
                    topic_id = payload.get("topic_id")
                    text = payload["text"]

                    await bot.send_message(
                        chat_id=chat_id,
                        text=text,
                        message_thread_id=topic_id,
                    )

                    logger.bind(
                        chat_id=chat_id,
                        topic_id=topic_id,
                        queue=queue_name
                    ).info(
                        "Message sent successfully",
                        text=text[:200]
                    )


                except Exception:
                    logger.bind(chat_id=payload.get("chat_id"),
                                topic_id=payload.get("topic_id"),
                                queue=queue_name).exception(
                        "Failed to send message"
                    )
