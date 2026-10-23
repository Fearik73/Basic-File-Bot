import logging

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup

from config import ADMINS, START_MESSAGE, START_BUTTONS, MESSAGE_EFFECT_ID, START_IMAGE
from database import add_user, total_users
from helper.styling import styled_button, send_styled, safe_reply
from helper.delivery import deliver, send_batch
from helper.fsub_helper import force_sub
from helper.settings_store import ensure_settings_loaded
from plugins.shortner import get_short

logger = logging.getLogger(__name__)


def build_start_markup() -> InlineKeyboardMarkup | None:
    buttons = [
        styled_button(b["label"], url=b.get("url"))
        for b in START_BUTTONS
    ]
    if not buttons:
        return None
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    return InlineKeyboardMarkup(rows)


async def send_shortener_gate(client: Client, message: Message, payload: str):
    deep_link = f"https://t.me/{client.me.username}?start=sh_{payload}"
    try:
        short_link = await get_short(deep_link, client)
    except Exception:
        logger.exception("Failed to generate short link for payload=%s", payload)
        short_link = deep_link

    tutorial_link = client.settings.get("tutorial_link") or short_link

    buttons = InlineKeyboardMarkup([
        [styled_button("• ᴄʟɪᴄᴋ ʜᴇʀᴇ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ •", url=short_link)],
        [
            styled_button("ᴛᴜᴛᴏʀɪᴀʟ", url=tutorial_link),
            styled_button("ᴄʟᴏꜱᴇ", callback_data="close"),
        ],
    ])

    await send_styled(
        client,
        message.chat.id,
        "<b>➲ ʏᴏᴜʀ ʟɪɴᴋ ɪꜱ ʀᴇᴀᴅʏ!</b>\n\n<i>_Click the button given below to download your file_</i>",
        reply_markup=buttons,
    )


@Client.on_message(filters.command("start") & filters.private)
@force_sub
async def start_handler(client: Client, message: Message):
    try:
        await add_user(
            message.from_user.id,
            message.from_user.username,
            message.from_user.first_name,
            message.from_user.last_name,
        )
    except Exception:
        logger.exception("Failed to store user %s in MongoDB", message.from_user.id)

    if len(message.command) < 2:
        await send_styled(
            client,
            message.chat.id,
            START_MESSAGE,
            reply_markup=build_start_markup(),
            photo=START_IMAGE or None,
            message_effect_id=MESSAGE_EFFECT_ID,
        )
        return

    payload = message.command[1]

    is_gated_link = payload.startswith("sh_")
    if is_gated_link:
        payload = payload[3:]

    parts = payload.split("_")
    payload_lower = payload.lower()
    is_file_link = payload_lower.startswith("batch_") or payload_lower.startswith("single_")

    if is_file_link and not is_gated_link and message.from_user.id not in ADMINS:
        await ensure_settings_loaded(client)
        if client.settings.get("shortner_enabled", False):
            await send_shortener_gate(client, message, payload)
            return

    if payload_lower.startswith("batch_") and len(parts) >= 3:
        try:
            first_id = int(parts[1])
            last_id = int(parts[2])
        except ValueError:
            return
        status_msg = None if (client.fsub_dict or client.flink_dict) else await safe_reply(message, "<b>Collecting Files.....</b>")
        await send_batch(client, message.chat.id, first_id, last_id, status_msg)

    elif payload_lower.startswith("single_") and len(parts) >= 3:
        try:
            message_id = int(parts[-1])
        except ValueError:
            return
        status_msg = None if (client.fsub_dict or client.flink_dict) else await safe_reply(message, "<b>Collecting Files.....</b>")
        await deliver(client, message.chat.id, message_id, status_msg)


@Client.on_callback_query(filters.regex("^close$"))
async def close_callback(client: Client, query: CallbackQuery):
    await query.message.delete()
    await query.answer()


@Client.on_message(filters.command("users") & filters.private)
async def user_count(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    total = await total_users()
    await safe_reply(message, f"<b>{total} Users are using this bot!!</b>")

