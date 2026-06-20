import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import aiosqlite

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "7648181342:AAFoe2w9wx5et-XbgT8HA9cUXFt9JMrZnZo"
BOT_USERNAME = "arcadeludo_bot"

CHAT_USERNAME = "@chatludomanii"
CHANNEL_USERNAME = "@Arcadeludo"
CHAT_TAG = "chatludomanii"
CHANNEL_TAG = "Arcadeludo"

OWNER_IDS = [8131755675, 8595680472]
MIN_WITHDRAW = 15
DB_NAME = "database.db"

# ==================== БАЗА ДАННЫХ ====================
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            balance INTEGER DEFAULT 0, ref_code TEXT UNIQUE,
            invited_by INTEGER, total_invited INTEGER DEFAULT 0)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS referrals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER, invited_user_id INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        await db.execute('''CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER, amount INTEGER,
            status TEXT DEFAULT 'pending',
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        await db.commit()

# ==================== КЛАВИАТУРЫ ====================
def main_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🔗 Реф")],
        [KeyboardButton(text="💎 Вывод звёзд")],
        [KeyboardButton(text="🏆 Топ")]
    ], resize_keyboard=True)

def admin_menu():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👥 Посмотреть рефов")],
        [KeyboardButton(text="📤 Заявки на вывод")],
        [KeyboardButton(text="📊 Статистика")]
    ], resize_keyboard=True)

def sub_check():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")]
    ])

# ==================== ФУНКЦИИ ====================
async def check_subs(bot, uid):
    ch, ct = False, False
    try:
        m = await bot.get_chat_member(f"@{CHANNEL_TAG}", uid)
        ch = m.status not in ['left', 'kicked']
    except: pass
    try:
        m = await bot.get_chat_member(f"@{CHAT_TAG}", uid)
        ct = m.status not in ['left', 'kicked']
    except: pass
    return ch, ct

async def get_ref_code(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT ref_code FROM users WHERE user_id=?", (uid,))
        r = await c.fetchone()
        if r and r[0]: return r[0]
        code = f"ref_{uid}_{datetime.now().strftime('%H%M%S')}"
        await db.execute("UPDATE users SET ref_code=? WHERE user_id=?", (code, uid))
        await db.commit()
        return code

async def add_user(uid, uname, fname):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users (user_id,username,first_name) VALUES (?,?,?)", (uid, uname, fname))
        await db.commit()

async def get_balance(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
        r = await c.fetchone()
        return r[0] if r else 0

async def get_ref_count(uid):
    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?", (uid,))
        r = await c.fetchone()
        return r[0] if r else 0

async def add_ref(ref_id, inv_id):
    if ref_id == inv_id: return
    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT id FROM referrals WHERE invited_user_id=?", (inv_id,))
        if await c.fetchone(): return
        await db.execute("INSERT INTO referrals (referrer_id,invited_user_id) VALUES (?,?)", (ref_id, inv_id))
        await db.execute("UPDATE users SET total_invited=total_invited+1 WHERE user_id=?", (ref_id,))
        await db.commit()

async def get_top(limit=5):
    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT u.user_id,u.username,u.first_name,COUNT(r.id) FROM users u LEFT JOIN referrals r ON u.user_id=r.referrer_id GROUP BY u.user_id ORDER BY COUNT(r.id) DESC LIMIT ?", (limit,))
        return await c.fetchall()

# ==================== ХЕНДЛЕРЫ ====================
async def start(message: types.Message, bot: Bot):
    uid = message.from_user.id
    uname = message.from_user.username
    fname = message.from_user.first_name
    await add_user(uid, uname, fname)

    args = message.text.split()
    if len(args) > 1:
        async with aiosqlite.connect(DB_NAME) as db:
            c = await db.execute("SELECT user_id FROM users WHERE ref_code=?", (args[1],))
            r = await c.fetchone()
            if r: await add_ref(r[0], uid)

    ch, ct = await check_subs(bot, uid)
    if ch and ct:
        await message.answer("✅ Добро пожаловать!\nВыберите действие:", reply_markup=main_menu())
    else:
        ns = []
        if not ch: ns.append(f"📢 {CHANNEL_USERNAME}")
        if not ct: ns.append(f"💬 {CHAT_USERNAME}")
        await message.answer(f"⚠️ Подпишитесь на:\n\n" + "\n".join(ns) + "\n\nЗатем нажмите проверку:", reply_markup=sub_check())

async def check_cb(callback: types.CallbackQuery, bot: Bot):
    uid = callback.from_user.id
    ch, ct = await check_subs(bot, uid)
    if ch and ct:
        await callback.message.delete()
        await callback.message.answer("✅ Доступ открыт!", reply_markup=main_menu())
        await callback.answer("✅ Подписки подтверждены!")
    else:
        await callback.answer("❌ Подпишитесь на всё!", show_alert=True)

async def ref_cmd(message: types.Message, bot: Bot):
    uid = message.from_user.id
    ch, ct = await check_subs(bot, uid)
    if not (ch and ct):
        await message.answer("⚠️ Сначала подпишитесь!")
        return
    code = await get_ref_code(uid)
    link = f"https://t.me/{BOT_USERNAME}?start={code}"
    cnt = await get_ref_count(uid)
    await message.answer(f"🔗 <b>Ваша ссылка:</b>\n\n<code>{link}</code>\n\n👥 Приглашено: <b>{cnt}</b>\n💡 15% от трат — ваши!", parse_mode=ParseMode.HTML)

async def withdraw_menu(message: types.Message, bot: Bot):
    uid = message.from_user.id
    ch, ct = await check_subs(bot, uid)
    if not (ch and ct):
        await message.answer("⚠️ Сначала подпишитесь!")
        return
    bal = await get_balance(uid)
    await message.answer(f"💰 <b>Вывод звёзд</b>\n\nБаланс: <b>{bal}</b> ⭐\nМинимум: <b>{MIN_WITHDRAW}</b> ⭐\n\nВведите сумму:", parse_mode=ParseMode.HTML)

async def withdraw_amount(message: types.Message, bot: Bot):
    uid = message.from_user.id
    if message.text in ["🔗 Реф", "💎 Вывод звёзд", "🏆 Топ", "👥 Посмотреть рефов", "📤 Заявки на вывод", "📊 Статистика"]:
        return
    try:
        amount = int(message.text)
    except:
        await message.answer("❌ Введите число!")
        return
    if amount < MIN_WITHDRAW:
        await message.answer(f"❌ Минимум: {MIN_WITHDRAW} ⭐")
        return
    bal = await get_balance(uid)
    if amount > bal:
        await message.answer(f"❌ Недостаточно! Баланс: {bal} ⭐")
        return

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO withdrawals (user_id,amount) VALUES (?,?)", (uid, amount))
        await db.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, uid))
        await db.commit()

    ment = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    for oid in OWNER_IDS:
        try: await bot.send_message(oid, f"📤 <b>Заявка на вывод!</b>\n\n👤 {ment} (ID: {uid})\n💎 Сумма: <b>{amount}</b> ⭐", parse_mode=ParseMode.HTML)
        except: pass

    await message.answer("✅ <b>Заявка создана!</b>\n⏳ Ожидайте в течение 24 часов.", reply_markup=main_menu(), parse_mode=ParseMode.HTML)

async def top_cmd(message: types.Message, bot: Bot):
    uid = message.from_user.id
    ch, ct = await check_subs(bot, uid)
    if not (ch and ct):
        await message.answer("⚠️ Сначала подпишитесь!")
        return
    top = await get_top(5)
    if not top:
        await message.answer("🏆 Топ пока пуст.")
        return
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣"]
    text = "🏆 <b>Топ рефереров:</b>\n\n"
    for i,(uid,uname,fname,cnt) in enumerate(top):
        name = f"@{uname}" if uname else (fname or "Юзер")
        text += f"{medals[i]} {name}: <b>{cnt}</b> чел.\n"
    text += "\n<i>Обновляется каждые 24 часа</i>"
    await message.answer(text, parse_mode=ParseMode.HTML)

async def admin_cmd(message: types.Message):
    if message.from_user.id not in OWNER_IDS:
        await message.answer("⛔ Недоступно.")
        return
    await message.answer("🔧 Админ-панель:", reply_markup=admin_menu())

async def admin_refs(message: types.Message):
    if message.from_user.id not in OWNER_IDS: return
    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT u.user_id,u.username,u.first_name,u.ref_code,(SELECT COUNT(*) FROM referrals WHERE referrer_id=u.user_id) FROM users u WHERE u.ref_code IS NOT NULL ORDER BY 5 DESC LIMIT 20")
        users = await c.fetchall()
    if not users:
        await message.answer("Нет рефералов.")
        return
    text = "📊 <b>Рефералы:</b>\n\n"
    for uid,uname,fname,code,cnt in users:
        name = f"@{uname}" if uname else (fname or f"ID:{uid}")
        link = f"https://t.me/{BOT_USERNAME}?start={code}"
        text += f"👤 {name}\n🔗 {link}\n👥 Привёл: {cnt}\n\n"
    await message.answer(text, parse_mode=ParseMode.HTML)

async def admin_wd(message: types.Message):
    if message.from_user.id not in OWNER_IDS: return
    async with aiosqlite.connect(DB_NAME) as db:
        c = await db.execute("SELECT w.id,w.user_id,w.amount,w.timestamp,u.username,u.first_name FROM withdrawals w JOIN users u ON w.user_id=u.user_id WHERE w.status='pending' ORDER BY w.timestamp DESC")
        wds = await c.fetchall()
    if not wds:
        await message.answer("Нет заявок.")
        return
    text = "📤 <b>Заявки на вывод:</b>\n\n"
    for wid,uid,amount,ts,uname,fname in wds:
        name = f"@{uname}" if uname else (fname or f"ID:{uid}")
        text += f"#{wid} | {name}\n💎 {amount} ⭐ | {ts}\n\n"
    await message.answer(text, parse_mode=ParseMode.HTML)

async def admin_stats(message: types.Message):
    if message.from_user.id not in OWNER_IDS: return
    async with aiosqlite.connect(DB_NAME) as db:
        u = await db.execute("SELECT COUNT(*) FROM users")
        tu = (await u.fetchone())[0]
        r = await db.execute("SELECT COUNT(*) FROM referrals")
        tr = (await r.fetchone())[0]
        p = await db.execute("SELECT COUNT(*) FROM withdrawals WHERE status='pending'")
        tp = (await p.fetchone())[0]
        c = await db.execute("SELECT COALESCE(SUM(amount),0) FROM withdrawals WHERE status='completed'")
        tw = (await c.fetchone())[0]
    await message.answer(f"📊 <b>Статистика:</b>\n\n👥 Пользователей: <b>{tu}</b>\n🔗 Рефералов: <b>{tr}</b>\n📤 Ожидают: <b>{tp}</b>\n💎 Выведено: <b>{tw}</b> ⭐", parse_mode=ParseMode.HTML)

# ==================== ЗАПУСК ====================
async def main():
    logging.basicConfig(level=logging.INFO)
    await init_db()
    print("✅ База готова")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()

    dp.message.register(start, Command("start"))
    dp.message.register(admin_cmd, Command("admin"))
    dp.callback_query.register(check_cb, F.data == "check_sub")
    dp.message.register(ref_cmd, F.text == "🔗 Реф")
    dp.message.register(withdraw_menu, F.text == "💎 Вывод звёзд")
    dp.message.register(top_cmd, F.text == "🏆 Топ")
    dp.message.register(admin_refs, F.text == "👥 Посмотреть рефов")
    dp.message.register(admin_wd, F.text == "📤 Заявки на вывод")
    dp.message.register(admin_stats, F.text == "📊 Статистика")
    dp.message.register(withdraw_amount, F.text.regexp(r"^\d+$"))

    print("🤖 Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
