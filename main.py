import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
headers = {"Authorization": f"Bearer {API_KEY}"}

async def fetch_api(endpoint, method="GET", json_data=None, params=None):
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{API_URL}{endpoint}"
            if method == "GET":
                async with session.get(url, headers=headers, params=params) as resp:
                    if resp.status == 403: return {"error": "not_linked"}
                    return await resp.json()
            else:
                async with session.post(url, headers=headers, json=json_data) as resp:
                    if resp.status == 403: return {"error": "not_linked"}
                    return await resp.json()
    except Exception as e:
        return {"error": "server error", "details": str(e)}

# Виправлена функція: тепер вона розуміє, що успішні ринки/замовлення - це списки
def check_link(res):
    if isinstance(res, list):
        return True
    return res.get("error") != "not_linked"

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Вітаю! Я бот маркету.\n\n"
        "Щоб користуватись ботом, прив'яжіть акаунт:\n"
        "1. Зайдіть на сервер Minecraft.\n"
        "2. Напишіть `/tg link`.\n"
        "3. Надішліть мені код командою `/link <code>`."
    )

@dp.message(Command("link"))
async def cmd_link(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Використання: `/link <код>`", parse_mode="Markdown")
        return
    
    res = await fetch_api("/link", "POST", {"telegram_id": message.from_user.id, "code": args[1]})
    await message.answer(res.get("message", "Помилка сервера."))

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    res = await fetch_api("/balance", params={"tg_id": message.from_user.id})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт (/start)")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка з'єднання з сервером.")
    
    await message.answer(f"💰 Ваш віртуальний баланс: {res['balance']} ізумрудів.")

@dp.message(Command("market"))
async def cmd_market(message: types.Message):
    res = await fetch_api("/market", params={"tg_id": message.from_user.id})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження маркету.")
    
    if not res:
        await message.answer("Маркет порожній.")
        return

    text = "🛒 **Товари на маркеті:**\n\n"
    for item in res[:20]:
        text += f"▪️ **{item['item']}** | Ціна: {item['price']} | Продавець: {item['seller']}\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("orders"))
async def cmd_orders(message: types.Message):
    res = await fetch_api("/orders", params={"tg_id": message.from_user.id})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження замовлень.")
    
    if not res: return await message.answer("Замовлень немає.")

    text = "📋 **Активні замовлення:**\n\n"
    for req in res[:20]:
        text += f"▪️ **{req['material']}** | Ціна: {req['price']} | Замовив: {req['customer']}\n"
    text += "\n*(Щоб виконати замовлення, зайдіть у гру та відкрийте /orders)*"
    await message.answer(text, parse_mode="Markdown")

@dp.message(Command("myorders"))
async def cmd_myorders(message: types.Message):
    res = await fetch_api("/myorders", params={"tg_id": message.from_user.id})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження ваших замовлень.")
    
    if not res: return await message.answer("У вас немає замовлень.")

    for req in res:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Скасувати", callback_data=f"cancel_{req['id']}")]
        ])
        await message.answer(f"📦 Замовлення: **{req['material']}**\nНагорода: {req['price']} ізумрудів", reply_markup=kb, parse_mode="Markdown")

@dp.callback_query(F.data.startswith("cancel_"))
async def callback_cancel(callback: types.CallbackQuery):
    order_id = int(callback.data.split("_")[1])
    res = await fetch_api("/cancel", "POST", {"telegram_id": callback.from_user.id, "order_id": order_id})
    
    if res.get("success"):
        await callback.message.edit_text("✅ Замовлення скасовано! Кошти надіслано в депо.")
    else:
        await callback.answer(res.get("message", "Помилка"), show_alert=True)

@dp.message(Command("order"))
async def cmd_order(message: types.Message):
    args = message.text.split()
    if len(args) != 5:
        await message.answer("Використання: `/order <предмет> <кількість> <ціна> <днів>`", parse_mode="Markdown")
        return
    
    try:
        data = {
            "telegram_id": message.from_user.id,
            "material": args[1], "count": int(args[2]),
            "price": int(args[3]), "days": int(args[4])
        }
    except ValueError:
        return await message.answer("Кількість, ціна та дні мають бути числами!")

    res = await fetch_api("/order", "POST", data)
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    await message.answer(res.get("message", "Помилка сервера."))

@dp.message(Command("send"))
async def cmd_send(message: types.Message):
    args = message.text.split()
    if len(args) != 3:
        return await message.answer("Використання: `/send <нік> <сума>`", parse_mode="Markdown")
    
    try:
        data = {
            "telegram_id": message.from_user.id,
            "target_name": args[1],
            "amount": int(args[2])
        }
    except ValueError:
        return await message.answer("Сума має бути числом!")

    res = await fetch_api("/send", "POST", data)
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    await message.answer(res.get("message", "Помилка сервера."))

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())