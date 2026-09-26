import os
import asyncio
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import database as db
from ai_service import summarize_laptop_post

# Muhit o'zgaruvchilari
BOT_TOKEN = os.getenv("BOT_TOKEN")
# CHANNEL_ID matn (@kanal_nomi) yoki raqam (-1001234567890) bo'lishi mumkin
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()
SUPER_ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
BOT_USERNAME = os.getenv("BOT_USERNAME", "").replace("@", "").strip()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")


# ==========================================
# 1. ADMIN BUYRUQLARI
# ==========================================

# ➕ Yangi admin qo'shish
@dp.message(Command("addadmin"))
async def cmd_add_admin(message: types.Message, command: CommandObject):
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Bu buyruq faqat Asosiy Admin uchun!")
        return

    if not command.args or not command.args.isdigit():
        await message.answer("⚠️ Foydalanish: <code>/addadmin TELEGRAM_ID</code>\nMasalan: <code>/addadmin 123456789</code>", parse_mode="HTML")
        return

    new_admin_id = int(command.args)
    await db.add_admin_db(user_id=new_admin_id, added_by=message.from_user.id)
    await message.answer(f"✅ Foydalanuvchi <code>{new_admin_id}</code> adminlar safiga qo'shildi!", parse_mode="HTML")


# ➖ Adminni o'chirish
@dp.message(Command("deladmin"))
async def cmd_del_admin(message: types.Message, command: CommandObject):
    if message.from_user.id != SUPER_ADMIN_ID:
        await message.answer("❌ Bu buyruq faqat Asosiy Admin uchun!")
        return

    if not command.args or not command.args.isdigit():
        await message.answer("⚠️ Foydalanish: <code>/deladmin TELEGRAM_ID</code>\nMasalan: <code>/deladmin 123456789</code>", parse_mode="HTML")
        return

    target_id = int(command.args)
    success = await db.remove_admin_db(target_id)
    if success:
        await message.answer(f"✅ Admin <code>{target_id}</code> muvaffaqiyatli o'chirildi.", parse_mode="HTML")
    else:
        await message.answer("❌ Bunday ID ga ega admin topilmadi.")


# 🚀 Xohlagan vaqtda qo'lda Dayjest chiqarish buyrug'i
@dp.message(Command("digest"))
async def cmd_manual_digest(message: types.Message):
    is_admin = await db.is_user_admin(message.from_user.id, SUPER_ADMIN_ID)
    if not is_admin:
        return

    posts = await db.get_today_posts()
    if not posts:
        await message.answer("⚠️ Bugun kanalga hali hech qanday e'lon joylanmagan!")
        return

    await message.answer("⏳ Dayjest tayyorlanib, kanalga yuborilmoqda...")
    await send_daily_digest()
    await message.answer("✅ Dayjest muvaffaqiyatli kanalga joylandi!")

# 📋 Adminlar ro'yxatini ko'rish
@dp.message(Command("admins"))
async def cmd_list_admins(message: types.Message):
    is_admin = await db.is_user_admin(message.from_user.id, SUPER_ADMIN_ID)
    if not is_admin:
        return

    admins = await db.get_all_admins()
    text = f"👑 <b>Asosiy Admin:</b> <code>{SUPER_ADMIN_ID}</code>\n\n👥 <b>Qo'shilgan Adminlar:</b>\n"
    if not admins:
        text += "<i>Qo'shimcha adminlar yo'q.</i>"
    else:
        for idx, adm in enumerate(admins, 1):
            text += f"{idx}. <code>{adm['user_id']}</code> (Sana: {adm['created_at'][:10]})\n"

    await message.answer(text, parse_mode="HTML")


# 📊 Talab statistikasi (Engagement hisoboti)
@dp.message(Command("stats"))
async def show_stats(message: types.Message):
    is_admin = await db.is_user_admin(message.from_user.id, SUPER_ADMIN_ID)
    if not is_admin:
        return

    stats = await db.get_engagement_stats()
    if not stats:
        await message.answer("Hozircha statistika mavjud emas.")
        return

    text = "📊 <b>XARIDORLAR QIZIQISHI (Engagement Hisoboti):</b>\n\n"
    for idx, item in enumerate(stats, 1):
        text += f"{idx}. {item['summary_text']}\n👉 <b>Bosishlar soni:</b> {item['clicks_count']} ta\n\n"

    await message.answer(text, parse_mode="HTML")


# ==========================================
# 2. KANAL POSTLARINI REAL VAQTDA USHLASH
# ==========================================

@dp.channel_post()
async def handle_channel_post(message: types.Message):
    # Kanal ID yoki @username to'g'ri kelishini tekshirish
    target_username = CHANNEL_ID.replace("@", "").lower()
    is_correct_channel = (
        str(message.chat.id) == CHANNEL_ID or 
        (message.chat.username and message.chat.username.lower() == target_username)
    )
    if not is_correct_channel:
        return

    text = message.text or message.caption or ""
    if not text:
        return

    # Post havolasini tayyorlash
    if message.chat.username:
        post_link = f"https://t.me/{message.chat.username}/{message.message_id}"
    else:
        clean_id = str(message.chat.id).replace("-100", "")
        post_link = f"https://t.me/c/{clean_id}/{message.message_id}"

    # Gemini AI orqali qisqartirish
    summary = await summarize_laptop_post(text)

    # SQLite bazasiga saqlash
    await db.add_post(
        message_id=message.message_id,
        channel_id=message.chat.id,
        post_link=post_link,
        summary_text=summary
    )


# ==========================================
# 3. CLICK TRACKER (Deep-linking)
# ==========================================

@dp.message(CommandStart(deep_link=True))
async def handle_deep_link(message: types.Message, command: CommandStart):
    args = command.args
    if args and args.startswith("item_"):
        post_id = int(args.replace("item_", ""))
        post = await db.get_post_by_id(post_id)
        if post:
            # Bosishni qayd etish
            await db.register_click(post_id=post["id"], user_id=message.from_user.id)
            
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔎 E'lonni kanalda ko'rish", url=post["post_link"])],
                [InlineKeyboardButton(text="👨‍💻 Admin bilan bog'lanish", url=f"tg://user?id={SUPER_ADMIN_ID}")]
            ])
            await message.answer(
                f"Siz qiziqqan e'lon:\n\n{post['summary_text']}\n\nQuyidagi tugma orqali asl postga o'tishingiz mumkin:",
                reply_markup=kb
            )
            return

    await message.answer("Assalomu alaykum! Noutbuklar kanali yordamchi botiga xush kelibsiz.")


@dp.message(CommandStart())
async def handle_normal_start(message: types.Message):
    await message.answer("Assalomu alaykum! Kanalimizdagi noutbuk e'lonlarini kuzatib boring.")


# ==========================================
# 4. AVTOMATIK DAYJEST (Har kuni 20:00 da)
# ==========================================

async def send_daily_digest():
    posts = await db.get_today_posts()
    if not posts:
        return

    text = "🔥 <b>KUNNING NOUTBUK E'LONLARI (Dayjest)</b>\n\nBugun kanalimizga joylangan e'lonlar to'plami:\n\n"
    keyboard_buttons = []
    row = []

    for idx, post in enumerate(posts, 1):
        text += f"{idx}️⃣ {post['summary_text']}\n\n"
        btn_url = f"https://t.me/{BOT_USERNAME}?start=item_{post['id']}"
        row.append(InlineKeyboardButton(text=f"👉 {idx}-e'lon", url=btn_url))
        if len(row) == 2:
            keyboard_buttons.append(row)
            row = []

    if row:
        keyboard_buttons.append(row)

    keyboard_buttons.append([InlineKeyboardButton(text="👨‍💻 Adminga yozish", url=f"tg://user?id={SUPER_ADMIN_ID}")])
    kb = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

    # Kanalga jo'natish (ID raqam yoki @username bo'yicha)
    target_chat = int(CHANNEL_ID) if CHANNEL_ID.lstrip("-").isdigit() else CHANNEL_ID
    await bot.send_message(chat_id=target_chat, text=text, parse_mode="HTML", reply_markup=kb)


# ==========================================
# 5. RENDER UCHUN BEPUL VEB-SERVER
# ==========================================

async def start_dummy_server():
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="Bot 24/7 rejimida ishlamoqda!"))
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


# ==========================================
# 6. ASOSIY ISHGA TUSHIRISH
# ==========================================

async def main():
    # Bazani ishga tushirish
    await db.init_db()
    
    # Har kuni 20:00 da dayjest yuborish rejalashtiruvchisi
    scheduler.add_job(send_daily_digest, "cron", hour=20, minute=0)
    scheduler.start()

    # Render.com serveri o'chib qolmasligi uchun port ochish
    await start_dummy_server()

    print("🚀 Bot muvaffaqiyatli ishga tushdi...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
