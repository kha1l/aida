from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update
from loguru import logger

class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:

        # Логируем тип апдейта и контекст (чат, пользователь, сообщение)
        log = logger

        try:
            update_type = event.event_type
            if event.message:
                chat_id = event.message.chat.id
                user_id = event.message.from_user.id
                log = log.bind(
                    update_type="message",
                    chat_id=chat_id,
                    user_id=user_id,
                    message_id=event.message.message_id,
                )
                log.info("message", text=event.message.text)

            elif event.callback_query:
                chat_id = (
                    event.callback_query.message.chat.id
                    if event.callback_query.message
                    else None
                )
                user_id = event.callback_query.from_user.id

                log = log.bind(
                    update_type="callback_query",
                    chat_id=chat_id,
                    user_id=user_id,
                    callback_data=event.callback_query.data,
                )
                # Skip logging callbacks to reduce noise

            else:
                log = log.bind(update_type=update_type)
                log.info("update")

            return await handler(event, data)

        except Exception:
            log.exception("failed")
            raise
