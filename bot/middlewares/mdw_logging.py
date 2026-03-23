from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update
from loguru import logger


def _is_start_message(update: Update) -> bool:
    """Проверяет, что update содержит команду `/start`."""
    if not update.message:
        return False
    return (update.message.text or "").strip().startswith("/start")


def _extract_log_context(event: Update) -> dict[str, Any]:
    """Собирает общий контекст апдейта для всех логов внутри обработки."""
    context: dict[str, Any] = {
        "update_type": event.event_type,
        "chat_id": None,
        "user_id": None,
        "telegram_id": None,
        "topic_id": None,
        "message_id": None,
        "callback_data": None,
    }

    if event.message:
        from_user = event.message.from_user
        context.update(
            {
                "update_type": "message",
                "chat_id": event.message.chat.id,
                "user_id": from_user.id if from_user else None,
                "telegram_id": from_user.id if from_user else None,
                "topic_id": getattr(event.message, "message_thread_id", None),
                "message_id": event.message.message_id,
            }
        )
        return context

    if event.callback_query:
        message = event.callback_query.message
        from_user = event.callback_query.from_user
        context.update(
            {
                "update_type": "callback_query",
                "chat_id": message.chat.id if message else None,
                "user_id": from_user.id if from_user else None,
                "telegram_id": from_user.id if from_user else None,
                "topic_id": getattr(message, "message_thread_id", None) if message else None,
                "message_id": message.message_id if message else None,
                "callback_data": event.callback_query.data,
            }
        )

    return context


class LoggingMiddleware(BaseMiddleware):
    """Логирует входящие обновления и ошибки обработки."""
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """Оборачивает обработку update логированием контекста."""
        context = _extract_log_context(event)
        log = logger.bind(**context)

        try:
            with logger.contextualize(**context):
                if event.message:
                    if _is_start_message(event):
                        log.info("message", text=event.message.text)
                elif event.callback_query:
                    # Callback'и специально не дублируем отдельной info-строкой,
                    # но их контекст уже попадет во все внутренние логи хендлеров.
                    pass
                else:
                    log.info("update")

                return await handler(event, data)

        except Exception:
            log.exception("failed")
            raise
