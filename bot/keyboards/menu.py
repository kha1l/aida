from typing import Callable
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def menu(_: Callable[[str], str]) -> InlineKeyboardMarkup:
    """Строит старую inline-клавиатуру главного меню."""

    inline_keyboard = [
        [
            InlineKeyboardButton(
                text=_('🔊 Notifications'),
                callback_data='notice'
            )
        ],
        [
            InlineKeyboardButton(
                text=_('📑 Reports'),
                callback_data='reports'
            )
        ],
        [
            InlineKeyboardButton(
                text=_('💬 Live data'),
                callback_data='operation'
            )
        ],
        [
            InlineKeyboardButton(
                text=_('🛠 Settings'),
                callback_data='settings'
            )
        ],
        [
            InlineKeyboardButton(
                text=_('❎ Close menu'),
                callback_data='exit'
            )
        ]
    ]

    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)
