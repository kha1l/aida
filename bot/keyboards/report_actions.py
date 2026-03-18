from aiogram.filters.callback_data import CallbackData
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


class ReportActionCallback(CallbackData, prefix="report"):
    post: str
    action: str
    unit_uuid: str


def build_report_keyboard(
    post: str | None,
    unit_uuid: str | None,
) -> InlineKeyboardMarkup | None:
    """Возвращает inline-клавиатуру для отчёта из RabbitMQ."""
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
                ]
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
