import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, html
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from config import Config


TOKEN = Config.BOT_TOKEN
ADMINS_IDS = Config.ADMINS_IDS

dp = Dispatcher()


@dp.message(Command("start"))
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command.
    """
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!, Your ID: `{message.from_user.id}`")


@dp.message(Command("admin"))
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/admin` command and check if they're in an admin list.
    """
    if message.from_user.id in ADMINS_IDS:
        await message.answer(f"You are admin!")
    else:
        await message.answer(f"You are not admin.")


@dp.message()
async def echo_handler(message: Message) -> None:
    """
    Handler will forward receive a message back to the sender

    By default, message handler will handle all message types (like a text, photo, sticker etc.)
    """
    try:
        await message.send_copy(chat_id=message.chat.id)
    except TypeError:
        await message.answer("Nice try!")


async def main() -> None:
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())