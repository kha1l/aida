"""Обработчики действий в меню подписок и отчетов."""
import logging
from typing import Callable, Awaitable, cast

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from aiogram_dialog.widgets.kbd import Button, Select, Multiselect

from bot.dialogs.data import POST, STOCK_ITEMS
from bot.dialogs.helpers import DialogContext
from bot.dialogs.states import MenuSG
from bot.dialogs.texts import MenuTexts
from database.requests.settings import set_chat_language_for_user
from database.requests.orders import get_orders_by_post, upsert_order, delete_order
from datetime import datetime
from config import load_config
from services.dagster import DagsterClient, DagsterLaunchError
from services.i18n import get_translator, tr


logger = logging.getLogger(__name__)


# Конфигурация manual-job'ов, которые запускаются из раздела "Оперативные данные".
OPERATION_JOB_CONFIGS = {
    "tracking": {
        "job_name": "tracking_job",
        "op_name": "tracking_op",
        "success_popup": "Starting tracking collection...",
        "error_popup": "Unable to start tracking",
    },
    "metrics": {
        "job_name": "metrics_manual_job",
        "op_name": "metrics_manual_op",
        "success_popup": "Starting metrics collection...",
        "error_popup": "Unable to start metrics report",
    },
    "revenue": {
        "job_name": "revenue_manual_job",
        "op_name": "revenue_manual_op",
        "success_popup": "Starting revenue collection...",
        "error_popup": "Unable to start revenue report",
    },
    "stock": {
        "job_name": "stock_manual_job",
        "op_name": "stock_manual_op",
        "success_popup": "Starting stock balance collection...",
        "error_popup": "Unable to start stock balance report",
    },
}


class MenuHandlers:
    """Коллекция обработчиков для диалогов меню."""

    @staticmethod
    def _current_topic_id(manager: DialogManager) -> int | None:
        """Возвращает id текущего Telegram topic для message/callback-события."""
        event = manager.event
        direct_topic_id = getattr(event, "message_thread_id", None)
        if direct_topic_id is not None:
            return int(direct_topic_id)

        message = getattr(event, "message", None)
        nested_topic_id = getattr(message, "message_thread_id", None)
        if nested_topic_id is not None:
            return int(nested_topic_id)
        return None

    @staticmethod
    def _translator(manager: DialogManager):
        """Безопасно достаёт переводчик из middleware data."""
        return get_translator(manager)

    @staticmethod
    def _drop_widget_state(manager: DialogManager, key: str) -> None:
        """Мягко удаляет данные виджета из текущего контекста диалога."""
        try:
            manager.current_context().widget_data.pop(key, None)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Не удалось сбросить widget_data[%s]", key, exc_info=exc)

    @staticmethod
    def _set_widget_state(manager: DialogManager, key: str, value) -> None:
        """Мягко записывает данные виджета в текущий контекст диалога."""
        try:
            manager.current_context().widget_data[key] = value
        except Exception as exc:  # noqa: BLE001
            logger.debug("Не удалось записать widget_data[%s]", key, exc_info=exc)

    @staticmethod
    def _reset_units_selection(manager: DialogManager) -> None:
        """Сбрасывает выбранные заведения перед новым сценарием выбора."""
        MenuHandlers._drop_widget_state(manager, "units")

    @staticmethod
    def _set_dialog_type(manager: DialogManager, dialog_type: str, *, post: str | None = None) -> None:
        """Единообразно переключает режим диалога и обновляет связанный `post`."""
        manager.dialog_data["type"] = dialog_type
        if post is None:
            manager.dialog_data.pop("post", None)
        else:
            manager.dialog_data["post"] = post

    @staticmethod
    def _dialog_back_state(dialog_type: str | None) -> MenuSG:
        """Возвращает экран, на который нужно вернуться из выбора заведений."""
        if dialog_type == "stock":
            return MenuSG.stocks
        if dialog_type == "stop":
            return MenuSG.stops
        if dialog_type == "reports":
            return MenuSG.reports
        if str(dialog_type).startswith("operation_"):
            return MenuSG.operation
        return MenuSG.notice

    @staticmethod
    def _build_dagster_client() -> DagsterClient:
        """Создает Dagster GraphQL-клиент из текущего env-конфига."""
        config = load_config()
        return DagsterClient.from_settings(config.dagster)

    @staticmethod
    async def set_type_notice(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Переключает контекст диалога на уведомления."""
        MenuHandlers._set_dialog_type(manager, "notice")

    @staticmethod
    async def set_type_reports(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Переключает контекст диалога на отчёты."""
        MenuHandlers._set_dialog_type(manager, "reports")

    @staticmethod
    async def set_type_stop(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Переключает контекст диалога на меню стопов."""
        MenuHandlers._set_dialog_type(manager, "stop")

    @staticmethod
    async def set_type_stock(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Подготавливает диалог к выбору складских остатков."""
        # Для stock сначала выбираем категории, поэтому дополнительно чистим виджет `stocks`.
        MenuHandlers._set_dialog_type(manager, "stock", post="stock")
        MenuHandlers._drop_widget_state(manager, "stocks")

    @staticmethod
    async def on_exit(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Закрывает меню и отправляет сообщение с подсказкой."""
        _ = MenuHandlers._translator(manager)
        try:
            # Пытаемся удалить текущее сообщение с меню
            if callback.message:
                await callback.message.delete()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Не удалось удалить сообщение меню при выходе", exc_info=exc)
        await manager.done()
        await callback.message.answer(_(MenuTexts.EXIT_MESSAGE))

    @staticmethod
    def make_post_handler(post: str, state: MenuSG) -> Callable[[CallbackQuery, Button, DialogManager], Awaitable[None]]:
        """Строит обработчик выбора типа отчёта."""
        async def _handler(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
            """Сохраняет выбранный post и открывает нужное окно."""
            if manager.dialog_data.get("post") != post:
                MenuHandlers._reset_units_selection(manager)
            manager.dialog_data["post"] = post
            await manager.switch_to(state)

        return _handler

    @staticmethod
    def make_stop_post_handler(post: str) -> Callable[[CallbackQuery, Button, DialogManager], Awaitable[None]]:
        """Строит обработчик выбора типа уведомления о стопах."""
        async def _handler(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
            """Сохраняет выбранный stop-post и открывает список заведений."""
            if manager.dialog_data.get("post") != post:
                MenuHandlers._reset_units_selection(manager)
            manager.dialog_data["post"] = post
            await manager.switch_to(MenuSG.units)

        return _handler

    @staticmethod
    async def on_stock_commit(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Сохраняет выбранные категории и ведёт к выбору заведений."""
        # Сохраняем выбранные категории складских остатков
        widget = cast(Multiselect, manager.find("stocks"))
        selected = widget.get_checked()
        manager.dialog_data["post"] = "stock"
        manager.dialog_data["stock_params"] = list(selected)
        await manager.switch_to(MenuSG.units)

    @staticmethod
    async def on_units_commit(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Применяет выбор заведений и синхронизирует подписки с БД."""
        # Применяем выбор заведений для отчёта/уведомления
        widget = cast(Multiselect, manager.find("units"))
        selected = set(widget.get_checked())

        dialog_type = str(manager.dialog_data.get("type") or "")
        if dialog_type.startswith("operation_"):
            await MenuHandlers._launch_operation_job(callback, manager, selected)
            return

        post = manager.dialog_data.get("post")
        if not post:
            await manager.switch_to(MenuSG.main)
            return

        session = manager.middleware_data.get("session")
        event_chat = manager.middleware_data.get("event_chat")
        topic_id = MenuHandlers._current_topic_id(manager)
        orders = []
        if session and event_chat:
            orders = await get_orders_by_post(session, event_chat.id, post, topic_id)

        subs_by_post = DialogContext.get_dialog_value(manager, "subs_by_post", {})
        prev_selected = set(subs_by_post.get(post, []))
        subs_by_post[post] = list(selected)

        units_by_id = await DialogContext.get_units_by_id(manager)
        units_meta = manager.dialog_data.get("units_meta", {})

        # Текущее состояние подписок из БД на уровне всего чата/топика.
        existing_by_account: dict[int | None, set[str]] = {}
        existing_owner_by_uuid: dict[str, int | None] = {}
        for order in orders:
            uuids = set(order.uuids or [])
            existing_by_account.setdefault(order.account_id, set()).update(uuids)
            for unit_uuid in uuids:
                existing_owner_by_uuid.setdefault(unit_uuid, order.account_id)

        accessible_units = set(units_meta.keys())
        existing_global = set(existing_owner_by_uuid.keys())
        inaccessible_existing = existing_global - accessible_units
        final_global = inaccessible_existing | selected

        added_ids = final_global - existing_global
        removed_ids = existing_global - final_global

        # Каждая точка в рамках одного чата/топика должна храниться только один раз.
        # Если точка уже была подписана кем-то в этом чате, сохраняем прежний owner account_id.
        # Для новых точек owner берем из текущего списка доступов пользователя.
        final_by_account: dict[int | None, set[str]] = {}
        for unit_uuid in final_global:
            owner_account_id = existing_owner_by_uuid.get(unit_uuid)
            if owner_account_id is None:
                owner_account_id = (units_meta.get(unit_uuid) or {}).get("account_id")
            final_by_account.setdefault(owner_account_id, set()).add(unit_uuid)

        accounts = set(existing_by_account.keys()) | set(final_by_account.keys())

        add_units = [units_by_id.get(uuid, uuid) for uuid in added_ids]
        drop_units = [units_by_id.get(uuid, uuid) for uuid in removed_ids]

        _ = MenuHandlers._translator(manager)
        message = _(MenuTexts.APPLY_PREFIX).format(label=_(POST.get(post, post)))
        if add_units:
            message += _(MenuTexts.APPLY_ADDED).format(items=", ".join(str(name) for name in add_units))
            if drop_units:
                message += _(MenuTexts.APPLY_REMOVED).format(items=", ".join(str(name) for name in drop_units))
        else:
            if drop_units:
                message += _(MenuTexts.APPLY_REMOVED).format(items=", ".join(str(name) for name in drop_units))
            else:
                if selected:
                    current_units = [units_by_id.get(uuid, uuid) for uuid in selected]
                    message += _(MenuTexts.APPLY_NO_CHANGES).format(
                        items=", ".join(str(name) for name in current_units)
                    )
                else:
                    message += _(MenuTexts.APPLY_NONE)

        await callback.message.answer(message)

        if session and event_chat:
            timestamp = datetime.now().isoformat(timespec="seconds")
            if post == "stock":
                selected_stock = manager.dialog_data.get("stock_params", [])
                stock_ids = {str(item) for item in selected_stock}
                ordered = [
                    item["id"] for item in STOCK_ITEMS if item["id"] in stock_ids
                ]
                params = ",".join(ordered)
            else:
                params = timestamp

            for account_id in accounts:
                final_set = final_by_account.get(account_id, set())
                existing_set = existing_by_account.get(account_id, set())
                if not final_set:
                    if existing_set:
                        await delete_order(session, event_chat.id, post, account_id, topic_id)
                    continue
                if final_set != existing_set:
                    await upsert_order(
                        session,
                        event_chat.id,
                        post,
                        account_id,
                        topic_id,
                        sorted(final_set),
                        params,
                    )

    @staticmethod
    async def on_units_subscribe_all(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Выбирает все заведения, но сохраняет изменения только по кнопке Apply."""
        units_meta = manager.dialog_data.get("units_meta", {})
        unit_ids = list(units_meta.keys())
        MenuHandlers._set_widget_state(manager, "units", unit_ids)
        await manager.show()

    @staticmethod
    async def on_units_unsubscribe_all(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Снимает выбор со всех заведений, но пишет в БД только после Apply."""
        MenuHandlers._set_widget_state(manager, "units", [])
        await manager.show()

    @staticmethod
    async def on_units_back(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Возвращает пользователя в предыдущее меню выбора."""
        await manager.switch_to(MenuHandlers._dialog_back_state(manager.dialog_data.get("type")))

    @staticmethod
    async def on_operation_action(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Открывает выбор заведений для оперативного отчета."""
        _ = MenuHandlers._translator(manager)
        action = getattr(button, "widget_id", None) or getattr(button, "id", None)
        if not action:
            await callback.answer(tr(_, "Unable to determine action"), show_alert=True)
            return
        MenuHandlers._set_dialog_type(manager, f"operation_{action}")
        MenuHandlers._reset_units_selection(manager)
        await manager.switch_to(MenuSG.units)

    @staticmethod
    async def _launch_operation_job(
        callback: CallbackQuery,
        manager: DialogManager,
        selected_unit_ids: set[str],
    ) -> None:
        """Запускает manual Dagster job для выбранного оперативного отчета."""
        message = callback.message
        _ = MenuHandlers._translator(manager)
        if message is None:
            await callback.answer(tr(_, "Unable to determine message"), show_alert=True)
            return

        if not selected_unit_ids:
            await callback.answer(tr(_, "Choose at least one location"), show_alert=True)
            return

        dialog_type = str(manager.dialog_data.get("type") or "")
        action = dialog_type.removeprefix("operation_")
        config_entry = OPERATION_JOB_CONFIGS.get(action)
        if config_entry is None:
            await callback.answer(tr(_, "Unknown live data report type"), show_alert=True)
            return

        client = MenuHandlers._build_dagster_client()

        units_meta = manager.dialog_data.get("units_meta", {})
        selected_units = sorted(
            selected_unit_ids,
            key=lambda unit_uuid: str((units_meta.get(unit_uuid) or {}).get("name") or unit_uuid).lower(),
        )
        tags = {
            "source": "aida3",
            "post": action,
            "action": action,
            "chat_id": str(message.chat.id),
            "user_id": str(callback.from_user.id),
            "unit_count": str(len(selected_units)),
        }
        topic_id = getattr(message, "message_thread_id", None)
        op_config = {
            "unit_uuids": selected_units,
            "chat_id": int(message.chat.id),
        }
        if topic_id is not None:
            op_config["topic_id"] = int(topic_id)

        try:
            run = await client.launch_job(
                job_name=config_entry["job_name"],
                op_name=config_entry["op_name"],
                op_config=op_config,
                tags=tags,
            )
        except DagsterLaunchError as exc:
            logger.warning("Failed to launch operation job %s: %s", action, exc)
            await callback.answer(tr(_, config_entry["error_popup"]), show_alert=True)
            return

        logger.info(
            "Operation job launched: action=%s run_id=%s chat_id=%s unit_count=%s",
            action,
            run.run_id,
            message.chat.id,
            len(selected_units),
        )
        await callback.answer(tr(_, config_entry["success_popup"]))
        await manager.switch_to(MenuSG.operation)

    @staticmethod
    async def on_language_selected(
        callback: CallbackQuery,
        widget: Select,
        manager: DialogManager,
        item_id: str,
    ) -> None:
        """Сохраняет выбранный язык для текущего чата."""
        session = manager.middleware_data.get("session")
        event_chat = manager.middleware_data.get("event_chat")
        tg_user = manager.middleware_data.get("event_from_user")
        if not session or not event_chat or not tg_user:
            return
        await set_chat_language_for_user(session, tg_user, event_chat.id, item_id)
        _ = MenuHandlers._translator(manager)
        await callback.message.answer(_(MenuTexts.LANGUAGE_CHANGED))
        await manager.switch_to(MenuSG.settings)
