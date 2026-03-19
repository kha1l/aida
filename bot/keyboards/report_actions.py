"""Фабрики inline-клавиатур для отчетов и manual-запусков Dagster jobs."""

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


HIDE_REPORT_CALLBACK = "hide"
# Для этих payload из очереди не нужны action-кнопки — достаточно дать кнопку скрытия.
HIDE_ONLY_POSTS = {
    "certificates",
    "later",
    "waiting",
    "sectors",
    "longers",
    "later_rest",
    "assembly_rest",
    "drink_rest",
}
WAITING_THRESHOLD_VALUES_MINUTES = (1, 2, 3, 5, 10)
DRINK_THRESHOLD_VALUES_MINUTES = (1, 2, 3, 4, 5)
COURIERS_REPORT_BUTTONS = (
    ("\U0001F4A4 Ожидания курьеров", "waiting"),
    ("\u231A Опоздания/прогулы", "later"),
    ("\U0001F4D1 Сертификаты", "certificates"),
    ("🌏 Сектора", "sectors"),
    ("🛵 Долгие доставки", "longers"),
)
STATIONARY_REPORT_BUTTONS = (
    ("\U0001F4C3 Долгие заказы", "later_rest"),
    ("🧳 Долгая сборка заказа", "assembly_rest"),
    ("🍺 Долгие напитки", "drink_rest"),
)


class ReportActionCallback(CallbackData, prefix="report"):
    """Callback для прямых действий по отчету конкретного заведения."""
    post: str
    action: str
    unit_uuid: str


class WaitingThresholdCallback(CallbackData, prefix="report_wait"):
    post: str
    unit_uuid: str
    minutes: int


class DrinkThresholdCallback(CallbackData, prefix="report_drink"):
    post: str
    unit_uuid: str
    minutes: int


def _hide_row() -> list[InlineKeyboardButton]:
    """Строит единственную кнопку для удаления уже отправленного отчета."""
    return [
        InlineKeyboardButton(
            text="\U0001F504 Скрыть отчет",
            callback_data=HIDE_REPORT_CALLBACK,
        )
    ]


def _with_hide(keyboard: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup:
    """Добавляет кнопку скрытия к существующей клавиатуре или создает ее с нуля."""
    if keyboard is None:
        return InlineKeyboardMarkup(inline_keyboard=[_hide_row()])
    keyboard.inline_keyboard.append(_hide_row())
    return keyboard


def _action_button(
    *,
    text: str,
    post: str,
    action: str,
    unit_uuid: str,
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=text,
        callback_data=ReportActionCallback(
            post=post,
            action=action,
            unit_uuid=unit_uuid,
        ).pack(),
    )


def _build_action_keyboard(
    *,
    post: str,
    unit_uuid: str,
    buttons: tuple[tuple[str, str], ...],
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_action_button(text=text, post=post, action=action, unit_uuid=unit_uuid)]
            for text, action in buttons
        ]
    )


def _build_threshold_keyboard(
    *,
    post: str,
    unit_uuid: str,
    minutes_values: tuple[int, ...],
    callback_factory,
) -> InlineKeyboardMarkup:
    """Строит компактную двухрядную клавиатуру выбора порога."""
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for index, minutes in enumerate(minutes_values, start=1):
        current_row.append(
            InlineKeyboardButton(
                text=f"{minutes}мин",
                callback_data=callback_factory(
                    post=post,
                    unit_uuid=unit_uuid,
                    minutes=minutes,
                ).pack(),
            )
        )
        if index in {3, len(minutes_values)}:
            rows.append(current_row)
            current_row = []

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_waiting_threshold_keyboard(
    post: str,
    unit_uuid: str,
) -> InlineKeyboardMarkup:
    return _build_threshold_keyboard(
        post=post,
        unit_uuid=unit_uuid,
        minutes_values=WAITING_THRESHOLD_VALUES_MINUTES,
        callback_factory=WaitingThresholdCallback,
    )


def build_drink_threshold_keyboard(
    post: str,
    unit_uuid: str,
) -> InlineKeyboardMarkup:
    return _build_threshold_keyboard(
        post=post,
        unit_uuid=unit_uuid,
        minutes_values=DRINK_THRESHOLD_VALUES_MINUTES,
        callback_factory=DrinkThresholdCallback,
    )


def build_report_keyboard(
    post: str | None,
    unit_uuid: str | None,
) -> InlineKeyboardMarkup | None:
    """Возвращает inline-клавиатуру для отчёта из RabbitMQ."""
    if post in HIDE_ONLY_POSTS:
        return _with_hide(None)

    if not post or not unit_uuid:
        return None

    if post == "couriers":
        return _build_action_keyboard(
            post=post,
            unit_uuid=unit_uuid,
            buttons=COURIERS_REPORT_BUTTONS,
        )

    if post == "stationary":
        return _build_action_keyboard(
            post=post,
            unit_uuid=unit_uuid,
            buttons=STATIONARY_REPORT_BUTTONS,
        )

    return None
