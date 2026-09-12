from aiogram import Router
from aiogram.types import Message

router = Router(name="common")


@router.message()
async def on_unrecognized_message(message: Message) -> None:
    await message.answer("Не розумію цю команду. Скористайся меню нижче або /start.")
