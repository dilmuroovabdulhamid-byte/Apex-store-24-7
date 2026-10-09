"""PUBG bot."""
import asyncio
import logging
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

from db import Store

BOT_TOKEN = "8909183843:AAEKsLkNfy6debeVQYy7mr3L-MifdEmup1s"
ENC_KEY = "ApexStore2026SecureEncryptionKey_!982"

ADMIN_USERNAMES = {"apex_out"}
CHANNEL_URL = "https://t.me/apexpubgmn1"
SUPPORT_URL = "https://t.me/apex_out"
WARRANTY_TEXT = "akkauntga 3 oy kafolat"
MIN_TOPUP = 1000

logging.basicConfig(level=logging.INFO)
router = Router()
db = Store("store.db", ENC_KEY)

class AdminStates(StatesGroup):
    add_title = State()
    add_price = State()
    add_descr = State()
    add_login = State()
    add_pass = State()

class TopupStates(StatesGroup):
    amount = State()

def main_menu(is_admin=False):
    kb = [
        [InlineKeyboardButton(text="🛍 Akkauntlar", callback_data="catalog"),
         InlineKeyboardButton(text="👤 Kabinet", callback_data="cabinet")],
        [InlineKeyboardButton(text="💳 Balansni to'ldirish", callback_data="topup"),
         InlineKeyboardButton(text="💬 Qo'llab-quvvatlash", url=SUPPORT_URL)],
        [InlineKeyboardButton(text="📢 Kanal", url=CHANNEL_URL)]
    ]
    if is_admin:
        kb.append([InlineKeyboardButton(text="⚙️ Admin panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@router.message(Command("start"))
async def cmd_start(message: Message):
    db.touch_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    is_admin = message.from_user.username and message.from_user.username.lower() in ADMIN_USERNAMES
    await message.answer(
        "👋 Botimizga xush kelibsiz!\n\n"
        "Bu yerda ishonchli PUBG akkauntlarini xarid qilishingiz mumkin.",
        reply_markup=main_menu(is_admin),
        parse_mode="Markdown"
    )

@router.callback_query(F.data == "main_menu")
async def cb_main(callback: CallbackQuery):
    is_admin = callback.from_user.username and callback.from_user.username.lower() in ADMIN_USERNAMES
    await callback.message.edit_text(
        "🏠 Asosiy menyu:",
        reply_markup=main_menu(is_admin)
    )

@router.callback_query(F.data == "cabinet")
async def cb_cabinet(callback: CallbackQuery):
    user = db.get_user(callback.from_user.id)
    orders = db.user_orders(callback.from_user.id)
    
    text = (
        f"👤 **Sizning kabinetingiz:**\n\n"
        f"🆔 ID: `{callback.from_user.id}`\n"
        f"💰 Balans: **{user['balance']} so'm**\n"
        f"🛒 Sotib olingan akkauntlar: **{len(orders)} ta**\n\n"
    )
    
    if orders:
        text += "📦 **Oxirgi xaridlaringiz:**\n"
        for o in orders[:5]:
            text += f"• {o['title']} — {o['price']} so'm (Login: `{o['login']}` | Parol: `{o['password']}`)\n"
            
    kb = [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data == "catalog")
async def cb_catalog(callback: CallbackQuery):
    accs = db.list_available(limit=10, offset=0)
    if not accs:
        kb = [[InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")]]
        await callback.message.edit_text("📭 Hozircha sotuvda akkauntlar yo'q.", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))
        return

    kb = []
    for a in accs:
        kb.append([InlineKeyboardButton(text=f"{a['title']} — {a['price']} so'm", callback_data=f"acc_{a['id']}")])
    kb.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="main_menu")])
    
    await callback.message.edit_text("🛍 **Mavjud akkauntlar ro'yxati:**", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data.startswith("acc_"))
async def cb_account_detail(callback: CallbackQuery):
    acc_id = int(callback.data.split("_")[1])
    acc = db.get_account(acc_id)
    if not acc or acc["sold"]:
        await callback.answer("❌ Bu akkaunt allaqachon sotilgan yoki mavjud emas!", show_alert=True)
        return

    text = (
        f"🎮 **{acc['title']}**\n\n"
        f"📝 Tavsif: {acc['descr']}\n"
        f"🛡 Kafolat: {WARRANTY_TEXT}\n"
        f"💵 Narxi: **{acc['price']} so'm**"
    )
    kb = [
        [InlineKeyboardButton(text="💳 Sotib olish", callback_data=f"buy_{acc['id']}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="catalog")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb), parse_mode="Markdown")

@router.callback_query(F.data.startswith("buy_"))
async def cb_buy(callback: CallbackQuery):
    acc_id = int(callback.data.split("_")[1])
    uid = callback.from_user.id
    status, data = db.purchase(uid, acc_id)

    if status == "gone":
        await callback.answer("❌ Bu akkaunt allaqachon sotib bo'lingan!", show_alert=True)
    elif status == "money":
        await callback.answer("❌ Balansingiz yetarli emas! Iltimos, balansni to'ldiring.", show_alert=True)
    elif status == "ok":
        await callback.message.edit_text(
            f"✅ **Tabriklaymiz! Xarid muvaffaqiyatli amalga oshirildi.**\n\n"
            f"🎮 Akkaunt: {data['title']}\n"
            f"👤 Login: `{data['login']}`\n"
            f"🔑 Parol: `{data['password']}`\n\n"
            f"🛡 {WARRANTY_TEXT}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="main_menu")]]),
            parse_mode="Markdown"
        )

@router.callback_query(F.data == "topup")
async def cb_topup(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TopupStates.amount)
    kb = [[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="main_menu")]]
    await callback.message.edit_text(
        f"💳 Balansni to'ldirish uchun o'tkazmoqchi bo'lgan summani kiriting (Minimal: {MIN_TOPUP} so'm):\n\n"
        f"*(Admin kartasi: `8600...` ga o'tkazib, chekni yuboring)*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=kb),
        parse_mode="Markdown"
    )

@router.message(TopupStates.amount)
async def process_topup_amount(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit() or int(message.text) < MIN_TOPUP:
        await message.answer(f"❌ Noto'g'ri summa. Minimal miqdor: {MIN_TOPUP} so'm. Qaytadan kiriting:")
        return

    amount = int(message.text)
    topup_id = db.add_topup(message.from_user.id, amount)
    await state.clear()

    await message.answer(
        f"⏳ To'lov so'rovi (#{topup_id}) yaratildi ({amount} so'm).\n"
        "Iltimos, adminlar tasdiqlashini kuting."
    )

    admin_ids = db.admin_ids_by_username(ADMIN_USERNAMES)
    for aid in admin_ids:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"topup_ok_{topup_id}"),
                    InlineKeyboardButton(text="❌ Rad etish", callback_data=f"topup_no_{topup_id}")
                ]
            ])
            await bot.send_message(
                aid,
                f"🔔 **Yangi to'lov so'rovi!**\n
