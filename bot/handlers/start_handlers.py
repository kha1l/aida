"""Стартовые команды и базовые обработчики бота."""
import contextlib
from typing import Callable, Optional, Dict, Any

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from bot.dialogs.texts import MenuTexts
from bot.dialogs.states import MenuSG
from bot.keyboards.info import new_account
from services.i18n import tr

router = Router()


@router.message(CommandStart())
async def start_(
    message: Message,
    dialog_manager: DialogManager,
    _: Callable[[str], str] = lambda s: s,
    ctx: Optional[Dict[str, Any]] = None,
) -> None:
    """Открывает главное меню и сбрасывает стек диалогов."""
    if not ctx:
        await message.answer(
            tr(_, MenuTexts.AUTH_REQUIRED_MESSAGE),
            reply_markup=new_account(_),
        )
        return

    # Перед новым /start удаляем предыдущее сообщение диалога, если оно осталось
    # в стеке aiogram_dialog. Это не дает копиться старым "шапкам" меню.
    with contextlib.suppress(Exception):
        stack = dialog_manager.current_stack()
        last_message_id = getattr(stack, "last_message_id", None)
        if last_message_id:
            await message.bot.delete_message(
                chat_id=message.chat.id,
                message_id=last_message_id,
            )
            stack.last_message_id = None

    # Запускаем главное меню, сбрасывая стек диалогов
    await dialog_manager.start(
        MenuSG.main,
        mode=StartMode.RESET_STACK,
        data={"ctx": ctx or {}},
    )
