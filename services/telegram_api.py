"""Защита Telegram API-вызовов от flood control и коротких сетевых сбоев."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import DefaultDict

from aiogram.client.session.middlewares.base import BaseRequestMiddleware, NextRequestMiddlewareType
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
from aiogram.methods.base import TelegramMethod, TelegramType
from loguru import logger
from security_logging import pseudonymize


class TelegramRetryMiddleware(BaseRequestMiddleware):
    """Повторяет Telegram API-запросы при flood control и сериализует их по chat_id."""

    def __init__(
        self,
        *,
        max_retries: int = 4,
        global_limit: int = 4,
        per_chat_min_interval: float = 0.20,
        per_method_min_interval: float = 0.08,
    ) -> None:
        self.max_retries = max_retries
        self.per_chat_min_interval = max(0.0, per_chat_min_interval)
        self.per_method_min_interval = max(0.0, per_method_min_interval)
        self._global_semaphore = asyncio.Semaphore(max(1, global_limit))
        self._chat_locks: DefaultDict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._last_request_at: dict[str, float] = {}

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot,
        method: TelegramMethod[TelegramType],
    ):
        scope = self._request_scope(method)
        method_name = method.__class__.__name__
        async with self._global_semaphore:
            async with self._chat_locks[scope]:
                await self._throttle(scope=scope, method_name=method_name)
                return await self._call_with_retry(make_request, bot, method, scope)

    async def _call_with_retry(
        self,
        make_request: NextRequestMiddlewareType[TelegramType],
        bot,
        method: TelegramMethod[TelegramType],
        scope: str,
    ):
        for attempt in range(1, self.max_retries + 2):
            try:
                result = await make_request(bot, method)
                if attempt > 1:
                    logger.info(
                        "Telegram request succeeded after retry",
                        method=method.__class__.__name__,
                        source_hash=pseudonymize(scope),
                        attempt=attempt,
                    )
                return result
            except TelegramRetryAfter as exc:
                if attempt > self.max_retries:
                    logger.error(
                        "Telegram flood control: retries exhausted",
                        method=method.__class__.__name__,
                        source_hash=pseudonymize(scope),
                        retry_after=float(exc.retry_after),
                        attempt=attempt,
                        max_retries=self.max_retries,
                    )
                    raise
                delay = max(float(exc.retry_after), 0.5)
                logger.warning(
                    "Telegram flood control: retrying request",
                    method=method.__class__.__name__,
                    source_hash=pseudonymize(scope),
                    retry_after=delay,
                    attempt=attempt,
                    max_retries=self.max_retries,
                )
                await asyncio.sleep(delay)
            except TelegramNetworkError as exc:
                if attempt > self.max_retries:
                    logger.error(
                        "Telegram network error: retries exhausted",
                        method=method.__class__.__name__,
                        source_hash=pseudonymize(scope),
                        attempt=attempt,
                        max_retries=self.max_retries,
                        error=str(exc),
                    )
                    raise
                delay = min(0.5 * (2 ** (attempt - 1)), 3.0)
                logger.warning(
                    "Telegram network error: retrying request",
                    method=method.__class__.__name__,
                    source_hash=pseudonymize(scope),
                    retry_in=delay,
                    attempt=attempt,
                    max_retries=self.max_retries,
                    error=str(exc),
                )
                await asyncio.sleep(delay)

    async def _throttle(self, *, scope: str, method_name: str) -> None:
        """Делает небольшую паузу между запросами в один и тот же scope."""
        min_interval = self._scope_min_interval(scope)
        if min_interval <= 0:
            return

        now = time.monotonic()
        last_request_at = self._last_request_at.get(scope)
        if last_request_at is not None:
            elapsed = now - last_request_at
            wait_seconds = min_interval - elapsed
            if wait_seconds > 0:
                logger.debug(
                    "Telegram request throttled",
                    method=method_name,
                    source_hash=pseudonymize(scope),
                    wait_seconds=round(wait_seconds, 3),
                    min_interval=min_interval,
                )
                await asyncio.sleep(wait_seconds)
        self._last_request_at[scope] = time.monotonic()

    def _scope_min_interval(self, scope: str) -> float:
        """Возвращает интервал между запросами для текущего scope."""
        if scope.startswith("chat:"):
            return self.per_chat_min_interval
        return self.per_method_min_interval

    @staticmethod
    def _request_scope(method: TelegramMethod[TelegramType]) -> str:
        """Группирует запросы по chat_id, а если его нет — по типу метода."""
        chat_id = getattr(method, "chat_id", None)
        if chat_id is not None:
            return f"chat:{chat_id}"

        user_id = getattr(method, "user_id", None)
        if user_id is not None:
            return f"user:{user_id}"

        return f"method:{method.__class__.__name__}"
