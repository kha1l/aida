from typing import Callable
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def menu(_: Callable[[str], str]) -> InlineKeyboardMarkup:

    inline_keyboard = [
        [
            InlineKeyboardButton(
                text='🔊 Уведомления',
                callback_data='notice'
            )
        ],
        [
            InlineKeyboardButton(
                text='📑 Отчеты',
                callback_data='reports'
            )
        ],
        [
            InlineKeyboardButton(
                text='💬 Оперативные данные',
                callback_data='operation'
            )
        ],
        [
            InlineKeyboardButton(
                text='🛠 Настройки',
                callback_data='settings'
            )
        ],
        [
            InlineKeyboardButton(
                text='❎ Закрыть меню',
                callback_data='exit'
            )
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)