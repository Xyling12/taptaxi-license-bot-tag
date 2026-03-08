"""
TapTaxi License Bot — main entry point.

Flow:
  1. Driver sends any message containing their device_id
  2. Bot notifies admin(s) with Approve/Reject buttons
  3. Admin clicks Approve → bot generates license and sends it to the driver
  4. Admin can also use /approve, /revoke, /list commands
"""

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

from config import Config
from database import Database
from keygen import generate_license

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger("license_bot")

router = Router()

# Globals injected in main()
_config: Config = None  # type: ignore
_db: Database = None  # type: ignore
_bot: Bot = None  # type: ignore


# ── Helpers ────────────────────────────────────────────────────────────────

def is_admin(user_id: int) -> bool:
    return user_id in _config.admin_ids


def _approve_keyboard(device_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Выдать лицензию", callback_data=f"approve:{device_id}"),
        InlineKeyboardButton(text="❌ Отклонить",       callback_data=f"reject:{device_id}"),
    ]])


def _status_icon(status: str) -> str:
    return {"pending": "⏳", "approved": "✅", "revoked": "🚫"}.get(status, "❓")


def _user_label(msg: Message) -> str:
    username = msg.from_user.username
    if username:
        return f"@{username}"
    return f"id:{msg.from_user.id}"


def _license_text(device_id: str, code: str) -> str:
    return (
        "🎉 <b>Лицензия активирована!</b>\n\n"
        "Твой персональный код:\n"
        f"<code>{code}</code>\n\n"
        f"📱 Device ID: <code>{device_id}</code>\n\n"
        "Введи этот код при запуске приложения.\n"
        "При переустановке на том же телефоне — код не меняется ✅"
    )


async def _send_license_to_user(telegram_id: int, device_id: str, code: str) -> None:
    await _bot.send_message(
        telegram_id,
        _license_text(device_id, code),
        parse_mode=ParseMode.HTML,
    )


# ── Driver flow ────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message):
    if _config.auto_approve:
        await msg.answer(
            "👋 Привет!\n\n"
            "Отправь свой <b>Device ID</b> одним сообщением — "
            "и бот сразу выдаст лицензионный код.\n\n"
            "📱 Device ID отображается при первом запуске TapTaxi.",
            parse_mode=ParseMode.HTML,
        )
        return

    await msg.answer(
        "👋 Привет!\n\n"
        "Отправь свой <b>Device ID</b> (идентификатор телефона) одним сообщением — "
        "и мы выдадим тебе лицензионный код для приложения.\n\n"
        "📱 Где взять Device ID?\n"
        "Он отображается при первом запуске приложения TapTaxi (патч-версия).",
        parse_mode=ParseMode.HTML,
    )


@router.message(F.text & ~F.text.startswith("/"))
async def handle_device_id(msg: Message):
    """Any non-command text is treated as a device_id submission."""
    if is_admin(msg.from_user.id) and not _config.auto_approve:
        # Admins submitting text are handled separately
        await msg.answer("ℹ️ Используй команды: /list, /approve, /revoke")
        return

    device_id = msg.text.strip()

    if len(device_id) < 4 or len(device_id) > 128:
        await msg.answer("❌ Неверный Device ID. Проверь и попробуй ещё раз.")
        return

    username = msg.from_user.username
    is_new = await _db.upsert_request(device_id, msg.from_user.id, username)

    record = await _db.get(device_id)

    if record and record["status"] == "approved":
        # Already approved — just resend the code
        await msg.answer(
            f"✅ Твой лицензионный код:\n\n"
            f"<code>{record['license_code']}</code>\n\n"
            f"📱 Device ID: <code>{device_id}</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    if _config.auto_approve:
        code = generate_license(device_id, _config.secret_key)
        await _db.approve(device_id, code)
        await msg.answer(
            f"✅ Твой лицензионный код:\n\n"
            f"<code>{code}</code>\n\n"
            f"📱 Device ID: <code>{device_id}</code>",
            parse_mode=ParseMode.HTML,
        )

        if _config.admin_ids:
            for admin_id in _config.admin_ids:
                try:
                    await _bot.send_message(
                        admin_id,
                        f"⚙️ <b>Автовыдача лицензии</b>\n\n"
                        f"👤 {_user_label(msg)} (id: <code>{msg.from_user.id}</code>)\n"
                        f"📱 Device ID: <code>{device_id}</code>\n"
                        f"🔑 Код: <code>{code}</code>",
                        parse_mode=ParseMode.HTML,
                    )
                except Exception as e:
                    logger.warning(f"Failed to notify admin {admin_id}: {e}")
        return

    if not is_new:
        await msg.answer(
            "⏳ Твоя заявка уже на рассмотрении. Ожидай подтверждения от администратора."
        )
        return

    await msg.answer(
        "📨 Заявка отправлена! Ожидай подтверждения от администратора.\n"
        "Обычно это занимает несколько минут."
    )

    # Notify all admins
    for admin_id in _config.admin_ids:
        try:
            await _bot.send_message(
                admin_id,
                f"🆕 <b>Новая заявка на лицензию</b>\n\n"
                f"👤 {_user_label(msg)} (id: <code>{msg.from_user.id}</code>)\n"
                f"📱 Device ID: <code>{device_id}</code>",
                parse_mode=ParseMode.HTML,
                reply_markup=_approve_keyboard(device_id),
            )
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin_id}: {e}")


# ── Admin button handlers ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("approve:"))
async def cb_approve(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return

    device_id = cb.data.split(":", 1)[1]
    code = generate_license(device_id, _config.secret_key)
    record = await _db.approve(device_id, code)

    await cb.answer("✅ Лицензия выдана!")
    await cb.message.edit_text(
        cb.message.text + f"\n\n✅ <b>Одобрено</b> — код: <code>{code}</code>",
        parse_mode=ParseMode.HTML,
        reply_markup=None,
    )

    if record:
        try:
            await _send_license_to_user(record["telegram_id"], device_id, code)
        except Exception as e:
            logger.warning(f"Failed to send license to driver: {e}")
            await cb.message.answer(f"⚠️ Не удалось отправить код водителю (telegram_id={record['telegram_id']})")


@router.callback_query(F.data.startswith("reject:"))
async def cb_reject(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return

    device_id = cb.data.split(":", 1)[1]
    await _db.revoke(device_id)

    await cb.answer("❌ Отклонено")
    await cb.message.edit_text(
        cb.message.text + "\n\n❌ <b>Отклонено</b>",
        parse_mode=ParseMode.HTML,
        reply_markup=None,
    )

    record = await _db.get(device_id)
    if record:
        try:
            await _bot.send_message(
                record["telegram_id"],
                "❌ Ваша заявка на лицензию отклонена.\n"
                "Свяжитесь с администратором для уточнения.",
            )
        except Exception:
            pass


# ── Admin commands ─────────────────────────────────────────────────────────

@router.message(Command("approve"))
async def cmd_approve(msg: Message):
    """Usage: /approve <device_id>"""
    if not is_admin(msg.from_user.id):
        return

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("Использование: /approve <device_id>")
        return

    device_id = parts[1].strip()
    code = generate_license(device_id, _config.secret_key)
    record = await _db.approve(device_id, code)

    if not record:
        await msg.answer(f"❌ Device ID <code>{device_id}</code> не найден в базе.", parse_mode=ParseMode.HTML)
        return

    await msg.answer(
        f"✅ Лицензия выдана!\n"
        f"Device: <code>{device_id}</code>\n"
        f"Код: <code>{code}</code>",
        parse_mode=ParseMode.HTML,
    )

    try:
        await _send_license_to_user(record["telegram_id"], device_id, code)
    except Exception as e:
        await msg.answer(f"⚠️ Не смог отправить код водителю: {e}")


@router.message(Command("revoke"))
async def cmd_revoke(msg: Message):
    """Usage: /revoke <device_id>"""
    if not is_admin(msg.from_user.id):
        return

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("Использование: /revoke <device_id>")
        return

    device_id = parts[1].strip()
    ok = await _db.revoke(device_id)

    if ok:
        await msg.answer(f"🚫 Лицензия для <code>{device_id}</code> отозвана.", parse_mode=ParseMode.HTML)
    else:
        await msg.answer(f"❌ Device ID <code>{device_id}</code> не найден.", parse_mode=ParseMode.HTML)


@router.message(Command("list"))
async def cmd_list(msg: Message):
    """Show all licenses."""
    if not is_admin(msg.from_user.id):
        return

    records = await _db.list_all()
    if not records:
        await msg.answer("📭 Лицензий нет.")
        return

    lines = [f"📋 <b>Лицензии ({len(records)}):</b>\n"]
    for r in records[:30]:  # max 30 to avoid message size limit
        icon = _status_icon(r["status"])
        username = f"@{r['telegram_username']}" if r["telegram_username"] else f"id:{r['telegram_id']}"
        lines.append(
            f"{icon} <code>{r['device_id']}</code>\n"
            f"   {username} | {r['status']}"
            + (f" | <code>{r['license_code']}</code>" if r.get("license_code") else "")
        )

    await msg.answer("\n".join(lines), parse_mode=ParseMode.HTML)


@router.message(Command("gencode"))
async def cmd_gencode(msg: Message):
    """Generate a code for a device_id without saving to DB. Usage: /gencode <device_id>"""
    if not is_admin(msg.from_user.id):
        return

    parts = msg.text.split(maxsplit=1)
    if len(parts) < 2:
        await msg.answer("Использование: /gencode <device_id>")
        return

    device_id = parts[1].strip()
    code = generate_license(device_id, _config.secret_key)
    await msg.answer(
        f"🔑 Код для <code>{device_id}</code>:\n<code>{code}</code>",
        parse_mode=ParseMode.HTML,
    )


# ── Startup ────────────────────────────────────────────────────────────────

async def main():
    global _config, _db, _bot

    _config = Config.from_env()
    errors = _config.validate()
    if errors:
        for e in errors:
            logger.error(f"Config error: {e}")
        sys.exit(1)

    _db = Database(_config.db_path)
    await _db.init()

    _bot = Bot(token=_config.bot_token)

    dp = Dispatcher()
    dp.include_router(router)

    logger.info("License bot started")
    await dp.start_polling(_bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
