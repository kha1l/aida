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
from database.requests.settings import set_chat_language
from database.requests.orders import get_orders_by_post, upsert_order, delete_order
from datetime import datetime


logger = logging.getLogger(__name__)


class MenuHandlers:
    """Коллекция обработчиков для диалогов меню."""
    @staticmethod
    def _translator(manager: DialogManager):
        """Безопасно достаёт переводчик из middleware data."""
        # Берём функцию перевода из middleware (если нет — fallback)
        value = (
            manager.middleware_data.get("i18n_gettext")
            or manager.middleware_data.get("_")
        )
        return value if callable(value) else (lambda s: s)

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
    async def set_type_notice(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Переключает контекст диалога на уведомления."""
        manager.dialog_data["type"] = "notice"

    @staticmethod
    async def set_type_reports(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Переключает контекст диалога на отчёты."""
        manager.dialog_data["type"] = "reports"

    @staticmethod
    async def set_type_stop(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Переключает контекст диалога на меню стопов."""
        manager.dialog_data["type"] = "stop"

    @staticmethod
    async def set_type_stock(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Подготавливает диалог к выбору складских остатков."""
        # Переходим в режим "складские остатки" и сбрасываем выбор категорий
        manager.dialog_data["type"] = "stock"
        manager.dialog_data["post"] = "stock"
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
            # Если тип отчёта изменился — сбрасываем выбор заведений
            if manager.dialog_data.get("post") != post:
                MenuHandlers._drop_widget_state(manager, "units")
            manager.dialog_data["post"] = post
            await manager.switch_to(state)

        return _handler

    @staticmethod
    def make_stop_post_handler(post: str) -> Callable[[CallbackQuery, Button, DialogManager], Awaitable[None]]:
        """Строит обработчик выбора типа уведомления о стопах."""
        async def _handler(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
            """Сохраняет выбранный stop-post и открывает список заведений."""
            if manager.dialog_data.get("post") != post:
                MenuHandlers._drop_widget_state(manager, "units")
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

        post = manager.dialog_data.get("post")
        if not post:
            await manager.switch_to(MenuSG.main)
            return

        session = manager.middleware_data.get("session")
        event_chat = manager.middleware_data.get("event_chat")
        orders = []
        if session and event_chat:
            orders = await get_orders_by_post(session, event_chat.id, post)

        subs_by_post = DialogContext.get_dialog_value(manager, "subs_by_post", {})
        prev_selected = set(subs_by_post.get(post, []))
        subs_by_post[post] = list(selected)

        units_by_id = await DialogContext.get_units_by_id(manager)
        units_meta = manager.dialog_data.get("units_meta", {})

        def _group_by_account(uuids: set[str]) -> dict[int | None, set[str]]:
            """Группирует выбранные заведения по account_id."""
            # Группировка заведений по account_id
            grouped: dict[int | None, set[str]] = {}
            for uuid in uuids:
                meta = units_meta.get(uuid, {})
                account_id = meta.get("account_id")
                grouped.setdefault(account_id, set()).add(uuid)
            return grouped

        # Текущее состояние подписок из БД
        existing_by_account: dict[int | None, set[str]] = {
            order.account_id: set(order.uuids or []) for order in orders
        }
        selected_by_account = _group_by_account(selected)
        baseline_by_account = _group_by_account(prev_selected)

        added_ids: set[str] = set()
        removed_ids: set[str] = set()
        final_by_account: dict[int | None, set[str]] = {}

        accounts = (
            set(existing_by_account.keys())
            | set(selected_by_account.keys())
            | set(baseline_by_account.keys())
        )
        for account_id in accounts:
            existing_set = existing_by_account.get(account_id, set())
            baseline_set = baseline_by_account.get(account_id, set())
            selected_set = selected_by_account.get(account_id, set())

            to_remove = baseline_set - selected_set
            final_set = (existing_set - to_remove) | selected_set

            added_ids.update(selected_set - existing_set)
            removed_ids.update(existing_set - final_set)
            final_by_account[account_id] = final_set

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
                        await delete_order(session, event_chat.id, post, account_id)
                    continue
                if final_set != existing_set:
                    await upsert_order(
                        session,
                        event_chat.id,
                        post,
                        account_id,
                        sorted(final_set),
                        params,
                    )

    @staticmethod
    async def on_units_subscribe_all(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Выбирает все заведения и сразу применяет подписку."""
        units_meta = manager.dialog_data.get("units_meta", {})
        unit_ids = list(units_meta.keys())
        MenuHandlers._set_widget_state(manager, "units", unit_ids)
        await MenuHandlers.on_units_commit(callback, button, manager)

    @staticmethod
    async def on_units_unsubscribe_all(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Снимает подписку со всех заведений и возвращает назад."""
        MenuHandlers._set_widget_state(manager, "units", [])
        await MenuHandlers.on_units_commit(callback, button, manager)

        type_ = manager.dialog_data.get("type")
        if type_ == "notice":
            await manager.switch_to(MenuSG.notice)
        elif type_ == "reports" or type_ == "stock":
            await manager.switch_to(MenuSG.reports)
        elif type_ == "stop":
            await manager.switch_to(MenuSG.stops)
        else:
            await manager.switch_to(MenuSG.main)

    @staticmethod
    async def on_units_back(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Возвращает пользователя в предыдущее меню выбора."""
        type_ = manager.dialog_data.get("type")
        if type_ == "stock":
            await manager.switch_to(MenuSG.stocks)
        elif type_ == "stop":
            await manager.switch_to(MenuSG.stops)
        elif type_ == "reports":
            await manager.switch_to(MenuSG.reports)
        else:
            await manager.switch_to(MenuSG.notice)

    @staticmethod
    async def on_operation_action(callback: CallbackQuery, button: Button, manager: DialogManager) -> None:
        """Показывает сообщение о запуске обновления данных."""
        _ = MenuHandlers._translator(manager)
        await callback.message.answer(_(MenuTexts.UPDATE_WAIT))

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
        if not session or not event_chat:
            return
        await set_chat_language(session, event_chat.id, item_id)
        _ = MenuHandlers._translator(manager)
        await callback.message.answer(_(MenuTexts.LANGUAGE_CHANGED))
        await manager.switch_to(MenuSG.settings)
