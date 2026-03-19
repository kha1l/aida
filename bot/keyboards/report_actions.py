from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


HIDE_REPORT_CALLBACK = "hide"
HIDE_ONLY_POSTS = {"certificates", "later", "waiting", "sectors", "longers"}
WAITING_THRESHOLD_VALUES_MINUTES = (1, 2, 3, 5, 10)


class ReportActionCallback(CallbackData, prefix="report"):
    post: str
    action: str
    unit_uuid: str


class WaitingThresholdCallback(CallbackData, prefix="report_wait"):
    post: str
    unit_uuid: str
    minutes: int


def _hide_row() -> list[InlineKeyboardButton]:
    return [
        InlineKeyboardButton(
            text="\U0001F504 Скрыть отчет",
            callback_data=HIDE_REPORT_CALLBACK,
        )
    ]


def _with_hide(keyboard: InlineKeyboardMarkup | None) -> InlineKeyboardMarkup:
    if keyboard is None:
        return InlineKeyboardMarkup(inline_keyboard=[_hide_row()])
    keyboard.inline_keyboard.append(_hide_row())
    return keyboard


def build_waiting_threshold_keyboard(
    post: str,
    unit_uuid: str,
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []

    for index, minutes in enumerate(WAITING_THRESHOLD_VALUES_MINUTES, start=1):
        current_row.append(
            InlineKeyboardButton(
                text=f"{minutes}мин",
                callback_data=WaitingThresholdCallback(
                    post=post,
                    unit_uuid=unit_uuid,
                    minutes=minutes,
                ).pack(),
            )
        )
        if index in {3, len(WAITING_THRESHOLD_VALUES_MINUTES)}:
            rows.append(current_row)
            current_row = []

    return InlineKeyboardMarkup(inline_keyboard=rows)


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
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="\U0001F4A4 Ожидания курьеров",
                        callback_data=ReportActionCallback(
                            post=post,
                            action="waiting",
                            unit_uuid=unit_uuid,
                        ).pack(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="\u231A Опоздания/прогулы",
                        callback_data=ReportActionCallback(
                            post=post,
                            action="later",
                            unit_uuid=unit_uuid,
                        ).pack(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="\U0001F4D1 Сертификаты",
                        callback_data=ReportActionCallback(
                            post=post,
                            action="certificates",
                            unit_uuid=unit_uuid,
                        ).pack(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🌏 Сектора",
                        callback_data=ReportActionCallback(
                            post=post,
                            action="sectors",
                            unit_uuid=unit_uuid,
                        ).pack(),
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🛵 Долгие доставки",
                        callback_data=ReportActionCallback(
                            post=post,
                            action="longers",
                            unit_uuid=unit_uuid,
                        ).pack(),
                    )
                ],
            ]
        )

    if post == "stationary":
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="\U0001F4C3 Опоздания в ресторане",
                        callback_data=ReportActionCallback(
                            post=post,
                            action="later_rest",
                            unit_uuid=unit_uuid,
                        ).pack(),
                    )
                ]
            ]
        )

    return None
