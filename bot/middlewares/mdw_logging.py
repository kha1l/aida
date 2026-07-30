from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Update
from loguru import logger
from aiogram_dialog.api.exceptions import OutdatedIntent, UnknownIntent
from security_logging import create_correlation_id, pseudonymize


def _is_start_message(update: Update) -> bool:
    """Проверяет, что update содержит команду `/start`."""
    if not update.message:
        return False
    return (update.message.text or "").strip().startswith("/start")


class LoggingMiddleware(BaseMiddleware):
    """Логирует входящие обновления и ошибки обработки."""
    async def __call__(
        self,
        handler: Callable[[Update, Dict[str, Any]], Awaitable[Any]],
        event: Update,
        data: Dict[str, Any],
    ) -> Any:
        """Оборачивает обработку update логированием контекста."""
        correlation_id = create_correlation_id(f"telegram-update:{event.update_id}")
        # Передаём единый correlation ID следующим middleware и хендлерам.
        # Это позволяет связать audit-событие с обычными техническими логами,
        # не создавая отдельный идентификатор и лишнюю строку на каждом шаге.
        data["request_id"] = correlation_id
        data["trace_id"] = correlation_id
        log = logger.bind(
            request_id=correlation_id,
            trace_id=correlation_id,
        )

        try:
            update_type = event.event_type
            if event.message:
                if _is_start_message(event):
                    chat_id = event.message.chat.id
                    user_id = event.message.from_user.id
                    log = log.bind(
                        update_type="message",
                        chat_hash=pseudonymize(chat_id),
                        user_hash=pseudonymize(user_id),
                        message_id=event.message.message_id,
                    )
                    # Результат проверки `/start` попадёт в security_audit.
                    # Отдельная application-строка здесь была бы дублем.

            elif event.callback_query:
                chat_id = (
                    event.callback_query.message.chat.id
                    if event.callback_query.message
                    else None
                )
                user_id = event.callback_query.from_user.id

                log = log.bind(
                    update_type="callback_query",
                    chat_hash=pseudonymize(chat_id),
                    user_hash=pseudonymize(user_id),
                )
                # Skip logging callbacks to reduce noise

            else:
                log = log.bind(update_type=update_type)
                # Неизвестный успешный update не даёт отдельной строки:
                # bound-контекст всё равно попадёт в лог, если обработка упадёт.

            with logger.contextualize(
                request_id=correlation_id,
                trace_id=correlation_id,
            ):
                return await handler(event, data)

        except (OutdatedIntent, UnknownIntent):
            # Старые dialog intent'ы и потерянный context отдельно обрабатываются
            # в global error handler, поэтому не дублируем traceback здесь.
            raise
        except Exception:
            log.exception("failed")
            raise
