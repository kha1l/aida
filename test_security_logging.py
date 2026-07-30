import os
import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from security_logging import (
    SECURITY_EVENT_TYPES,
    SERVICE_NAME,
    build_application_log,
    build_security_event,
    create_correlation_id,
    pseudonymize,
    redact_record,
    redact_text,
)

try:
    from loguru import logger as loguru_logger

    from bot.middlewares.mdw_logging import LoggingMiddleware
except ModuleNotFoundError:
    loguru_logger = None
    LoggingMiddleware = None


class SecurityLoggingTests(unittest.TestCase):
    def test_correlation_id_is_stable_and_contains_no_source_identifier(self) -> None:
        first = create_correlation_id("telegram-update:123456789")
        second = create_correlation_id("telegram-update:123456789")

        self.assertEqual(first, second)
        self.assertRegex(first, r"^[0-9a-f]{32}$")
        self.assertNotIn("123456789", first)

    def test_every_security_event_type_has_safe_schema(self) -> None:
        with patch.dict(
            os.environ,
            {"SECURITY_PSEUDONYM_KEY": "synthetic-test-key"},
            clear=False,
        ):
            for event_type in SECURITY_EVENT_TYPES:
                with self.subTest(event_type=event_type):
                    event = build_security_event(
                        event_type,
                        service="test-service",
                        source="synthetic",
                        actor="test@example.invalid",
                        object_name="synthetic-object",
                        result="success",
                        reason_code="synthetic_test",
                        request_id="request-1",
                        trace_id="trace-1",
                    )
                    self.assertEqual(event["event_type"], event_type)
                    self.assertEqual(event["service"], "test-service")
                    self.assertEqual(event["record"]["message"], event_type)
                    self.assertNotIn("test@example.invalid", json.dumps(event))

    def test_security_event_always_has_correlation_ids(self) -> None:
        event = build_security_event(
            "access_denied",
            service=SERVICE_NAME,
            source="synthetic",
            result="denied",
            reason_code="synthetic_test",
        )

        self.assertRegex(event["request_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(event["trace_id"], event["request_id"])

    def test_pseudonym_is_hmac_and_versioned(self) -> None:
        with patch.dict(
            os.environ,
            {
                "SECURITY_PSEUDONYM_KEY": "synthetic-test-key",
                "SECURITY_PSEUDONYM_KEY_VERSION": "test-v1",
            },
            clear=False,
        ):
            value = pseudonymize("123456789")
        self.assertRegex(value or "", r"^test-v1:[0-9a-f]{64}$")

    def test_pseudonym_is_omitted_without_key(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(pseudonymize("123456789"))

    def test_redaction_removes_sensitive_synthetic_values(self) -> None:
        with patch.dict(
            os.environ,
            {"SECURITY_PSEUDONYM_KEY": "synthetic-test-key"},
            clear=False,
        ):
            result = redact_text(
                "Authorization: Bearer synthetic-token "
                "test@example.invalid +7 999 123-45-67 user_id=123456789"
            )
        self.assertNotIn("synthetic-token", result)
        self.assertNotIn("test@example.invalid", result)
        self.assertNotIn("999 123-45-67", result)
        self.assertNotIn("123456789", result)

    def test_redaction_removes_quoted_credentials(self) -> None:
        samples = (
            (
                '{"access_token":"synthetic-json-token"}',
                '{"access_token":"[REDACTED]"}',
            ),
            (
                "{'Authorization': 'Bearer synthetic-dict-token'}",
                "{'Authorization': '[REDACTED]'}",
            ),
            (
                '{"password":"synthetic value with spaces"}',
                '{"password":"[REDACTED]"}',
            ),
            (
                "token = 'synthetic value with spaces'",
                "token=[REDACTED]",
            ),
        )
        for sample, expected in samples:
            with self.subTest(sample=sample):
                result = redact_text(sample)
                self.assertEqual(result, expected)
                self.assertEqual(redact_text(result), expected)

    def test_redaction_does_not_corrupt_pseudonyms(self) -> None:
        with patch.dict(
            os.environ,
            {"SECURITY_PSEUDONYM_KEY": "synthetic-test-key"},
            clear=False,
        ):
            user_hash = pseudonymize("123456789")
            self.assertIsNotNone(user_hash)
            self.assertEqual(redact_text(user_hash), user_hash)
            event = build_application_log(
                {
                    "time": datetime.now(timezone.utc),
                    "level": SimpleNamespace(name="INFO"),
                    "message": "synthetic",
                    "extra": {
                        "service": SERVICE_NAME,
                        "user_hash": user_hash,
                    },
                    "exception": None,
                }
            )
        self.assertEqual(event["user_hash"], user_hash)

    def test_record_extra_uses_allowlist_and_hashes_identifiers(self) -> None:
        record = {
            "message": "synthetic",
            "extra": {
                "service": "test",
                "user_id": 123456789,
                "callback_data": "must-not-survive",
            },
        }
        with patch.dict(
            os.environ,
            {"SECURITY_PSEUDONYM_KEY": "synthetic-test-key"},
            clear=False,
        ):
            redact_record(record)
        self.assertEqual(record["extra"]["service"], "test")
        self.assertRegex(record["extra"]["user_hash"], r"^v1:[0-9a-f]{64}$")
        self.assertNotIn("callback_data", record["extra"])

    def test_application_log_uses_fixed_allowlist(self) -> None:
        event = build_application_log(
            {
                "time": datetime.now(timezone.utc),
                "level": SimpleNamespace(name="INFO"),
                "message": "synthetic",
                "extra": {
                    "service": "test",
                    "request_id": "request-1",
                    "callback_data": "must-not-survive",
                },
                "exception": None,
                "module": "synthetic_module",
                "function": "synthetic_function",
                "line": 42,
                "file": SimpleNamespace(name="synthetic.py"),
            }
        )
        self.assertEqual(event["stream"], "application")
        self.assertEqual(event["service"], "test")
        self.assertEqual(event["request_id"], "request-1")
        self.assertEqual(event["record"]["level"]["name"], "INFO")
        self.assertEqual(event["record"]["message"], "synthetic")
        self.assertEqual(event["record"]["module"], "synthetic_module")
        self.assertEqual(event["record"]["function"], "synthetic_function")
        self.assertEqual(event["record"]["line"], 42)
        self.assertEqual(event["record"]["file"]["name"], "synthetic.py")
        self.assertNotIn("callback_data", event)
        self.assertNotIn("file", event)

    def test_delivery_log_hashes_chat_and_drops_report_body(self) -> None:
        raw_chat_id = "987654321"
        report_body = "Synthetic Employee was late"
        callback_data = "synthetic:callback:payload"
        record = {
            "time": datetime.now(timezone.utc),
            "level": SimpleNamespace(name="INFO"),
            "message": "Message sent successfully",
            "extra": {
                "service": "aida",
                "chat_id": raw_chat_id,
                "text": report_body,
                "callback_data": callback_data,
            },
            "exception": None,
            "module": "services.rabbitmq",
            "function": "on_message",
            "line": 1,
            "file": SimpleNamespace(name="rabbitmq.py"),
        }
        with patch.dict(
            os.environ,
            {
                "SECURITY_PSEUDONYM_KEY": "synthetic-test-key",
                "SECURITY_PSEUDONYM_KEY_VERSION": "test-v1",
            },
            clear=False,
        ):
            redact_record(record)
            event = build_application_log(record)

        serialized = json.dumps(event, ensure_ascii=False)
        self.assertRegex(event["chat_hash"], r"^test-v1:[0-9a-f]{64}$")
        self.assertNotIn(raw_chat_id, serialized)
        self.assertNotIn(report_body, serialized)
        self.assertNotIn(callback_data, serialized)


@unittest.skipIf(LoggingMiddleware is None, "bot runtime dependencies are not installed")
class LoggingMiddlewareTests(unittest.IsolatedAsyncioTestCase):
    async def test_correlation_context_reaches_nested_handler_logs(self) -> None:
        records: list[dict] = []
        handler_data: dict = {}
        sink_id = loguru_logger.add(
            lambda message: records.append(dict(message.record)),
            filter=lambda record: record["message"] == "nested handler log",
        )

        async def handler(event, data):
            handler_data.update(data)
            loguru_logger.info("nested handler log")
            return "ok"

        event = SimpleNamespace(
            update_id=123456789,
            event_type="synthetic",
            message=None,
            callback_query=None,
        )
        try:
            result = await LoggingMiddleware()(handler, event, {})
        finally:
            loguru_logger.remove(sink_id)

        self.assertEqual(result, "ok")
        self.assertEqual(len(records), 1)
        extra = records[0]["extra"]
        self.assertRegex(extra["request_id"], r"^[0-9a-f]{32}$")
        self.assertEqual(extra["trace_id"], extra["request_id"])
        self.assertNotIn(str(event.update_id), extra["request_id"])
        self.assertEqual(handler_data["request_id"], extra["request_id"])
        self.assertEqual(handler_data["trace_id"], extra["trace_id"])

    async def test_ordinary_update_adds_no_success_log_noise(self) -> None:
        middleware_records: list[dict] = []
        sink_id = loguru_logger.add(
            lambda message: middleware_records.append(dict(message.record)),
            filter=lambda record: record["module"] == "mdw_logging",
        )

        async def handler(event, data):
            return "ok"

        event = SimpleNamespace(
            update_id=123456789,
            event_type="synthetic",
            message=None,
            callback_query=None,
        )
        try:
            result = await LoggingMiddleware()(handler, event, {})
        finally:
            loguru_logger.remove(sink_id)

        self.assertEqual(result, "ok")
        self.assertEqual(middleware_records, [])


@unittest.skipIf(LoggingMiddleware is None, "bot runtime dependencies are not installed")
class AuthAuditTests(unittest.IsolatedAsyncioTestCase):
    @staticmethod
    def _data() -> dict:
        return {
            "session": object(),
            "state": SimpleNamespace(
                get_data=AsyncMock(return_value={}),
                update_data=AsyncMock(),
            ),
            "event_from_user": SimpleNamespace(
                id=123456789,
                full_name="Synthetic User",
            ),
            "request_id": "request-1",
            "trace_id": "trace-1",
        }

    async def test_start_records_one_auth_success_after_context_check(self) -> None:
        from bot.middlewares.mdw_database import UserDBMiddleware

        handler = AsyncMock(return_value="ok")
        data = self._data()
        with (
            patch(
                "bot.middlewares.mdw_database._needs_user_context",
                return_value=True,
            ),
            patch(
                "bot.middlewares.mdw_database._is_start_message",
                return_value=True,
            ),
            patch(
                "bot.middlewares.mdw_database.get_user_context",
                new_callable=AsyncMock,
                return_value={"user_id": 42},
            ),
            patch(
                "bot.middlewares.mdw_database.emit_security_event",
            ) as emit_event,
        ):
            result = await UserDBMiddleware()(handler, object(), data)

        self.assertEqual(result, "ok")
        emit_event.assert_called_once_with(
            "auth_succeeded",
            service=SERVICE_NAME,
            source="telegram",
            actor=123456789,
            object_name="bot_session",
            result="success",
            reason_code="user_context_verified",
            request_id="request-1",
            trace_id="trace-1",
        )

    async def test_start_records_one_auth_failure(self) -> None:
        from bot.middlewares.mdw_database import UserDBMiddleware

        handler = AsyncMock()
        data = self._data()
        with (
            patch(
                "bot.middlewares.mdw_database._needs_user_context",
                return_value=True,
            ),
            patch(
                "bot.middlewares.mdw_database._is_start_message",
                return_value=True,
            ),
            patch(
                "bot.middlewares.mdw_database.get_user_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "bot.middlewares.mdw_database._send_authorization_required",
                new_callable=AsyncMock,
            ),
            patch(
                "bot.middlewares.mdw_database.emit_security_event",
            ) as emit_event,
        ):
            result = await UserDBMiddleware()(handler, object(), data)

        self.assertIsNone(result)
        handler.assert_not_awaited()
        emit_event.assert_called_once_with(
            "auth_failed",
            service=SERVICE_NAME,
            source="telegram",
            actor=123456789,
            object_name="bot_session",
            result="failure",
            reason_code="user_not_registered",
            request_id="request-1",
            trace_id="trace-1",
        )

    async def test_callback_denial_is_a_single_access_event(self) -> None:
        from bot.middlewares.mdw_database import UserDBMiddleware

        data = self._data()
        with (
            patch(
                "bot.middlewares.mdw_database._needs_user_context",
                return_value=True,
            ),
            patch(
                "bot.middlewares.mdw_database._is_start_message",
                return_value=False,
            ),
            patch(
                "bot.middlewares.mdw_database.get_user_context",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "bot.middlewares.mdw_database._send_authorization_required",
                new_callable=AsyncMock,
            ),
            patch(
                "bot.middlewares.mdw_database.emit_security_event",
            ) as emit_event,
        ):
            await UserDBMiddleware()(AsyncMock(), object(), data)

        emit_event.assert_called_once_with(
            "access_denied",
            service=SERVICE_NAME,
            source="telegram",
            actor=123456789,
            object_name="bot_session",
            result="denied",
            reason_code="user_context_missing",
            request_id="request-1",
            trace_id="trace-1",
        )

    async def test_cached_context_creates_no_duplicate_audit_event(self) -> None:
        from bot.middlewares.mdw_database import UserDBMiddleware

        handler = AsyncMock(return_value="ok")
        data = self._data()
        data["state"].get_data = AsyncMock(
            return_value={"ctx": {"user_id": 42}},
        )
        with (
            patch(
                "bot.middlewares.mdw_database._needs_user_context",
                return_value=True,
            ),
            patch(
                "bot.middlewares.mdw_database.get_user_context",
                new_callable=AsyncMock,
            ) as get_context,
            patch(
                "bot.middlewares.mdw_database.emit_security_event",
            ) as emit_event,
        ):
            result = await UserDBMiddleware()(handler, object(), data)

        self.assertEqual(result, "ok")
        get_context.assert_not_awaited()
        emit_event.assert_not_called()


class EncryptedFieldsConfigTests(unittest.TestCase):
    def test_secret_key_is_loaded_from_dotenv_without_mutating_os_environ(self) -> None:
        from database.encrypted_fields import _get_secret_key

        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "SECRET_KEY_AUTH=synthetic-dotenv-key\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {}, clear=True):
                self.assertEqual(
                    _get_secret_key(str(env_path)),
                    "synthetic-dotenv-key",
                )
                self.assertNotIn("SECRET_KEY_AUTH", os.environ)

    def test_exported_secret_key_takes_precedence_over_dotenv(self) -> None:
        from database.encrypted_fields import _get_secret_key

        with TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "SECRET_KEY_AUTH=synthetic-dotenv-key\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {"SECRET_KEY_AUTH": "synthetic-exported-key"},
                clear=True,
            ):
                self.assertEqual(
                    _get_secret_key(str(env_path)),
                    "synthetic-exported-key",
                )


if __name__ == "__main__":
    unittest.main()
