from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def new_account(_) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=_(f'▶️ Авторизация'),
                    url='https://marketplace.dodois.io/11ecf3aaf97d059cb9706f21406ebd11'
                )
            ],
            [
                InlineKeyboardButton(
                    text=_(f'🗄 База знаний'),
                    url='https://aida.kaiten.site'
                )
            ],
            [
                InlineKeyboardButton(
                    text=_('🤝 Aida Community'),
                    url='https://t.me/aidacommunity'
                )
            ]
        ]
    )
