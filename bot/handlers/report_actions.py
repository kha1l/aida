from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery
from loguru import logger

from bot.keyboards.report_actions import (
    HIDE_REPORT_CALLBACK,
    ReportActionCallback,
    WaitingThresholdCallback,
    build_report_keyboard,
    build_waiting_threshold_keyboard,
)
from config import Config, load_config
from services.dagster import DagsterClient, DagsterLaunchError


router = Router()


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
        success_popup="Запускаю сбор сертификатов...",
        launch_error_popup="Не удалось запустить отчет по сертификатам",
        log_label="Certificates",
    ),
    "later": ManualReportLaunchConfig(
        job_name="later_job",
        op_name="later_op",
        success_popup="Запускаю сбор опозданий и прогулов...",
        launch_error_popup="Не удалось запустить отчет по опозданиям и прогулам",
        log_label="Later",
    ),
    "waiting": ManualReportLaunchConfig(
        job_name="waiting_job",
        op_name="waiting_op",
        success_popup="Запускаю сбор ожиданий курьеров...",
        launch_error_popup="Не удалось запустить отчет по ожиданиям курьеров",
        log_label="Waiting",
    ),
    "sectors": ManualReportLaunchConfig(
        job_name="sectors_job",
        op_name="sectors_op",
        success_popup="Запускаю сбор отчета по секторам...",
        launch_error_popup="Не удалось запустить отчет по секторам доставки",
        log_label="Sectors",
    ),
    "longers": ManualReportLaunchConfig(
        job_name="longers_job",
        op_name="longers_op",
        success_popup="Запускаю сбор отчета по долгим доставкам...",
        launch_error_popup="Не удалось запустить отчет по долгим доставкам",
        log_label="Longers",
    ),
}


def _find_unit(ctx: dict[str, Any], unit_uuid: str) -> dict[str, Any] | None:
    for unit in ctx.get("units", []):
        if unit.get("uuid") == unit_uuid:
            return unit
    return None


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
) -> None:
    """Запускает Dagster job для одного заведения из inline-кнопки."""
    message = callback.message
    if message is None:
        await callback.answer("Не удалось определить сообщение", show_alert=True)
        return

    config = config or load_config()
    state_data = await state.get_data()
    ctx = state_data.get("ctx") or {}
    unit = _find_unit(ctx, unit_uuid)

    if not unit:
        logger.bind(
            unit_uuid=unit_uuid,
            chat_id=message.chat.id,
            user_id=callback.from_user.id,
        ).warning(
            f"{report_config.log_label} launch skipped: unit not found in user context"
        )
        await callback.answer("Не нашел это заведение в вашем доступе", show_alert=True)
        return

    account_id = unit.get("account_id")
    if not account_id:
        logger.bind(
            unit_uuid=unit_uuid,
            chat_id=message.chat.id,
            user_id=callback.from_user.id,
        ).warning(f"{report_config.log_label} launch skipped: account_id missing")
        await callback.answer("Не удалось определить аккаунт для заведения", show_alert=True)
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
        op_config["message_date"] = message.date.isoformat()

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

    client = DagsterClient(
        graphql_url=config.dagster.graphql_url,
        repository_location_name=config.dagster.repository_location_name,
        repository_name=config.dagster.repository_name,
        auth_header_name=config.dagster.auth_header_name,
        auth_header_value=config.dagster.auth_header_value,
        request_timeout_seconds=config.dagster.request_timeout_seconds,
    )

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
        await callback.answer(
            report_config.launch_error_popup,
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

    await callback.answer(report_config.success_popup)


@router.callback_query(ReportActionCallback.filter(F.action == "certificates"))
async def launch_certificates_report(
    callback: CallbackQuery,
    callback_data: ReportActionCallback,
    state: FSMContext,
    config: Config | None = None,
) -> None:
    """Запускает `certificates_job` для одного заведения из inline-кнопки."""
    await _launch_manual_report(
        callback,
        unit_uuid=callback_data.unit_uuid,
        action=callback_data.action,
        post=callback_data.post,
        state=state,
        report_config=MANUAL_REPORT_CONFIGS["certificates"],
        config=config,
    )


@router.callback_query(ReportActionCallback.filter(F.action == "later"))
async def launch_later_report(
    callback: CallbackQuery,
    callback_data: ReportActionCallback,
    state: FSMContext,
    config: Config | None = None,
) -> None:
    """Запускает `later_job` для одного заведения из inline-кнопки."""
    await _launch_manual_report(
        callback,
        unit_uuid=callback_data.unit_uuid,
        action=callback_data.action,
        post=callback_data.post,
        state=state,
        report_config=MANUAL_REPORT_CONFIGS["later"],
        config=config,
    )


@router.callback_query(ReportActionCallback.filter(F.action == "sectors"))
async def launch_sectors_report(
    callback: CallbackQuery,
    callback_data: ReportActionCallback,
    state: FSMContext,
    config: Config | None = None,
) -> None:
    """Запускает `sectors_job` для одного заведения из inline-кнопки."""
    await _launch_manual_report(
        callback,
        unit_uuid=callback_data.unit_uuid,
        action=callback_data.action,
        post=callback_data.post,
        state=state,
        report_config=MANUAL_REPORT_CONFIGS["sectors"],
        config=config,
    )


@router.callback_query(ReportActionCallback.filter(F.action == "longers"))
async def launch_longers_report(
    callback: CallbackQuery,
    callback_data: ReportActionCallback,
    state: FSMContext,
    config: Config | None = None,
) -> None:
    """Запускает `longers_job` для одного заведения из inline-кнопки."""
    await _launch_manual_report(
        callback,
        unit_uuid=callback_data.unit_uuid,
        action=callback_data.action,
        post=callback_data.post,
        state=state,
        report_config=MANUAL_REPORT_CONFIGS["longers"],
        config=config,
    )


@router.callback_query(ReportActionCallback.filter(F.action == "waiting"))
async def show_waiting_thresholds(
    callback: CallbackQuery,
    callback_data: ReportActionCallback,
) -> None:
    """Показывает inline-клавиатуру выбора порога ожидания."""
    message = callback.message
    if message is None:
        await callback.answer("Не удалось определить сообщение", show_alert=True)
        return

    try:
        await message.edit_reply_markup(
            reply_markup=build_waiting_threshold_keyboard(
                callback_data.post,
                callback_data.unit_uuid,
            )
        )
        await callback.answer("Выберите порог ожидания")
    except Exception:
        logger.bind(
            unit_uuid=callback_data.unit_uuid,
            chat_id=message.chat.id,
            user_id=callback.from_user.id,
        ).exception("Failed to show waiting threshold keyboard")
        await callback.answer("Не удалось показать порог ожидания", show_alert=True)


@router.callback_query(WaitingThresholdCallback.filter())
async def launch_waiting_report(
    callback: CallbackQuery,
    callback_data: WaitingThresholdCallback,
    state: FSMContext,
    config: Config | None = None,
) -> None:
    """Запускает `waiting_job` для выбранного порога ожидания."""
    try:
        await _launch_manual_report(
            callback,
            unit_uuid=callback_data.unit_uuid,
            action="waiting",
            post=callback_data.post,
            state=state,
            report_config=MANUAL_REPORT_CONFIGS["waiting"],
            extra_op_config={
                "wait_threshold_seconds": int(callback_data.minutes) * 60,
            },
            extra_tags={
                "wait_threshold_minutes": str(callback_data.minutes),
            },
            config=config,
        )
    finally:
        message = callback.message
        if message is not None:
            try:
                await message.edit_reply_markup(
                    reply_markup=build_report_keyboard(
                        callback_data.post,
                        callback_data.unit_uuid,
                    )
                )
            except Exception:
                logger.bind(
                    unit_uuid=callback_data.unit_uuid,
                    chat_id=message.chat.id,
                    user_id=callback.from_user.id,
                ).exception("Failed to restore report keyboard after waiting selection")


@router.callback_query(F.data == HIDE_REPORT_CALLBACK)
async def hide_report_message(callback: CallbackQuery) -> None:
    """Удаляет сообщение с отчетом по кнопке `Скрыть отчет`."""
    message = callback.message
    if message is None:
        await callback.answer("Не удалось найти сообщение", show_alert=True)
        return

    try:
        await message.delete()
        await callback.answer()
    except Exception:
        logger.bind(
            chat_id=message.chat.id,
            message_id=message.message_id,
            user_id=callback.from_user.id,
        ).exception("Failed to hide report message")
        await callback.answer("Не удалось скрыть отчет", show_alert=True)
