"""APEX STORE 24/7 - PUBG akkauntlar do'kon boti (aiogram 3.x)."""
import asyncio
import html
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, FSInputFile, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

from db import Store

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ENC_KEY = os.getenv("ENC_KEY", "").strip()
CARD_NUMBER = os.getenv("CARD_NUMBER", "9860 1606 0260 2171").strip()
CARD_OWNER = os.getenv("CARD_OWNER", "").strip()
ADMIN_USERNAMES = {u.strip().lstrip("@").lower() for u in os.getenv("ADMIN_USERNAMES", "apex_out").split(",") if u.strip()}
ADMIN_IDS = {int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x}
CHANNEL_URL = os.getenv("CHANNEL_URL", "https://t.me/apexpubgmn1")
SUPPORT_URL = os.getenv("SUPPORT_URL", "https://t.me/apex_out")
WARRANTY = os.getenv("WARRANTY_TEXT", "akkauntga 3 oy kafolat")
MIN_TOPUP = int(os.getenv("MIN_TOPUP", "1000"))
BANNER = os.getenv("BANNER_PATH", "banner.jpg")
PAGE = 8

if not BOT_TOKEN or not ENC_KEY:
    raise SystemExit(".env faylida BOT_TOKEN va ENC_KEY bo'lishi kerak (README.txt ga qarang).")

store = Store(os.getenv("DB_PATH", "store.db"), ENC_KEY)
router = Router()


# ------------------------------------------------------------------ yordamchilar
def som(n) -> str:
    return f"{int(n):,}".replace(",", " ") + " so'm"


def esc(s) -> str:
    return html.escape(str(s or ""))


def is_admin(user) -> bool:
    return user.id in ADMIN_IDS or (user.username or "").lower() in ADMIN_USERNAMES


def admin_ids() -> set:
    return ADMIN_IDS | store.admin_ids_by_username(ADMIN_USERNAMES)


def touch(user):
    store.touch_user(user.id, user.username, user.full_name)


async def show(cb: CallbackQuery, text: str, kb=None):
    """Xabarni tahrirlaydi; rasmli xabar bo'lsa o'chirib, yangisini yuboradi."""
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except Exception:
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.message.answer(text, reply_markup=kb)


def main_menu(user):
    b = InlineKeyboardBuilder()
    b.button(text="🛍 Do'kon", callback_data="shop:0")
    b.button(text="👤 Profil", callback_data="profile")
    b.button(text="💳 Balans to'ldirish", callback_data="topup")
    b.button(text="ℹ️ Yo'riqnoma", callback_data="guide")
    b.button(text="📣 Kanal", url=CHANNEL_URL)
    b.button(text="❓ Yordam", url=SUPPORT_URL)
    if is_admin(user):
        b.button(text="🛠 Admin Panel", callback_data="admin")
    b.adjust(1, 2, 2, 1, 1)
    return b.as_markup()


def welcome(user) -> str:
    return (
        f"👋 Salom, <b>{esc(user.full_name)}</b>!\n\n"
        "Bu <b>APEX STORE 24/7</b> - PUBG akkauntlar do'koni.\n"
        "Do'kondan akkaunt tanlang, balansni to'ldiring va akkauntni darhol oling.\n\n"
        f"🛡 Kafolat: {esc(WARRANTY)}"
    )


def back_kb(data="menu", text="◀️ Orqaga"):
    b = InlineKeyboardBuilder()
    b.button(text=text, callback_data=data)
    return b.as_markup()


# ------------------------------------------------------------------ holatlar
class AddAcc(StatesGroup):
    title = State()
    price = State()
    descr = State()
    login = State()
    password = State()


class EditPrice(StatesGroup):
    price = State()


class TopUp(StatesGroup):
    amount = State()
    check = State()


# ------------------------------------------------------------------ umumiy
@router.message(CommandStart())
async def cmd_start(m: Message, state: FSMContext):
    await state.clear()
    touch(m.from_user)
    kb = main_menu(m.from_user)
    if Path(BANNER).exists():
        await m.answer_photo(FSInputFile(BANNER), caption=welcome(m.from_user), reply_markup=kb)
    else:
        await m.answer(welcome(m.from_user), reply_markup=kb)


@router.message(Command("id"))
async def cmd_id(m: Message):
    await m.answer(f"Sizning Telegram ID: <code>{m.from_user.id}</code>")


@router.callback_query(F.data == "menu")
async def cb_menu(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    touch(cb.from_user)
    await show(cb, welcome(cb.from_user), main_menu(cb.from_user))
    await cb.answer()


@router.callback_query(F.data == "guide")
async def cb_guide(cb: CallbackQuery):
    text = (
        "ℹ️ <b>Yo'riqnoma</b>\n\n"
        "1️⃣ <b>Balans to'ldirish</b> - summani kiriting, kartaga o'tkazing va chekni yuboring.\n"
        "2️⃣ Admin chekni tekshirib tasdiqlagach, balansingiz to'ladi.\n"
        "3️⃣ <b>Do'kon</b>dan akkauntni tanlang va <b>Sotib olish</b>ni bosing.\n"
        "4️⃣ Login va parol darhol shu yerga yuboriladi.\n\n"
        f"🛡 Kafolat: {esc(WARRANTY)}\n"
        "Akkauntga kirgach parolni o'zgartiring. Muammo bo'lsa, Yordam tugmasini bosing."
    )
    await show(cb, text, back_kb())
    await cb.answer()


@router.callback_query(F.data == "profile")
async def cb_profile(cb: CallbackQuery):
    touch(cb.from_user)
    u = store.get_user(cb.from_user.id)
    orders = store.user_orders(cb.from_user.id)
    b = InlineKeyboardBuilder()
    if orders:
        b.button(text="📦 Xaridlarim", callback_data="orders")
    b.button(text="◀️ Orqaga", callback_data="menu")
    b.adjust(1)
    text = (
        "👤 <b>Profil</b>\n\n"
        f"🆔 ID: <code>{u['id']}</code>\n"
        f"💰 Balans: <b>{som(u['balance'])}</b>\n"
        f"🛒 Xaridlar: {len(orders)} ta"
    )
    await show(cb, text, b.as_markup())
    await cb.answer()


@router.callback_query(F.data == "orders")
async def cb_orders(cb: CallbackQuery):
    orders = store.user_orders(cb.from_user.id)
    lines = [
        f"📦 <b>{esc(o['title'])}</b> - {som(o['price'])}\n"
        f"🔑 <code>{esc(o['login'])}</code> / <code>{esc(o['password'])}</code>\n🕒 {o['sold_at']}"
        for o in orders[:10]
    ]
    await show(cb, "📦 <b>Xaridlarim</b>\n\n" + "\n\n".join(lines or ["Hozircha xarid yo'q."]), back_kb("profile"))
    await cb.answer()


# ------------------------------------------------------------------ do'kon
@router.callback_query(F.data.startswith("shop:"))
async def cb_shop(cb: CallbackQuery):
    page = int(cb.data.split(":")[1])
    rows = store.list_available(PAGE + 1, page * PAGE)
    has_next, rows = len(rows) > PAGE, rows[:PAGE]
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"{r['title']} - {som(r['price'])}", callback_data=f"acc:{r['id']}:{page}")
    b.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"shop:{page - 1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"shop:{page + 1}"))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="menu"))
    text = "🛍 <b>Do'kon</b>\n\nAkkauntni tanlang:" if rows else "🛍 <b>Do'kon</b>\n\nHozircha sotuvda akkaunt yo'q. Keyinroq qaytib keling."
    await show(cb, text, b.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("acc:"))
async def cb_acc(cb: CallbackQuery):
    _, acc_id, page = cb.data.split(":")
    a = store.get_account(int(acc_id))
    if not a or a["sold"]:
        await cb.answer("Bu akkaunt sotilgan", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    b.button(text="✅ Sotib olish", callback_data=f"buy:{a['id']}:{page}")
    b.button(text="◀️ Orqaga", callback_data=f"shop:{page}")
    b.adjust(1)
    text = (
        f"📦 <b>{esc(a['title'])}</b>\n\n"
        f"{esc(a['descr'])}\n\n" if a["descr"] else f"📦 <b>{esc(a['title'])}</b>\n\n"
    ) + f"💰 Narx: <b>{som(a['price'])}</b>\n🛡 Kafolat: {esc(WARRANTY)}"
    await show(cb, text, b.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("buy:"))
async def cb_buy(cb: CallbackQuery):
    _, acc_id, page = cb.data.split(":")
    a = store.get_account(int(acc_id))
    if not a or a["sold"]:
        await cb.answer("Bu akkaunt sotilgan", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, sotib olaman", callback_data=f"buyok:{a['id']}")
    b.button(text="❌ Yo'q", callback_data=f"acc:{a['id']}:{page}")
    b.adjust(1)
    await show(cb, f"<b>{esc(a['title'])}</b> akkauntini <b>{som(a['price'])}</b> evaziga sotib olasizmi?", b.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("buyok:"))
async def cb_buyok(cb: CallbackQuery, bot: Bot):
    touch(cb.from_user)
    acc_id = int(cb.data.split(":")[1])
    status, a = store.purchase(cb.from_user.id, acc_id)
    if status == "gone":
        await cb.answer("Afsuski, bu akkaunt allaqachon sotilgan", show_alert=True)
        await show(cb, "Bu akkaunt sotilgan.", back_kb("shop:0", "🛍 Do'konga"))
        return
    if status == "money":
        u = store.get_user(cb.from_user.id)
        b = InlineKeyboardBuilder()
        b.button(text="💳 Balans to'ldirish", callback_data="topup")
        b.button(text="◀️ Orqaga", callback_data="shop:0")
        b.adjust(1)
        await show(
            cb,
            f"❌ Balans yetarli emas.\n\nNarx: {som(a['price'])}\nBalansingiz: {som(u['balance'])}",
            b.as_markup(),
        )
        await cb.answer()
        return
    text = (
        "✅ <b>Xarid muvaffaqiyatli!</b>\n\n"
        f"📦 {esc(a['title'])}\n💰 {som(a['price'])}\n\n"
        f"🔑 Login: <code>{esc(a['login'])}</code>\n"
        f"🔐 Parol: <code>{esc(a['password'])}</code>\n\n"
        f"🛡 Kafolat: {esc(WARRANTY)}\n"
        "Akkauntga kirgach parolni darhol o'zgartiring va ma'lumotlarni hech kimga bermang."
    )
    await show(cb, text, back_kb("menu", "🏠 Bosh menyu"))
    await cb.answer("Xarid amalga oshdi ✅")
    for aid in admin_ids():
        try:
            await bot.send_message(
                aid,
                f"🛒 Sotildi: <b>{esc(a['title'])}</b> - {som(a['price'])}\n"
                f"👤 {esc(cb.from_user.full_name)} (@{esc(cb.from_user.username)}) | ID <code>{cb.from_user.id}</code>",
            )
        except Exception:
            pass


# ------------------------------------------------------------------ balans to'ldirish
@router.callback_query(F.data == "topup")
async def cb_topup(cb: CallbackQuery, state: FSMContext):
    touch(cb.from_user)
    await state.set_state(TopUp.amount)
    await show(cb, f"💳 Qancha to'ldirmoqchisiz?\n\nSummani so'mda yozing (kamida {som(MIN_TOPUP)}).\nMasalan: <code>50000</code>", back_kb())
    await cb.answer()


@router.message(TopUp.amount, F.text)
async def topup_amount(m: Message, state: FSMContext):
    digits = "".join(ch for ch in m.text if ch.isdigit())
    if not digits or int(digits) < MIN_TOPUP:
        await m.answer(f"Summani raqam bilan yozing (kamida {som(MIN_TOPUP)}).")
        return
    amount = int(digits)
    await state.update_data(amount=amount)
    await state.set_state(TopUp.check)
    owner = f"\n👤 Karta egasi: {esc(CARD_OWNER)}" if CARD_OWNER else ""
    await m.answer(
        f"💳 <b>To'lov</b>\n\nQuyidagi kartaga <b>{som(amount)}</b> o'tkazing:\n\n"
        f"<code>{esc(CARD_NUMBER)}</code>{owner}\n\n"
        "To'lovdan keyin <b>chek skrinshotini</b> shu yerga rasm qilib yuboring. "
        "Admin tekshirib, balansingizni to'ldiradi.",
        reply_markup=back_kb("menu", "❌ Bekor qilish"),
    )


@router.message(TopUp.check, F.photo)
async def topup_check(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    amount = data.get("amount")
    admins = admin_ids()
    if not amount:
        await state.clear()
        await m.answer("Qaytadan urinib ko'ring.", reply_markup=main_menu(m.from_user))
        return
    if not admins:
        await m.answer("Hozir to'lovni qabul qilib bo'lmayapti. Iltimos, Yordam orqali adminga yozing.")
        logging.warning("Admin topilmadi: ADMIN_IDS yoki @apex_out botga /start bosishi kerak.")
        return
    tid = store.add_topup(m.from_user.id, amount)
    b = InlineKeyboardBuilder()
    b.button(text="✅ Tasdiqlash", callback_data=f"tp_ok:{tid}")
    b.button(text="❌ Rad etish", callback_data=f"tp_no:{tid}")
    caption = (
        f"💳 <b>Yangi to'lov so'rovi #{tid}</b>\n"
        f"👤 {esc(m.from_user.full_name)} (@{esc(m.from_user.username)})\n"
        f"🆔 <code>{m.from_user.id}</code>\n"
        f"💰 Ko'rsatilgan summa: <b>{som(amount)}</b>\n\n"
        "Chekdagi summa, vaqt va karta to'g'riligini tekshirib tasdiqlang."
    )
    for aid in admins:
        try:
            await bot.send_photo(aid, m.photo[-1].file_id, caption=caption, reply_markup=b.as_markup())
        except Exception:
            logging.exception("Adminga yuborib bo'lmadi: %s", aid)
    await state.clear()
    await m.answer("✅ Chek adminga yuborildi. Tekshirilgach balansingiz to'ldiriladi.", reply_markup=main_menu(m.from_user))


@router.message(TopUp.check)
async def topup_check_wrong(m: Message):
    await m.answer("Iltimos, to'lov chekini <b>rasm</b> (skrinshot) qilib yuboring.")


async def _resolve(cb: CallbackQuery, bot: Bot, approve: bool):
    if not is_admin(cb.from_user):
        await cb.answer("Ruxsat yo'q", show_alert=True)
        return
    t = store.resolve_topup(int(cb.data.split(":")[1]), approve)
    if not t:
        await cb.answer("Bu so'rov allaqachon ko'rib chiqilgan", show_alert=True)
        return
    mark = "✅ Tasdiqlandi" if approve else "❌ Rad etildi"
    try:
        await cb.message.edit_caption(caption=(cb.message.html_text or "") + f"\n\n{mark} ({esc(cb.from_user.full_name)})", reply_markup=None)
    except Exception:
        pass
    try:
        if approve:
            await bot.send_message(t["user_id"], f"✅ Balansingiz <b>{som(t['amount'])}</b>ga to'ldirildi.")
        else:
            await bot.send_message(t["user_id"], "❌ To'lovingiz tasdiqlanmadi. Muammo bo'lsa, Yordam orqali adminga yozing.")
    except Exception:
        pass
    await cb.answer(mark)


@router.callback_query(F.data.startswith("tp_ok:"))
async def tp_ok(cb: CallbackQuery, bot: Bot):
    await _resolve(cb, bot, True)


@router.callback_query(F.data.startswith("tp_no:"))
async def tp_no(cb: CallbackQuery, bot: Bot):
    await _resolve(cb, bot, False)


# ------------------------------------------------------------------ admin panel
async def admin_only(cb: CallbackQuery) -> bool:
    if not is_admin(cb.from_user):
        await cb.answer("Ruxsat yo'q", show_alert=True)
        return False
    return True


@router.callback_query(F.data == "admin")
async def cb_admin(cb: CallbackQuery, state: FSMContext):
    if not await admin_only(cb):
        return
    await state.clear()
    touch(cb.from_user)
    b = InlineKeyboardBuilder()
    b.button(text="➕ Akkaunt qo'shish", callback_data="adm_add")
    b.button(text="📋 Akkauntlar", callback_data="adm_list:0")
    b.button(text="📊 Statistika", callback_data="adm_stats")
    b.button(text="◀️ Orqaga", callback_data="menu")
    b.adjust(1)
    await show(cb, "🛠 <b>Admin Panel</b>\n\nBalansga qo'lda pul qo'shish: <code>/addbalance ID SUMMA</code>", b.as_markup())
    await cb.answer()


@router.callback_query(F.data == "adm_stats")
async def adm_stats(cb: CallbackQuery):
    if not await admin_only(cb):
        return
    s = store.stats()
    text = (
        "📊 <b>Statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {s['users']}\n"
        f"📦 Sotuvda: {s['available']} ta\n"
        f"✅ Sotilgan: {s['sold']} ta\n"
        f"💰 Tushum: {som(s['revenue'])}\n"
        f"⏳ Kutilayotgan to'lovlar: {s['pending']}"
    )
    await show(cb, text, back_kb("admin"))
    await cb.answer()


@router.message(Command("addbalance"))
async def cmd_addbalance(m: Message, bot: Bot):
    if not is_admin(m.from_user):
        return
    parts = (m.text or "").split()
    if len(parts) != 3 or not parts[1].lstrip("-").isdigit() or not parts[2].lstrip("-").isdigit():
        await m.answer("Format: <code>/addbalance ID SUMMA</code>")
        return
    uid, amount = int(parts[1]), int(parts[2])
    if store.add_balance(uid, amount):
        await m.answer(f"✅ {uid} balansiga {som(amount)} qo'shildi.")
        try:
            await bot.send_message(uid, f"💰 Balansingiz {som(amount)}ga o'zgartirildi.")
        except Exception:
            pass
    else:
        await m.answer("Bunday foydalanuvchi topilmadi (u botga /start bosgan bo'lishi kerak).")


# --- akkaunt qo'shish
@router.callback_query(F.data == "adm_add")
async def adm_add(cb: CallbackQuery, state: FSMContext):
    if not await admin_only(cb):
        return
    await state.clear()
    await state.set_state(AddAcc.title)
    await state.update_data(trash=[])
    await show(cb, "➕ <b>Yangi akkaunt</b>\n\n1/5. Akkaunt <b>nomini</b> yozing.\nMasalan: <code>PUBG Level 70 | 25 ta skin</code>", back_kb("admin", "❌ Bekor qilish"))
    await cb.answer()


@router.message(AddAcc.title, F.text)
async def add_title(m: Message, state: FSMContext):
    if not is_admin(m.from_user):
        return
    await state.update_data(title=m.text.strip()[:80])
    await state.set_state(AddAcc.price)
    await m.answer("2/5. <b>Narxini</b> so'mda yozing. Masalan: <code>150000</code>")


@router.message(AddAcc.price, F.text)
async def add_price(m: Message, state: FSMContext):
    if not is_admin(m.from_user):
        return
    digits = "".join(ch for ch in m.text if ch.isdigit())
    if not digits or int(digits) <= 0:
        await m.answer("Narxni raqam bilan yozing.")
        return
    await state.update_data(price=int(digits))
    await state.set_state(AddAcc.descr)
    await m.answer("3/5. <b>Tavsif</b> (level, rank, skinlar...) yozing. Kerak bo'lmasa <code>-</code> yuboring.")


@router.message(AddAcc.descr, F.text)
async def add_descr(m: Message, state: FSMContext):
    if not is_admin(m.from_user):
        return
    await state.update_data(descr="" if m.text.strip() == "-" else m.text.strip()[:500])
    await state.set_state(AddAcc.login)
    await m.answer("4/5. Akkaunt <b>loginini</b> yozing.")


@router.message(AddAcc.login, F.text)
async def add_login(m: Message, state: FSMContext):
    if not is_admin(m.from_user):
        return
    data = await state.get_data()
    await state.update_data(login=m.text.strip(), trash=data.get("trash", []) + [m.message_id])
    await state.set_state(AddAcc.password)
    await m.answer("5/5. Akkaunt <b>parolini</b> yozing.")


@router.message(AddAcc.password, F.text)
async def add_password(m: Message, state: FSMContext, bot: Bot):
    if not is_admin(m.from_user):
        return
    d = await state.get_data()
    acc_id = store.add_account(d["title"], d["price"], d.get("descr", ""), d["login"], m.text.strip())
    await state.clear()
    for mid in d.get("trash", []) + [m.message_id]:  # login/parol xabarlarini chatdan o'chiramiz
        try:
            await bot.delete_message(m.chat.id, mid)
        except Exception:
            pass
    b = InlineKeyboardBuilder()
    b.button(text="➕ Yana qo'shish", callback_data="adm_add")
    b.button(text="🛠 Admin Panel", callback_data="admin")
    b.adjust(1)
    await m.answer(f"✅ Akkaunt #{acc_id} qo'shildi: <b>{esc(d['title'])}</b> - {som(d['price'])}\n(Login/parol shifrlab saqlandi, xabarlar chatdan o'chirildi.)", reply_markup=b.as_markup())


# --- akkauntlar ro'yxati / narx / o'chirish
@router.callback_query(F.data.startswith("adm_list:"))
async def adm_list(cb: CallbackQuery):
    if not await admin_only(cb):
        return
    page = int(cb.data.split(":")[1])
    rows = store.list_available(PAGE + 1, page * PAGE)
    has_next, rows = len(rows) > PAGE, rows[:PAGE]
    b = InlineKeyboardBuilder()
    for r in rows:
        b.button(text=f"#{r['id']} {r['title']} - {som(r['price'])}", callback_data=f"adm_acc:{r['id']}:{page}")
    b.adjust(1)
    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"adm_list:{page - 1}"))
    if has_next:
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"adm_list:{page + 1}"))
    if nav:
        b.row(*nav)
    b.row(InlineKeyboardButton(text="◀️ Orqaga", callback_data="admin"))
    await show(cb, "📋 <b>Sotuvdagi akkauntlar</b>" if rows else "📋 Sotuvda akkaunt yo'q.", b.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("adm_acc:"))
async def adm_acc(cb: CallbackQuery):
    if not await admin_only(cb):
        return
    _, acc_id, page = cb.data.split(":")
    a = store.get_account(int(acc_id))
    if not a or a["sold"]:
        await cb.answer("Topilmadi yoki sotilgan", show_alert=True)
        return
    b = InlineKeyboardBuilder()
    b.button(text="✏️ Narxni o'zgartirish", callback_data=f"adm_price:{a['id']}")
    b.button(text="🗑 O'chirish", callback_data=f"adm_del:{a['id']}:{page}")
    b.button(text="◀️ Orqaga", callback_data=f"adm_list:{page}")
    b.adjust(1)
    await show(cb, f"📦 <b>#{a['id']} {esc(a['title'])}</b>\n{esc(a['descr'])}\n\n💰 {som(a['price'])}", b.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("adm_price:"))
async def adm_price(cb: CallbackQuery, state: FSMContext):
    if not await admin_only(cb):
        return
    await state.set_state(EditPrice.price)
    await state.update_data(acc_id=int(cb.data.split(":")[1]))
    await show(cb, "Yangi narxni so'mda yozing:", back_kb("admin", "❌ Bekor qilish"))
    await cb.answer()


@router.message(EditPrice.price, F.text)
async def edit_price(m: Message, state: FSMContext):
    if not is_admin(m.from_user):
        return
    digits = "".join(ch for ch in m.text if ch.isdigit())
    if not digits or int(digits) <= 0:
        await m.answer("Narxni raqam bilan yozing.")
        return
    d = await state.get_data()
    await state.clear()
    ok = store.set_price(d["acc_id"], int(digits))
    await m.answer(f"✅ Narx {som(digits)} qilindi." if ok else "Akkaunt topilmadi yoki sotilgan.", reply_markup=back_kb("adm_list:0", "📋 Akkauntlar"))


@router.callback_query(F.data.startswith("adm_del:"))
async def adm_del(cb: CallbackQuery):
    if not await admin_only(cb):
        return
    _, acc_id, page = cb.data.split(":")
    b = InlineKeyboardBuilder()
    b.button(text="✅ Ha, o'chirish", callback_data=f"adm_delok:{acc_id}:{page}")
    b.button(text="❌ Yo'q", callback_data=f"adm_acc:{acc_id}:{page}")
    b.adjust(1)
    await show(cb, f"#{acc_id} akkauntni o'chirasizmi?", b.as_markup())
    await cb.answer()


@router.callback_query(F.data.startswith("adm_delok:"))
async def adm_delok(cb: CallbackQuery):
    if not await admin_only(cb):
        return
    _, acc_id, page = cb.data.split(":")
    ok = store.delete_account(int(acc_id))
    await cb.answer("O'chirildi" if ok else "O'chirib bo'lmadi", show_alert=not ok)
    await show(cb, "🗑 O'chirildi." if ok else "O'chirib bo'lmadi.", back_kb(f"adm_list:{page}", "📋 Akkauntlar"))


# ------------------------------------------------------------------ ishga tushirish
async def main():
    logging.basicConfig(level=logging.INFO)
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    if not ADMIN_IDS:
        logging.warning("ADMIN_IDS bo'sh: faqat @%s username orqali admin aniqlanadi. Xavfsizroq bo'lishi uchun /id orqali ID olib, .env ga yozing.", ", @".join(ADMIN_USERNAMES))
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
