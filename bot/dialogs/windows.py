from aiogram_dialog import Window
from aiogram_dialog.widgets.kbd import Button, Column, Row, Select, SwitchTo, Url, Multiselect, Group
from aiogram_dialog.widgets.text import Const, Format

from bot.dialogs.getters import MenuGetters
from bot.dialogs.handlers import MenuHandlers
from bot.dialogs.states import MenuSG
from bot.dialogs.texts import MenuTexts


class MenuWindows:
    """Окна меню для aiogram_dialog."""
    @staticmethod
    def main() -> Window:
        """Возвращает окно главного меню."""
        return Window(
            Format("{main_greeting}"),
            Column(
                SwitchTo(Format("{btn_notifications}"), id="notice", state=MenuSG.notice, on_click=MenuHandlers.set_type_notice),
                SwitchTo(Format("{btn_reports}"), id="reports", state=MenuSG.reports, on_click=MenuHandlers.set_type_reports),
                SwitchTo(Format("{btn_live_data}"), id="operation", state=MenuSG.operation),
                SwitchTo(Format("{btn_settings}"), id="settings", state=MenuSG.settings),
                Button(Format("{btn_close_menu}"), id="exit", on_click=MenuHandlers.on_exit),
            ),
            getter=MenuGetters.main_data,
            state=MenuSG.main,
        )

    @staticmethod
    def settings() -> Window:
        """Возвращает окно настроек приложения."""
        return Window(
            Format("{title_settings}"),
            Column(
                Url(
                    Format("{btn_manage_app}"),
                    id="manage_app",
                    url=Const("https://marketplace.dodois.io/apps/11ECF3AAF97D059CB9706F21406EBD11"),
                ),
                Url(
                    Format("{btn_kb}"),
                    id="kb",
                    url=Const("https://aida.kaiten.site"),
                ),
                SwitchTo(Format("{btn_change_language}"), id="lang", state=MenuSG.language),
                SwitchTo(Format("{btn_back}"), id="back", state=MenuSG.main),
            ),
            getter=MenuGetters.texts_data,
            state=MenuSG.settings,
        )

    @staticmethod
    def operation() -> Window:
        """Возвращает окно оперативных действий."""
        return Window(
            Format("{title_operation}"),
            Column(
                Button(Format("{btn_current_metrics}"), id="metrics", on_click=MenuHandlers.on_operation_action),
                Button(Format("{btn_network_revenue}"), id="revenue", on_click=MenuHandlers.on_operation_action),
                Button(Format("{btn_large_stocks}"), id="stock", on_click=MenuHandlers.on_operation_action),
                SwitchTo(Format("{btn_back}"), id="back", state=MenuSG.main),
            ),
            getter=MenuGetters.texts_data,
            state=MenuSG.operation,
        )

    @staticmethod
    def notice() -> Window:
        """Возвращает окно подписок на уведомления."""
        return Window(
            Format("{title_subscription}"),
            Column(
                SwitchTo(Format("{btn_birthdays}"), id="birthday", state=MenuSG.units, on_click=MenuHandlers.make_post_handler("birthday", MenuSG.units)),
                SwitchTo(Format("{btn_stops}"), id="stops", state=MenuSG.stops, on_click=MenuHandlers.set_type_stop),
                SwitchTo(Format("{btn_tickets}"), id="tickets", state=MenuSG.units, on_click=MenuHandlers.make_post_handler("tickets", MenuSG.units)),
                SwitchTo(Format("{btn_staff}"), id="staff", state=MenuSG.units, on_click=MenuHandlers.make_post_handler("staff", MenuSG.units)),
                SwitchTo(Format("{btn_cancellations}"), id="refusal", state=MenuSG.units, on_click=MenuHandlers.make_post_handler("refusal", MenuSG.units)),
                SwitchTo(Format("{btn_back}"), id="back", state=MenuSG.main),
            ),
            getter=MenuGetters.texts_data,
            state=MenuSG.notice,
        )

    @staticmethod
    def reports() -> Window:
        """Возвращает окно подписок на отчёты."""
        return Window(
            Format("{title_subscription}"),
            Column(
                SwitchTo(Format("{btn_network_revenue}"), id="revenue", state=MenuSG.units, on_click=MenuHandlers.make_post_handler("revenue", MenuSG.units)),
                SwitchTo(Format("{btn_courier_reports}"), id="couriers", state=MenuSG.units, on_click=MenuHandlers.make_post_handler("couriers", MenuSG.units)),
                SwitchTo(Format("{btn_restaurant_reports}"), id="stationary", state=MenuSG.units, on_click=MenuHandlers.make_post_handler("stationary", MenuSG.units)),
                SwitchTo(Format("{btn_metrics}"), id="metrics", state=MenuSG.units, on_click=MenuHandlers.make_post_handler("metrics", MenuSG.units)),
                SwitchTo(Format("{btn_stock_balances}"), id="stock", state=MenuSG.stocks, on_click=MenuHandlers.set_type_stock),
                SwitchTo(Format("{btn_back}"), id="back", state=MenuSG.main),
            ),
            getter=MenuGetters.texts_data,
            state=MenuSG.reports,
        )

    @staticmethod
    def stops() -> Window:
        """Возвращает окно выбора типов стопов."""
        return Window(
            Format("{title_stops}"),
            Column(
                SwitchTo(Format("{btn_stops_rest}"), id="stops_rest", state=MenuSG.units, on_click=MenuHandlers.make_stop_post_handler("stops_rest")),
                SwitchTo(Format("{btn_stops_key_ings}"), id="stops_key_ings", state=MenuSG.units, on_click=MenuHandlers.make_stop_post_handler("stops_key_ings")),
                SwitchTo(Format("{btn_stops_ings}"), id="stops_ings", state=MenuSG.units, on_click=MenuHandlers.make_stop_post_handler("stops_ings")),
                SwitchTo(Format("{btn_stops_sector}"), id="stops_sector", state=MenuSG.units, on_click=MenuHandlers.make_stop_post_handler("stops_sector")),
                SwitchTo(Format("{btn_back}"), id="back", state=MenuSG.notice, on_click=MenuHandlers.set_type_notice),
            ),
            getter=MenuGetters.texts_data,
            state=MenuSG.stops,
        )

    @staticmethod
    def stocks() -> Window:
        """Возвращает окно выбора категорий складских остатков."""
        return Window(
            Format("{title_stocks}"),
            Column(
                Multiselect(
                    checked_text=Format("{item[label]} \u2705"),
                    unchecked_text=Format("{item[label]} \u2611\uFE0F"),
                    id="stocks",
                    items="stocks",
                    item_id_getter=lambda item: item["id"],
                ),
                Row(
                    Button(Format("{btn_apply}"), id="commit_stock", on_click=MenuHandlers.on_stock_commit),
                    SwitchTo(Format("{btn_back}"), id="back", state=MenuSG.reports, on_click=MenuHandlers.set_type_reports),
                ),
            ),
            getter=MenuGetters.stocks_data,
            state=MenuSG.stocks,
        )

    @staticmethod
    def units() -> Window:
        """Возвращает окно выбора заведений для подписки."""
        return Window(
            Format("{title_units}"),
            Group(
                Multiselect(
                    checked_text=Format("\u2705 {item[name]}"),
                    unchecked_text=Format("\u2611\uFE0F {item[name]}"),
                    id="units",
                    items="units",
                    item_id_getter=lambda item: item["uuid"],
                ),
                id="units_group",
                width=2,  # Два столбца для списка заведений
            ),
            Row(
                Button(Format("{btn_subscribe_all}"), id="units_all", on_click=MenuHandlers.on_units_subscribe_all),
                Button(Format("{btn_unsubscribe_all}"), id="units_none", on_click=MenuHandlers.on_units_unsubscribe_all),
            ),
            Row(
                Button(Format("{btn_apply}"), id="commit_units", on_click=MenuHandlers.on_units_commit),
                Button(Format("{btn_back}"), id="back_units", on_click=MenuHandlers.on_units_back),
            ),
            getter=MenuGetters.units_data,
            state=MenuSG.units,
        )

    @staticmethod
    @staticmethod
    def language() -> Window:
        """Возвращает окно выбора языка интерфейса."""
        return Window(
            Format("{title_language}"),
            Column(
                Select(
                    Format("{item[label]}"),
                    id="lang_select",
                    item_id_getter=lambda item: item["id"],
                    items="languages",
                    on_click=MenuHandlers.on_language_selected,
                ),
                SwitchTo(Format("{btn_back}"), id="back", state=MenuSG.settings),
            ),
            getter=MenuGetters.language_data,
            state=MenuSG.language,
        )
