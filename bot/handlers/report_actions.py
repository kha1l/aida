"""Обработчики inline-действий для запуска отчетов и скрытия сообщений."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from loguru import logger

from bot.keyboards.report_actions import (
    DrinkThresholdCallback,
    HIDE_REPORT_CALLBACK,
    ReportActionCallback,
    WaitingThresholdCallback,
    build_drink_threshold_keyboard,
    build_report_keyboard,
    build_waiting_threshold_keyboard,
)
from config import Config, load_config
from services.dagster import DagsterClient, DagsterLaunchError
from services.i18n import tr


router = Router()
def _is_expired_callback_error(exc: TelegramBadRequest) -> bool:
    text = str(exc).lower()
    return "query is too old" in text or "query id is invalid" in text


async def _safe_callback_answer(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    """Отвечает на callback без падения на истекшем query id."""
    try:
        await callback.answer(text, show_alert=show_alert)
    except TelegramBadRequest as exc:
        if _is_expired_callback_error(exc):
            logger.info("Skip expired callback answer", error=str(exc))
            return
        raise


DIRECT_REPORT_ACTIONS = (
    "certificates",
    "later",
    "sectors",
    "longers",
    "later_rest",
    "assembly_rest",
)


@dataclass(frozen=True, slots=True)
class ManualReportLaunchConfig:
    job_name: str
    op_name: str
    success_popup: str
    launch_error_popup: str
    log_label: str


MANUAL_REPORT_CONFIGS = {
    "certificates": ManualReportLaunchConfig(
        job_name="certificates_job",
        op_name="certificates_op",
        success_popup="Starting certificate collection...",
        launch_error_popup="Unable to start certificate report",
        log_label="Certificates",
    ),
    "later": ManualReportLaunchConfig(
        job_name="later_job",
        op_name="later_op",
        success_popup="Starting late / missed shift collection...",
        launch_error_popup="Unable to start late / missed shift report",
        log_label="Later",
    ),
    "waiting": ManualReportLaunchConfig(
        job_name="waiting_job",
        op_name="waiting_op",
        success_popup="Starting courier waiting collection...",
        launch_error_popup="Unable to start courier waiting report",
        log_label="Waiting",
    ),
    "sectors": ManualReportLaunchConfig(
        job_name="sectors_job",
        op_name="sectors_op",
        success_popup="Starting sector report collection...",
        launch_error_popup="Unable to start delivery sectors report",
        log_label="Sectors",
    ),
    "longers": ManualReportLaunchConfig(
        job_name="longers_job",
        op_name="longers_op",
        success_popup="Starting long delivery report collection...",
        launch_error_popup="Unable to start long delivery report",
        log_label="Longers",
    ),
    "later_rest": ManualReportLaunchConfig(
        job_name="later_rest_job",
        op_name="later_rest_op",
        success_popup="Starting long dine-in order report collection...",
        launch_error_popup="Unable to start long dine-in order report",
        log_label="LaterRest",
    ),
    "assembly_rest": ManualReportLaunchConfig(
        job_name="assembly_rest_job",
        op_name="assembly_rest_op",
        success_popup="Starting slow order assembly report collection...",
        launch_error_popup="Unable to start slow order assembly report",
        log_label="AssemblyRest",
    ),
    "drink_rest": ManualReportLaunchConfig(
        job_name="drink_rest_job",
        op_name="drink_rest_op",
        success_popup="Starting slow drink report collection...",
        launch_error_popup="Unable to start slow drink report",
        log_label="DrinkRest",
    ),
}
THRESHOLD_KEYBOARD_CONFIGS = {
    "waiting": (
        build_waiting_threshold_keyboard,
        "Choose waiting threshold",
        "Unable to show waiting threshold",
        "Failed to show waiting threshold keyboard",
    ),
    "drink_rest": (
        build_drink_threshold_keyboard,
        "Choose time threshold",
        "Unable to show time threshold",
        "Failed to show drink threshold keyboard",
    ),
}


def _find_unit(ctx: dict[str, Any], unit_uuid: str) -> dict[str, Any] | None:
    """Ищет заведение в пользовательском контексте, загруженном middleware."""
    for unit in ctx.get("units", []):
        if unit.get("uuid") == unit_uuid:
            return unit
    return None


def _build_dagster_client(config: Config) -> DagsterClient:
    """Создает Dagster-клиент для запуска manual-job'ов из inline-отчетов."""
    return DagsterClient.from_settings(config.dagster)


async def _restore_report_keyboard(
    callback: CallbackQuery,
    *,
    post: str,
    unit_uuid: str,
    log_label: str,
    extra_log_context: dict[str, Any] | None = None,
    translate: Callable[[str], str] = lambda message: message,
) -> None:
    """Возвращает исходную клавиатуру отчета после выбора порога."""
    message = callback.message
    if message is None:
        return

    try:
        await message.edit_reply_markup(
            reply_markup=build_report_keyboard(post, unit_uuid, translate=translate)
        )
    except Exception:
        logger.bind(
            unit_uuid=unit_uuid,
            chat_id=message.chat.id,
            user_id=callback.from_user.id,
            **(extra_log_context or {}),
        ).exception(log_label)


async def _launch_manual_report(
    callback: CallbackQuery,
    *,
    unit_uuid: str,
    action: str,
    post: str,
    state: FSMContext,
    report_config: ManualReportLaunchConfig,
    extra_op_config: dict[str, Any] | None = None,
    extra_tags: dict[str, str] | None = None,
    config: Config | None = None,
    translate: Callable[[str], str] = lambda message: message,
) -> None:
    """Запускает Dagster job для одного заведения из inline-кнопки."""
    message = callback.message
    if message is None:
        await _safe_callback_answer(callback, tr(translate, "Unable to determine message"), show_alert=True)
        return

    config = config or load_config()
    state_data = await state.get_data()
    ctx = state_data.get("ctx") or {}
    # Не берем unit из callback вслепую — сначала проверяем, что он реально есть в доступах пользователя.
    unit = _find_unit(ctx, unit_uuid)

    if not unit:
        logger.bind(
            unit_uuid=unit_uuid,
            chat_id=message.chat.id,
            user_id=callback.from_user.id,
        ).warning(
            f"{report_config.log_label} launch skipped: unit not found in user context"
        )
        await _safe_callback_answer(callback, tr(translate, "Unable to find this location in your access list"), show_alert=True)
        return

    account_id = unit.get("account_id")
    if not account_id:
        logger.bind(
            unit_uuid=unit_uuid,
            chat_id=message.chat.id,
            user_id=callback.from_user.id,
        ).warning(f"{report_config.log_label} launch skipped: account_id missing")
        await _safe_callback_answer(callback, tr(translate, "Unable to determine account for this location"), show_alert=True)
        return

    topic_id = getattr(message, "message_thread_id", None)
    op_config: dict[str, Any] = {
        "unit_uuid": unit_uuid,
        "account_id": int(account_id),
        "chat_id": int(message.chat.id),
    }
    if extra_op_config:
        op_config.update(extra_op_config)
    if topic_id is not None:
        op_config["topic_id"] = int(topic_id)
    if getattr(message, "date", None) is not None:
        # Дата сообщения нужна manual-job'ам, которые считают окно как "дата сообщения - 1 день".
        op_config["message_date"] = message.date.isoformat()

    # Теги потом помогают фильтровать manual-run'ы в Dagster и быстро понимать их источник.
    tags = {
        "source": "aida3",
        "post": post,
        "action": action,
        "unit_uuid": unit_uuid,
        "chat_id": str(message.chat.id),
        "user_id": str(callback.from_user.id),
    }
    if extra_tags:
        tags.update(extra_tags)

    client = _build_dagster_client(config)

    try:
        run = await client.launch_job(
            job_name=report_config.job_name,
            op_name=report_config.op_name,
            op_config=op_config,
            tags=tags,
        )
    except DagsterLaunchError as exc:
        logger.bind(
            unit_uuid=unit_uuid,
            unit_name=unit.get("name"),
            account_id=account_id,
            chat_id=message.chat.id,
            topic_id=topic_id,
            user_id=callback.from_user.id,
        ).warning(
            f"Failed to launch {report_config.log_label.lower()} job",
            error=str(exc),
        )
        await _safe_callback_answer(
            callback,
            tr(translate, report_config.launch_error_popup),
            show_alert=True,
        )
        return

    logger.bind(
        unit_uuid=unit_uuid,
        unit_name=unit.get("name"),
        account_id=account_id,
        chat_id=message.chat.id,
        topic_id=topic_id,
        user_id=callback.from_user.id,
        run_id=run.run_id,
        run_status=run.status,
    ).info(f"{report_config.log_label} job launched")

    await _safe_callback_answer(callback, tr(translate, report_config.success_popup))


async def _show_threshold_keyboard(
    callback: CallbackQuery,
    callback_data: ReportActionCallback,
    translate: Callable[[str], str] = lambda message: message,
) -> None:
    """Показывает inline-клавиатуру выбора порога отчета."""
    message = callback.message
    if message is None:
        await _safe_callback_answer(callback, tr(translate, "Unable to determine message"), show_alert=True)
        return

    builder, success_text, error_text, error_log = THRESHOLD_KEYBOARD_CONFIGS[callback_data.action]
    try:
        # Меняем только клавиатуру сообщения: сам текст отчета/карточки трогать не нужно.
        await message.edit_reply_markup(
            reply_markup=builder(
                callback_data.post,
                callback_data.unit_uuid,
                translate=translate,
            )
        )
        await _safe_callback_answer(callback, tr(translate, success_text))
    except Exception:
        logger.bind(
            unit_uuid=callback_data.unit_uuid,
            chat_id=message.chat.id,
            user_id=callback.from_user.id,
        ).exception(error_log)
        await _safe_callback_answer(callback, tr(translate, error_text), show_alert=True)


@router.callback_query(ReportActionCallback.filter(F.action.in_(DIRECT_REPORT_ACTIONS)))
async def launch_direct_report(
    callback: CallbackQuery,
    callback_data: ReportActionCallback,
    state: FSMContext,
    config: Config | None = None,
    _: Callable[[str], str] = lambda message: message,
) -> None:
    """Запускает manual job без промежуточного выбора порога."""
    await _launch_manual_report(
        callback,
        unit_uuid=callback_data.unit_uuid,
        action=callback_data.action,
        post=callback_data.post,
        state=state,
        report_config=MANUAL_REPORT_CONFIGS[callback_data.action],
        config=config,
        translate=_,
    )


@router.callback_query(ReportActionCallback.filter(F.action.in_(tuple(THRESHOLD_KEYBOARD_CONFIGS))))
async def show_threshold_keyboard(
    callback: CallbackQuery,
    callback_data: ReportActionCallback,
    _: Callable[[str], str] = lambda message: message,
) -> None:
    """Показывает inline-клавиатуру выбора порога."""
    await _show_threshold_keyboard(callback, callback_data, translate=_)


async def _launch_threshold_report(
    callback: CallbackQuery,
    *,
    post: str,
    unit_uuid: str,
    action: str,
    report_config: ManualReportLaunchConfig,
    state: FSMContext,
    threshold_minutes: int,
    extra_op_config: dict[str, Any],
    extra_tags: dict[str, str],
    restore_error_log: str,
    config: Config | None = None,
    translate: Callable[[str], str] = lambda message: message,
) -> None:
    try:
        await _launch_manual_report(
            callback,
            unit_uuid=unit_uuid,
            action=action,
            post=post,
            state=state,
            report_config=report_config,
            extra_op_config=extra_op_config,
            extra_tags=extra_tags,
            config=config,
            translate=translate,
        )
    finally:
        await _restore_report_keyboard(
            callback,
            post=post,
            unit_uuid=unit_uuid,
            log_label=restore_error_log,
            extra_log_context={"threshold_minutes": threshold_minutes},
            translate=translate,
        )


@router.callback_query(WaitingThresholdCallback.filter())
async def launch_waiting_report(
    callback: CallbackQuery,
    callback_data: WaitingThresholdCallback,
    state: FSMContext,
    config: Config | None = None,
    _: Callable[[str], str] = lambda message: message,
) -> None:
    """Запускает `waiting_job` для выбранного порога ожидания."""
    await _launch_threshold_report(
        callback,
        post=callback_data.post,
        unit_uuid=callback_data.unit_uuid,
        action="waiting",
        report_config=MANUAL_REPORT_CONFIGS["waiting"],
        state=state,
        threshold_minutes=int(callback_data.minutes),
        extra_op_config={
            "wait_threshold_seconds": int(callback_data.minutes) * 60,
        },
        extra_tags={
            "wait_threshold_minutes": str(callback_data.minutes),
        },
        restore_error_log="Failed to restore report keyboard after waiting selection",
        config=config,
        translate=_,
    )


@router.callback_query(DrinkThresholdCallback.filter())
async def launch_drink_rest_report(
    callback: CallbackQuery,
    callback_data: DrinkThresholdCallback,
    state: FSMContext,
    config: Config | None = None,
    _: Callable[[str], str] = lambda message: message,
) -> None:
    """Запускает `drink_rest_job` для выбранного порога времени."""
    await _launch_threshold_report(
        callback,
        post=callback_data.post,
        unit_uuid=callback_data.unit_uuid,
        action="drink_rest",
        report_config=MANUAL_REPORT_CONFIGS["drink_rest"],
        state=state,
        threshold_minutes=int(callback_data.minutes),
        extra_op_config={
            "drink_threshold_seconds": int(callback_data.minutes) * 60,
        },
        extra_tags={
            "drink_threshold_minutes": str(callback_data.minutes),
        },
        restore_error_log="Failed to restore report keyboard after drink selection",
        config=config,
        translate=_,
    )


@router.callback_query(F.data == HIDE_REPORT_CALLBACK)
async def hide_report_message(
    callback: CallbackQuery,
    _: Callable[[str], str] = lambda message: message,
) -> None:
    """Удаляет сообщение с отчетом по кнопке `Скрыть отчет`."""
    message = callback.message
    if message is None:
        await _safe_callback_answer(callback, tr(_, "Unable to find report message"), show_alert=True)
        return

    try:
        await message.delete()
        await _safe_callback_answer(callback)
    except Exception:
        logger.bind(
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=callback.from_user.id,
        ).exception("Failed to hide report message")
        await _safe_callback_answer(callback, tr(_, "Unable to hide report"), show_alert=True)
