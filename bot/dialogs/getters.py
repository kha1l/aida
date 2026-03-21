"""Геттеры данных для `aiogram_dialog`-окон бота."""

from typing import Any

import logging

from aiogram_dialog import DialogManager

from bot.dialogs.data import STOCK_ITEMS, POST
from bot.dialogs.texts import MenuTexts
from database.requests.orders import get_orders_by_post
from bot.dialogs.helpers import DialogContext
from services.i18n import get_translator


logger = logging.getLogger(__name__)


OPERATION_TITLE_MAP = {
    "operation_tracking": "Choose locations for tracking:",
    "operation_metrics": "Choose locations for metrics:",
    "operation_revenue": "Choose locations for network revenue:",
    "operation_stock": "Choose locations for stock balances:",
}


class MenuGetters:
    """Геттеры данных для окон меню (aiogram_dialog)."""

    @staticmethod
    def _current_topic_id(dialog_manager: DialogManager) -> int | None:
        """Возвращает id текущего Telegram topic, если диалог открыт в топике."""
        event = dialog_manager.event
        direct_topic_id = getattr(event, "message_thread_id", None)
        if direct_topic_id is not None:
            return int(direct_topic_id)

        message = getattr(event, "message", None)
        nested_topic_id = getattr(message, "message_thread_id", None)
        if nested_topic_id is not None:
            return int(nested_topic_id)
        return None

    @staticmethod
    def _get_context_state(dialog_manager: DialogManager, *, action: str):
        """Возвращает текущий контекст диалога и тихо логирует сбои UI-состояния."""
        try:
            return dialog_manager.current_context()
        except Exception as exc:  # noqa: BLE001
            logger.debug("Не удалось получить current_context для %s", action, exc_info=exc)
            return None

    @staticmethod
    def _translator(dialog_manager: DialogManager):
        """Безопасно достаёт функцию перевода из middleware."""
        return get_translator(dialog_manager)

    @staticmethod
    def _texts(dialog_manager: DialogManager) -> dict:
        """Собирает локализованные подписи для меню."""
        _ = MenuGetters._translator(dialog_manager)
        return {
            "title_settings": _(MenuTexts.SETTINGS_TITLE),
            "title_operation": _(MenuTexts.OPERATION_TITLE),
            "title_subscription": _(MenuTexts.SUBSCRIPTION_TITLE),
            "title_stops": _(MenuTexts.STOPS_TITLE),
            "title_stocks": _(MenuTexts.STOCKS_TITLE),
            "title_units": _(MenuTexts.UNITS_TITLE),
            "title_language": _(MenuTexts.LANGUAGE_TITLE),
            "btn_notifications": _("\U0001F50A Notifications"),
            "btn_reports": _("\U0001F4D1 Reports"),
            "btn_live_data": _("\U0001F4AC Live data"),
            "btn_settings": _("\U0001F6E0 Settings"),
            "btn_close_menu": _("\u274E Close menu"),
            "btn_manage_app": _("\U0001F4F1 Manage app"),
            "btn_kb": _("\U0001F4DA Knowledge base"),
            "btn_back": _("\U0001F519 Back"),
            "btn_change_language": _("\U0001F310 Change language"),
            "btn_language_ru": _("\U0001F1F7\U0001F1FA Russian"),
            "btn_language_en": _("\U0001F1EC\U0001F1E7 English"),
            "btn_subscribe_all": _("\U0001F4CC Subscribe all"),
            "btn_unsubscribe_all": _("\U0001F4CC Unsubscribe all"),
            "btn_current_metrics": _("\U0001F4CA Current metrics"),
            "btn_network_revenue": _("\U0001F4B9 Network revenue"),
            "btn_large_stocks": _("\U0001F69A Large stock balances"),
            "btn_tracking": _("🛰 Tracking"),
            "btn_birthdays": _("\U0001F389 Birthdays"),
            "btn_stops": _("\U0001F6AB Stops"),
            "btn_tickets": _("\U0001F4E9 Tickets"),
            "btn_staff": _("\U0001F5C2 Tenure/Anniversary"),
            "btn_cancellations": _("\U0001F17E Cancellations"),
            "btn_defect": _("\U0001F9EA Defect"),
            "btn_courier_reports": _("\U0001F699 Courier reports"),
            "btn_restaurant_reports": _("\U0001F957 Restaurant reports"),
            "btn_metrics": _("\U0001F4C9 Metrics"),
            "btn_stock_balances": _("\U0001F69A Stock balances"),
            "btn_writeoff": _("\U0001F5D1 Write-offs"),
            "btn_stops_rest": _("\U0001F3E0 Restaurant stops"),
            "btn_stops_key_ings": _("\U0001F9C0 Key ingredient stops"),
            "btn_stops_ings": _("\U0001F355 Ingredient stops"),
            "btn_stops_sector": _("\U0001F6A7 Sector stops"),
            "btn_apply": _("\U0001F44C Apply"),
            "btn_select_all": _("\U0001F4CC Select all"),
            "btn_clear_selection": _("\U0001F4CC Clear selection"),
        }

    @staticmethod
    async def main_data(dialog_manager: DialogManager, **kwargs: Any) -> dict:
        """Возвращает данные для главного окна меню."""
        # Приветствие + кнопки главного меню
        event = dialog_manager.event
        user = getattr(event, "from_user", None)
        user_name = user.full_name if user else "there"
        _ = MenuGetters._translator(dialog_manager)
        greeting = _(MenuTexts.MAIN_GREETING).format(user_name=user_name)
        return {
            "main_greeting": greeting,
            **MenuGetters._texts(dialog_manager),
        }

    @staticmethod
    async def units_data(dialog_manager: DialogManager, **kwargs: Any) -> dict:
        """Готовит список заведений и выбранные подписки."""
        ctx = await DialogContext.load_ctx(dialog_manager)
        units = [unit.model_dump() for unit in ctx.units]
        dialog_manager.dialog_data["units_by_id"] = {
            unit["uuid"]: unit["name"] for unit in units
        }
        dialog_manager.dialog_data["units_meta"] = {
            unit["uuid"]: {
                "name": unit["name"],
                "account_id": unit.get("account_id"),
            }
            for unit in units
        }

        session = dialog_manager.middleware_data.get("session")
        event_chat = dialog_manager.middleware_data.get("event_chat")
        post = dialog_manager.dialog_data.get("post")
        if session and event_chat and post:
            ctx_state = MenuGetters._get_context_state(dialog_manager, action="units_data")
            if ctx_state and ctx_state.widget_data.get("units") is None:
                try:
                    # При первом открытии экрана подтягиваем уже сохраненные подписки,
                    # чтобы пользователь видел текущее состояние без лишних кликов.
                    orders = await get_orders_by_post(
                        session,
                        event_chat.id,
                        post,
                        MenuGetters._current_topic_id(dialog_manager),
                    )
                    selected = []
                    for order in orders:
                        if order.uuids:
                            selected.extend(order.uuids)
                    # Подсветка в UI должна отражать общее состояние чата/топика,
                    # поэтому схлопываем дубли по uuid.
                    selected = list(dict.fromkeys(selected))
                    ctx_state.widget_data["units"] = selected
                    subs_by_post = dialog_manager.dialog_data.setdefault("subs_by_post", {})
                    subs_by_post[post] = selected
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Не удалось предзагрузить выбранные заведения", exc_info=exc)
        _ = MenuGetters._translator(dialog_manager)
        texts = MenuGetters._texts(dialog_manager)
        dialog_type = str(dialog_manager.dialog_data.get("type") or "")
        if dialog_type.startswith("operation_"):
            texts["title_units"] = _(
                OPERATION_TITLE_MAP.get(
                    dialog_type,
                    "Choose locations:",
                )
            )
            texts["btn_subscribe_all"] = texts["btn_select_all"]
            texts["btn_unsubscribe_all"] = texts["btn_clear_selection"]

        return {
            "units": units,
            **texts,
        }

    @staticmethod
    async def stocks_data(dialog_manager: DialogManager, **kwargs: Any) -> dict:
        """Готовит список категорий складских остатков."""
        _ = MenuGetters._translator(dialog_manager)
        session = dialog_manager.middleware_data.get("session")
        event_chat = dialog_manager.middleware_data.get("event_chat")
        post = dialog_manager.dialog_data.get("post")
        valid_ids = {item["id"] for item in STOCK_ITEMS}
        if session and event_chat and post == "stock":
            ctx_state = MenuGetters._get_context_state(dialog_manager, action="stocks_data")
            if ctx_state and ctx_state.widget_data.get("stocks") is None:
                try:
                    # В stock-подписке дополнительно сохраняются категории,
                    # поэтому предзагружаем их отдельно от списка заведений.
                    orders = await get_orders_by_post(
                        session,
                        event_chat.id,
                        "stock",
                        MenuGetters._current_topic_id(dialog_manager),
                    )
                    selected = []
                    for order in orders:
                        if order.params:
                            if "|" in order.params:
                                _prefix, raw = order.params.split("|", 1)
                                selected.extend([p for p in raw.split(",") if p in valid_ids])
                            else:
                                selected.extend([p for p in order.params.split(",") if p in valid_ids])
                    ctx_state.widget_data["stocks"] = selected
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Не удалось предзагрузить категории stock", exc_info=exc)
        return {
            "stocks": [
                {**item, "label": _(item["label"])}
                for item in STOCK_ITEMS
            ],
            **MenuGetters._texts(dialog_manager),
        }

    @staticmethod
    async def texts_data(dialog_manager: DialogManager, **kwargs: Any) -> dict:
        """Возвращает общий набор локализованных текстов."""
        return MenuGetters._texts(dialog_manager)

    @staticmethod
    async def language_data(dialog_manager: DialogManager, **kwargs: Any) -> dict:
        """Возвращает список доступных языков интерфейса."""
        texts = MenuGetters._texts(dialog_manager)
        return {
            "languages": [
                {"id": "ru", "label": texts["btn_language_ru"]},
                {"id": "en", "label": texts["btn_language_en"]},
            ],
            **texts,
        }
