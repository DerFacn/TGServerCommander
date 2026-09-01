import os
import asyncio
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiohttp
from aiohttp import web

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL")
API_KEY = os.getenv("API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
headers = {"Authorization": f"Bearer {API_KEY}"}

# Глобальна змінна для веб-сервера
runner = None

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
    if isinstance(res, dict) and res.get("error") == "not_linked":
        return False
    return True

# --- Webhook Server для отримання сповіщень з Minecraft ---
async def handle_notify(request):
    try:
        data = await request.json()
        tg_id = data.get("telegram_id")
        msg = data.get("message")
        if tg_id and msg:
            await bot.send_message(chat_id=tg_id, text=msg, parse_mode="HTML")
        return web.Response(text="OK")
    except Exception as e:
        return web.Response(text=str(e), status=500)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 Вітаю! Я бот маркету.\n\n"
        "Щоб користуватись ботом, прив'яжіть акаунт:\n"
        "1. Зайдіть на сервер Minecraft.\n"
        "2. Напишіть <code>/tg link</code>.\n"
        "3. Надішліть мені код командою <code>/link &lt;код&gt;</code>.\n\n"
        "Введіть <code>/help</code> для перегляду всіх команд.",
        parse_mode="HTML"
    )

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "🛠 <b>Доступні команди:</b>\n\n"
        "🔸 <b>Акаунт та Баланс:</b>\n"
        "<code>/link &lt;код&gt;</code> — Прив'язати акаунт\n"
        "<code>/balance</code> — Перевірити віртуальний баланс\n"
        "<code>/send &lt;нік&gt; &lt;сума&gt;</code> — Переказати ізумруди\n"
        "<code>/settings</code> — Налаштування сповіщень 🔔\n\n"
        "🔸 <b>Ринок та Замовлення:</b>\n"
        "<code>/market [сторінка]</code> — Переглянути товари\n"
        "<code>/details &lt;id&gt;</code> — Показати чари та ефекти предмета\n"
        "<code>/orders [сторінка]</code> — Активні замовлення\n"
        "<code>/order &lt;предмет&gt; &lt;кількість&gt; &lt;ціна&gt; &lt;днів&gt;</code> — Нове замовлення\n\n"
        "🔸 <b>Керування своїм:</b>\n"
        "<code>/myorders [сторінка]</code> — Список ваших замовлень\n"
        "<code>/depot [сторінка]</code> — Забрати повернуті ізумруди\n"
    )
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("link"))
async def cmd_link(message: types.Message):
    args = message.text.split()
    if len(args) != 2:
        return await message.answer("Використання: <code>/link &lt;код&gt;</code>", parse_mode="HTML")
    
    res = await fetch_api("/link", "POST", {"telegram_id": message.from_user.id, "code": args[1]})
    await message.answer(res.get("message", "Помилка сервера."))

@dp.message(Command("balance"))
async def cmd_balance(message: types.Message):
    res = await fetch_api("/balance", params={"tg_id": message.from_user.id})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт (/start)")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка з'єднання з сервером.")
    
    await message.answer(f"💰 Ваш віртуальний баланс: <b>{res['balance']}</b> ізумрудів.", parse_mode="HTML")

@dp.message(Command("settings"))
async def cmd_settings(message: types.Message):
    res = await fetch_api("/settings", params={"tg_id": message.from_user.id})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження налаштувань.")
    
    def get_btn(text, val, key):
        emoji = "🟢 Так" if val else "🔴 Ні"
        return InlineKeyboardButton(text=f"{text}: {emoji}", callback_data=f"toggle_{key}")

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [get_btn("Замовлення", res.get('notify_orders', False), "orders")],
        [get_btn("Маркет", res.get('notify_market', False), "market")],
        [get_btn("Пересилання", res.get('notify_transfers', False), "transfers")]
    ])
    await message.answer("⚙️ <b>Налаштування сповіщень:</b>", reply_markup=kb, parse_mode="HTML")

# БЕЗПЕЧНИЙ ОБРОБНИК КНОПОК НАЛАШТУВАНЬ
@dp.callback_query(F.data.startswith("toggle_"))
async def callback_toggle(callback: types.CallbackQuery):
    setting = callback.data.split("_")[1]
    res = await fetch_api("/settings/toggle", "POST", {"telegram_id": callback.from_user.id, "setting": setting})
    
    # Запобігаємо падінню, якщо натиснув неавторизований користувач
    if isinstance(res, dict) and "error" in res:
        await callback.answer("Помилка: " + res.get("error", "Невідома помилка"), show_alert=True)
        return

    if res.get("success"):
        new_settings = await fetch_api("/settings", params={"tg_id": callback.from_user.id})
        if isinstance(new_settings, dict) and "error" in new_settings:
            await callback.answer("Помилка завантаження налаштувань.", show_alert=True)
            return

        def get_btn(text, val, key):
            emoji = "🟢 Так" if val else "🔴 Ні"
            return InlineKeyboardButton(text=f"{text}: {emoji}", callback_data=f"toggle_{key}")
        
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [get_btn("Замовлення", new_settings.get('notify_orders', False), "orders")],
            [get_btn("Маркет", new_settings.get('notify_market', False), "market")],
            [get_btn("Пересилання", new_settings.get('notify_transfers', False), "transfers")]
        ])
        await callback.message.edit_reply_markup(reply_markup=kb)
    await callback.answer()

@dp.message(Command("market"))
async def cmd_market(message: types.Message):
    args = message.text.split()
    page = 1
    if len(args) == 2 and args[1].isdigit():
        page = int(args[1])

    res = await fetch_api("/market", params={"tg_id": message.from_user.id, "page": page - 1})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження маркету.")
    
    # Оскільки плагін поки що повертає звичайний список, ми працюємо з ним напряму
    if not res:
        return await message.answer(f"Маркет порожній на сторінці {page}.")

    text = f"🛒 <b>Товари на маркеті (Сторінка {page}):</b>\n\n"
    for item in res:
        text += f"▪️ ID: <code>{item['id']}</code> | <b>{item['item']}</b> | Ціна: {item['price']} | Продавець: <code>{item['seller']}</code>\n"
    
    if len(res) == 40:
        text += f"\n<i>Наступна сторінка:</i> <code>/market {page + 1}</code>"

    await message.answer(text, parse_mode="HTML")

@dp.message(Command("details"))
async def cmd_details(message: types.Message):
    args = message.text.split()
    if len(args) != 2 or not args[1].isdigit():
        return await message.answer("Використання: <code>/details &lt;id&gt;</code>", parse_mode="HTML")
    
    res = await fetch_api("/details", params={"tg_id": message.from_user.id, "id": args[1]})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Предмет не знайдено.")

    text = f"🔍 <b>Деталі предмета:</b> <code>{res['material']}</code>\n\n"
    details = res.get("details", [])
    
    if not details:
        text += "<i>Немає особливих чар або ефектів.</i>"
    else:
        for d in details:
            text += f"🔹 <b>{d}</b>\n"
            
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
    
    if len(args) == 3 and args[1].lower() == "cancel" and args[2].isdigit():
        order_id = int(args[2])
        res = await fetch_api("/cancel", "POST", {"telegram_id": message.from_user.id, "order_id": order_id})
        
        # Запобігаємо падінню
        if isinstance(res, dict) and "error" in res:
            return await message.answer(f"Помилка: {res.get('error')}")

        if res.get("success"):
            return await message.answer("✅ Замовлення скасовано! Кошти надіслано в депо.")
        else:
            return await message.answer(res.get("message", "Помилка"))

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

@dp.message(Command("depot"))
async def cmd_depot(message: types.Message):
    args = message.text.split()
    page = 1
    if len(args) == 2 and args[1].isdigit(): page = int(args[1])

    res = await fetch_api("/depot", params={"tg_id": message.from_user.id, "page": page - 1})
    if not check_link(res): return await message.answer("Спочатку прив'яжіть акаунт!")
    if isinstance(res, dict) and "error" in res: return await message.answer("Помилка завантаження депо.")
    
    if not res: return await message.answer(f"Депо порожнє на сторінці {page}.")

    text = f"🗄 <b>Ваше Депо (Сторінка {page}):</b>\n\n"
    kb_buttons = []
    
    for item in res:
        if item.get("is_refund"):
            text += f"▪️ ID: <code>{item['id']}</code> | <b>{item['item']} x{item['amount']}</b> | Від: {item['fulfiller']}\n"
            kb_buttons.append([InlineKeyboardButton(text=f"💵 Забрати {item['amount']} ізумрудів (ID: {item['id']})", callback_data=f"claim_{item['id']}")])
        else:
            text += f"▪️ ID: <code>{item['id']}</code> | <b>{item['item']}</b> | Виконав: {item['fulfiller']}\n"
    
    text += "\n<i>(Предмети можна забрати лише у грі через /depot)</i>"
    kb = InlineKeyboardMarkup(inline_keyboard=kb_buttons) if kb_buttons else None
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

# БЕЗПЕЧНИЙ ОБРОБНИК КНОПОК ДЕПО
@dp.callback_query(F.data.startswith("claim_"))
async def callback_claim(callback: types.CallbackQuery):
    depot_id = int(callback.data.split("_")[1])
    res = await fetch_api("/depot/claim", "POST", {"telegram_id": callback.from_user.id, "depot_id": depot_id})
    
    if isinstance(res, dict) and "error" in res:
        await callback.answer("Помилка: " + res.get("error", "Невідома помилка"), show_alert=True)
        return

    if res.get("success"):
        await callback.answer(res.get("message"), show_alert=True)
        # Опціонально: можна видаляти повідомлення або прибирати кнопку після успішного взяття
    else:
        await callback.answer(res.get("message", "Помилка"), show_alert=True)

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


# --- Життєвий цикл веб-сервера aiohttp прив'язаний до aiogram ---
async def on_startup(dispatcher: Dispatcher):
    global runner
    app = web.Application()
    app.router.add_post('/notify', handle_notify)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8501)
    await site.start()
    print("Webhook server started on port 8501")

async def on_shutdown(dispatcher: Dispatcher):
    global runner
    if runner:
        await runner.cleanup()
    print("Webhook server gracefully stopped")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    
    # Видаляємо всі "завислі" кліки/повідомлення, що накопичились під час крашів
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Запускаємо бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("Bot stopped!")