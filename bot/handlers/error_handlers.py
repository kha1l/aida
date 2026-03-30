"""Обработчики ошибок Telegram-бота."""
import asyncio

from aiogram import Router
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramConflictError,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramNotFound,
    TelegramRetryAfter,
)
from aiogram.types import ErrorEvent
from aiogram_dialog.api.exceptions import OutdatedIntent, UnknownIntent
from loguru import logger


router = Router()  # Роутер для обработки ошибок


def _bind_event_log(event: ErrorEvent):
    """Привязка контекста к логам (чат, пользователь, тип обновления)."""
    log = logger
    update = event.update
    if not update:
        return log.bind(update_type="unknown")
    if update.message:
        return log.bind(
            update_type="message",
            chat_id=update.message.chat.id,
            user_id=update.message.from_user.id if update.message.from_user else None,
            message_id=update.message.message_id,
        )
    if update.callback_query:
        return log.bind(
            update_type="callback_query",
            chat_id=update.callback_query.message.chat.id if update.callback_query.message else None,
            user_id=update.callback_query.from_user.id if update.callback_query.from_user else None,
            callback_data=update.callback_query.data,
        )
    return log.bind(update_type=update.event_type)


@router.error()
async def telegram_error_handler(event: ErrorEvent) -> bool:
    """Глобальный обработчик ошибок Telegram API, чтобы бот не падал."""
    exc = event.exception
    log = _bind_event_log(event)

    if isinstance(exc, TelegramRetryAfter):
        log.warning("Telegram flood control", retry_after=exc.retry_after)
        await asyncio.sleep(exc.retry_after)
        return True

    if isinstance(exc, TelegramNetworkError):
        log.warning("Telegram network error", error=str(exc))
        return True

    if isinstance(
        exc,
        (
            TelegramBadRequest,
            TelegramForbiddenError,
            TelegramNotFound,
            TelegramConflictError,
        ),
    ):
        log.warning("Telegram API warning", error=str(exc), exc_type=type(exc).__name__)
        return True

    if isinstance(exc, TelegramAPIError):
        log.error("Telegram API error", error=str(exc), exc_type=type(exc).__name__)
        return True

    # Пользователь нажал на старую inline-кнопку из уже обновленного dialog stack
    # или контекст диалога уже исчез из storage после рестарта/TTL.
    # Для aiogram_dialog это штатный UX-кейс, поэтому отвечаем мягко и не шумим traceback'ом.
    if isinstance(exc, (OutdatedIntent, UnknownIntent)):
        log.warning("Stale dialog intent", error=str(exc), exc_type=type(exc).__name__)
        callback = event.update.callback_query if event.update else None
        if callback is not None:
            try:
                await callback.answer(
                    "Это меню устарело. Откройте его заново.",
                    show_alert=False,
                )
            except TelegramAPIError:
                log.debug("Failed to answer outdated callback")
        return True

    log.opt(exception=exc).error("Unhandled error")
    return True
