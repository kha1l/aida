from typing import Any

from aiogram_dialog import DialogManager

from bot.dialogs.data import STOCK_ITEMS, POST
from bot.dialogs.texts import MenuTexts
from database.requests.orders import get_orders_by_post
from bot.dialogs.helpers import DialogContext


class MenuGetters:
    """Геттеры данных для окон меню (aiogram_dialog)."""
    @staticmethod
    def _translator(dialog_manager: DialogManager):
        """Безопасно достаёт функцию перевода из middleware."""
        # Безопасно получаем функцию перевода из middleware
        value = (
            dialog_manager.middleware_data.get("i18n_gettext")
            or dialog_manager.middleware_data.get("_")
        )
        return value if callable(value) else (lambda s: s)

    @staticmethod
    def _texts(dialog_manager: DialogManager) -> dict:
        """Собирает локализованные подписи для меню."""
        # Все текстовые константы для окна
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
            "btn_birthdays": _("\U0001F389 Birthdays"),
            "btn_stops": _("\U0001F6AB Stops"),
            "btn_tickets": _("\U0001F4E9 Tickets"),
            "btn_staff": _("\U0001F5C2 Tenure/Anniversary"),
            "btn_cancellations": _("\U0001F17E Cancellations"),
            "btn_courier_reports": _("\U0001F699 Courier reports"),
            "btn_restaurant_reports": _("\U0001F957 Restaurant reports"),
            "btn_metrics": _("\U0001F4C9 Metrics"),
            "btn_stock_balances": _("\U0001F69A Stock balances"),
            "btn_stops_rest": _("\U0001F3E0 Restaurant stops"),
            "btn_stops_key_ings": _("\U0001F9C0 Key ingredient stops"),
            "btn_stops_ings": _("\U0001F355 Ingredient stops"),
            "btn_stops_sector": _("\U0001F6A7 Sector stops"),
            "btn_apply": _("\U0001F44C Apply"),
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
        # Список заведений с учетом подписок из БД
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
            try:
                ctx_state = dialog_manager.current_context()
                if ctx_state.widget_data.get("units") is None:
                    # Подтягиваем уже подписанные заведения из БД
                    orders = await get_orders_by_post(session, event_chat.id, post)
                    selected = []
                    for order in orders:
                        if order.uuids:
                            selected.extend(order.uuids)
                    ctx_state.widget_data["units"] = selected
                    subs_by_post = dialog_manager.dialog_data.setdefault("subs_by_post", {})
                    subs_by_post[post] = selected
            except Exception:
                pass
        return {
            "units": units,
            **MenuGetters._texts(dialog_manager),
        }

    @staticmethod
    async def stocks_data(dialog_manager: DialogManager, **kwargs: Any) -> dict:
        """Готовит список категорий складских остатков."""
        # Категории складских остатков + предвыбор из БД
        _ = MenuGetters._translator(dialog_manager)
        session = dialog_manager.middleware_data.get("session")
        event_chat = dialog_manager.middleware_data.get("event_chat")
        post = dialog_manager.dialog_data.get("post")
        valid_ids = {item["id"] for item in STOCK_ITEMS}
        if session and event_chat and post == "stock":
            try:
                ctx_state = dialog_manager.current_context()
                if ctx_state.widget_data.get("stocks") is None:
                    orders = await get_orders_by_post(session, event_chat.id, "stock")
                    selected = []
                    for order in orders:
                        if order.params:
                            if "|" in order.params:
                                _prefix, raw = order.params.split("|", 1)
                                selected.extend([p for p in raw.split(",") if p in valid_ids])
                            else:
                                selected.extend([p for p in order.params.split(",") if p in valid_ids])
                    ctx_state.widget_data["stocks"] = selected
            except Exception:
                pass
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
