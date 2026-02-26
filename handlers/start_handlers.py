from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from typing import Callable
from keyboards.menu import menu

router = Router()

@router.message(CommandStart())
async def start_(message: Message, _: Callable[[str], str]) -> None:
    await message.answer(
        _(f'👋 Привет, {message.from_user.full_name}! \n\n'
        f'Я - Aida. Помогаю удаленно управлять рестораном или сетью ресторанов '
        f'Dodo Brands и принимать правильные управленческие решения.'),
        reply_markup=menu(_),
        parse_mode="HTML"
    )
