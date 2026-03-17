from typing import Callable, Optional, Dict, Any

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode

from bot.dialogs.states import MenuSG

router = Router()

@router.message(CommandStart())
async def start_(
    message: Message,
    dialog_manager: DialogManager,
    _: Callable[[str], str] = lambda s: s,
    ctx: Optional[Dict[str, Any]] = None,
) -> None:
    # Запускаем главное меню, сбрасывая стек диалогов
    await dialog_manager.start(
        MenuSG.main,
        mode=StartMode.RESET_STACK,
        data={"ctx": ctx or {}},
    )
