import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
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
        "2. Напишіть <code>/tg link</code>.\n"
        "3. Надішліть мені код командою <code>/link &lt;код&gt;</code>.",
        parse_mode="HTML"
    )
    
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "🛠 <b>Доступні команди:</b>\n\n"
        "🔸 <b>Акаунт та Баланс:</b>\n"
        "<code>/link &lt;код&gt;</code> — Прив'язати акаунт з гри\n"
        "<code>/balance</code> — Перевірити свій віртуальний баланс\n"
        "<code>/send &lt;нік&gt; &lt;сума&gt;</code> — Переказати ізумруди іншому гравцю\n\n"
        "🔸 <b>Ринок та Замовлення:</b>\n"
        "<code>/market [сторінка]</code> — Переглянути товари, що продаються\n"
        "<code>/orders [сторінка]</code> — Список активних замовлень сервера\n"
        "<code>/order &lt;предмет&gt; &lt;кількість&gt; &lt;ціна&gt; &lt;днів&gt;</code> — Створити нове замовлення\n\n"
        "🔸 <b>Керування своїм:</b>\n"
        "<code>/myorders [сторінка]</code> — Список ваших створених замовлень\n"
        "<code>/myorders cancel &lt;ID&gt;</code> — Скасувати своє замовлення за його ID\n\n"
        "ℹ️ <i>Підказка: [сторінка] — необов'язковий параметр. Наприклад: /market 2</i>"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("link"))
async def cmd_link(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        await message.answer("Використання: <code>/link &lt;код&gt;</code>", parse_mode="HTML")
        return
    
    res = await fetch_api("/link", "POST", {"telegram_id": message.from_user.id, "code": args[1]})
    await message.answer(res.get("message", "Помилка сервера."))

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    res = await fetch_api("/balance", params={"tg_id": message.from_user.id})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт (/start)")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка з'єднання з сервером.")
    
    await message.answer(f"💰 Ваш віртуальний баланс: <b>{res['balance']}</b> ізумрудів.", parse_mode="HTML")

@dp.message(Command("market"))
async def cmd_market(message: types.Message):
    args = message.text.split()
    page = 1
    if len(args) == 2 and args[1].isdigit():
        page = int(args[1])

    res = await fetch_api("/market", params={"tg_id": message.from_user.id, "page": page - 1})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження маркету.")
    
    if not res:
        return await message.answer(f"Маркет порожній на сторінці {page}.")

    text = f"🛒 <b>Товари на маркеті (Сторінка {page}):</b>\n\n"
    for item in res:
        text += f"▪️ ID: <code>{item['id']}</code> | <b>{item['item']}</b> | Ціна: {item['price']} | Продавець: <code>{item['seller']}</code>\n"
    
    if len(res) == 40:
        text += f"\n<i>Наступна сторінка:</i> <code>/market {page + 1}</code>"

    await message.answer(text, parse_mode="HTML")

@dp.message(Command("orders"))
async def cmd_orders(message: types.Message):
    args = message.text.split()
    page = 1
    if len(args) == 2 and args[1].isdigit():
        page = int(args[1])

    res = await fetch_api("/orders", params={"tg_id": message.from_user.id, "page": page - 1})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження замовлень.")
    
    if not res: return await message.answer(f"Замовлень немає на сторінці {page}.")

    text = f"📋 <b>Активні замовлення (Сторінка {page}):</b>\n\n"
    for req in res:
        text += f"▪️ ID: <code>{req['id']}</code> | <b>{req['material']}</b> | Нагорода: {req['price']} | Замовив: <code>{req['customer']}</code>\n"
    
    text += "\n<i>(Щоб виконати замовлення, зайдіть у гру та відкрийте /orders)</i>"
    if len(res) == 40:
        text += f"\n\n<i>Наступна сторінка:</i> <code>/orders {page + 1}</code>"

    await message.answer(text, parse_mode="HTML")

@dp.message(Command("myorders"))
async def cmd_myorders(message: types.Message):
    args = message.text.split()
    
    # Логіка для: /myorders cancel <ID>
    if len(args) == 3 and args[1].lower() == "cancel" and args[2].isdigit():
        order_id = int(args[2])
        res = await fetch_api("/cancel", "POST", {"telegram_id": message.from_user.id, "order_id": order_id})
        if res.get("success"):
            return await message.answer("✅ Замовлення скасовано! Кошти надіслано в депо.")
        else:
            return await message.answer(res.get("message", "Помилка"))

    # Логіка для пагінації: /myorders <page>
    page = 1
    if len(args) == 2 and args[1].isdigit():
        page = int(args[1])

    res = await fetch_api("/myorders", params={"tg_id": message.from_user.id, "page": page - 1})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження ваших замовлень.")
    
    if not res: return await message.answer(f"У вас немає замовлень на сторінці {page}.")

    text = f"📦 <b>Ваші замовлення (Сторінка {page}):</b>\n\n"
    for req in res:
        text += f"▪️ ID: <code>{req['id']}</code> | <b>{req['material']}</b> | Нагорода: {req['price']} ізумрудів\n"
    
    text += f"\n<i>Для скасування замовлення напишіть:</i>\n<code>/myorders cancel &lt;ID&gt;</code>"
    if len(res) == 40:
        text += f"\n\n<i>Наступна сторінка:</i> <code>/myorders {page + 1}</code>"

    await message.answer(text, parse_mode="HTML")

@dp.message(Command("order"))
async def cmd_order(message: types.Message):
    args = message.text.split()
    if len(args) != 5:
        await message.answer("Використання: <code>/order &lt;предмет&gt; &lt;кількість&gt; &lt;ціна&gt; &lt;днів&gt;</code>", parse_mode="HTML")
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
        return await message.answer("Використання: <code>/send &lt;нік&gt; &lt;сума&gt;</code>", parse_mode="HTML")
    
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