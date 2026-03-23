import json
import sys
from typing import Any

from loguru import logger


def _serialize_log_record(record: dict[str, Any]) -> str:
    """Собирает плоский JSON-лог, удобный для Promtail и Loki."""
    extra = dict(record.get("extra") or {})
    payload: dict[str, Any] = {
        "timestamp": record["time"].isoformat(),
        "level": record["level"].name,
        "message": record["message"],
        "service": extra.get("service"),
        "logger": record.get("name"),
        "module": record.get("module"),
        "function": record.get("function"),
        "line": record.get("line"),
        "process_id": record["process"].id,
        "thread_id": record["thread"].id,
        "exception": str(record["exception"]) if record.get("exception") else None,
    }

    # Переносим все extra-поля наверх, чтобы их было легко разбирать на стороне
    # promtail/loki без вложенного `record.extra.*`.
    for key, value in extra.items():
        if key not in payload:
            payload[key] = value

    return json.dumps(payload, ensure_ascii=False, default=str) + "\n"


def setup_logging(
    service_name: str = "aida",
    log_level: str = "INFO",
):
    """Настраивает вывод логов в stdout и файл сервиса."""

    logger.remove()

    def filter_logs(record):
        """Пропускает только записи текущего сервиса."""
        return record["extra"].get("service") == service_name

    logger.add(
        sys.stdout,
        format=_serialize_log_record,
        level=log_level,
        enqueue=True,
        backtrace=True,
        filter=filter_logs
    )

    logger.add(
        f"logs/{service_name}.log",
        format=_serialize_log_record,
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        filter=filter_logs,
    )

    logger.configure(
        extra={
            "service": service_name,
            "chat_id": None,
            "user_id": None,
            "telegram_id": None,
            "topic_id": None,
            "message_id": None,
            "callback_data": None,
            "update_type": None,
            "queue": None,
            "post": None,
            "unit_uuid": None,
            "account_id": None,
            "run_id": None,
            "run_status": None,
        }
    )
