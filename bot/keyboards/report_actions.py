"""Фабрики inline-клавиатур для отчетов и manual-запусков Dagster jobs."""

from typing import Callable

from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo


HIDE_REPORT_CALLBACK = "hide"
Translator = Callable[[str], str]
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
    "tracking",
    "metrics",
    "revenue",
    "stock",
}
WAITING_THRESHOLD_VALUES_MINUTES = (1, 2, 3, 5, 10)
DRINK_THRESHOLD_VALUES_MINUTES = (1, 2, 3, 4, 5)
COURIERS_REPORT_BUTTONS = (
    ("💤 Courier waiting", "waiting"),
    ("⌚ Late / missed shifts", "later"),
    ("📑 Certificates", "certificates"),
    ("🌏 Sectors", "sectors"),
    ("🛵 Long deliveries", "longers"),
)
STATIONARY_REPORT_BUTTONS = (
    ("📃 Long dine-in orders", "later_rest"),
    ("🧳 Slow order assembly", "assembly_rest"),
    ("🍺 Slow drinks", "drink_rest"),
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


def _hide_row(translate: Translator) -> list[InlineKeyboardButton]:
    """Строит единственную кнопку для удаления уже отправленного отчета."""
    return [
        InlineKeyboardButton(
            text=translate("\U0001F504 Hide report"),
            callback_data=HIDE_REPORT_CALLBACK,
        )
    ]


def _with_hide(
    keyboard: InlineKeyboardMarkup | None,
    translate: Translator,
) -> InlineKeyboardMarkup:
    """Добавляет кнопку скрытия к существующей клавиатуре или создает ее с нуля."""
    if keyboard is None:
        return InlineKeyboardMarkup(inline_keyboard=[_hide_row(translate)])
    keyboard.inline_keyboard.append(_hide_row(translate))
    return keyboard


def _action_button(
    *,
    text: str,
    post: str,
    action: str,
    unit_uuid: str,
    translate: Translator,
) -> InlineKeyboardButton:
    return InlineKeyboardButton(
        text=translate(text),
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
    translate: Translator,
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [_action_button(text=text, post=post, action=action, unit_uuid=unit_uuid, translate=translate)]
            for text, action in buttons
        ]
    )


def _build_threshold_keyboard(
    *,
    post: str,
    unit_uuid: str,
    minutes_values: tuple[int, ...],
    callback_factory,
    translate: Translator,
) -> InlineKeyboardMarkup:
    """Строит компактную двухрядную клавиатуру выбора порога."""
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for index, minutes in enumerate(minutes_values, start=1):
        current_row.append(
            InlineKeyboardButton(
                text=translate("{minutes} min").format(minutes=minutes),
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
    translate: Translator | None = None,
) -> InlineKeyboardMarkup:
    translate = translate or (lambda message: message)
    return _build_threshold_keyboard(
        post=post,
        unit_uuid=unit_uuid,
        minutes_values=WAITING_THRESHOLD_VALUES_MINUTES,
        callback_factory=WaitingThresholdCallback,
        translate=translate,
    )


def build_waiting_webapp_threshold_keyboard(
    *,
    urls_by_minutes: dict[int, str],
    translate: Translator | None = None,
) -> InlineKeyboardMarkup:
    """Строит клавиатуру порогов ожидания, где каждая кнопка открывает web-отчет."""
    return _build_webapp_threshold_keyboard(
        minutes_values=WAITING_THRESHOLD_VALUES_MINUTES,
        urls_by_minutes=urls_by_minutes,
        translate=translate,
    )


def build_drink_webapp_threshold_keyboard(
    *,
    urls_by_minutes: dict[int, str],
    translate: Translator | None = None,
) -> InlineKeyboardMarkup:
    """Строит клавиатуру порогов напитков, где каждая кнопка открывает web-отчет."""
    return _build_webapp_threshold_keyboard(
        minutes_values=DRINK_THRESHOLD_VALUES_MINUTES,
        urls_by_minutes=urls_by_minutes,
        translate=translate,
    )


def _build_webapp_threshold_keyboard(
    *,
    minutes_values: tuple[int, ...],
    urls_by_minutes: dict[int, str],
    translate: Translator | None = None,
) -> InlineKeyboardMarkup:
    """Строит компактную клавиатуру выбора порога с WebApp-ссылками."""
    translate = translate or (lambda message: message)
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for index, minutes in enumerate(minutes_values, start=1):
        url = urls_by_minutes.get(minutes)
        if not url:
            continue
        current_row.append(
            InlineKeyboardButton(
                text=translate("{minutes} min").format(minutes=minutes),
                web_app=WebAppInfo(url=url),
            )
        )
        if index in {3, len(minutes_values)}:
            if current_row:
                rows.append(current_row)
            current_row = []

    if current_row:
        rows.append(current_row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_report_webapp_keyboard(
    *,
    url: str,
    text: str = "Open web report",
    translate: Translator | None = None,
) -> InlineKeyboardMarkup:
    """Строит одну WebApp-кнопку для открытия готовящегося отчета."""
    translate = translate or (lambda message: message)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=translate(text),
                    web_app=WebAppInfo(url=url),
                )
            ]
        ]
    )


def build_drink_threshold_keyboard(
    post: str,
    unit_uuid: str,
    translate: Translator | None = None,
) -> InlineKeyboardMarkup:
    translate = translate or (lambda message: message)
    return _build_threshold_keyboard(
        post=post,
        unit_uuid=unit_uuid,
        minutes_values=DRINK_THRESHOLD_VALUES_MINUTES,
        callback_factory=DrinkThresholdCallback,
        translate=translate,
    )


def build_report_keyboard(
    post: str | None,
    unit_uuid: str | None,
    translate: Translator | None = None,
) -> InlineKeyboardMarkup | None:
    """Возвращает inline-клавиатуру для отчёта из RabbitMQ."""
    translate = translate or (lambda message: message)

    if post in HIDE_ONLY_POSTS:
        return _with_hide(None, translate)

    if not post or not unit_uuid:
        return None

    if post == "couriers":
        return _build_action_keyboard(
            post=post,
            unit_uuid=unit_uuid,
            buttons=COURIERS_REPORT_BUTTONS,
            translate=translate,
        )

    if post == "stationary":
        return _build_action_keyboard(
            post=post,
            unit_uuid=unit_uuid,
            buttons=STATIONARY_REPORT_BUTTONS,
            translate=translate,
        )

    return None
