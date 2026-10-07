import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup

from config import ADMINS, SETTINGS_IMAGE
from database import update_settings
from helper.styling import styled_button, send_styled, edit_styled
from helper.delivery import format_duration
from helper.settings_store import ensure_settings_loaded
from helper.fsub_helper import ensure_fsub_loaded, process_fsub_add, process_fsub_remove, flink_lines

logger = logging.getLogger(__name__)


pending_inputs = {}


async def _wait_for_reply(chat_id: int, user_id: int, timeout: int = 60):
    future = asyncio.get_event_loop().create_future()
    pending_inputs[(chat_id, user_id)] = future
    try:
        return await asyncio.wait_for(future, timeout=timeout)
    except asyncio.TimeoutError:
        return None
    finally:
        pending_inputs.pop((chat_id, user_id), None)


@Client.on_message(filters.private & filters.text & filters.incoming, group=-1)
async def _settings_input_interceptor(client: Client, message: Message):
    key = (message.chat.id, message.from_user.id)
    future = pending_inputs.get(key)
    if future and not future.done():
        future.set_result(message.text)
        message.stop_propagation()


def build_main_settings_panel(client: Client):
    protect = "ON" if client.settings.get("protect_content") else "OFF"
    auto_delete = client.settings.get("auto_delete", 0)
    auto_delete_display = format_duration(auto_delete) if auto_delete > 0 else "Disabled"
    shortner = "ON" if client.settings.get("shortner_enabled") else "OFF"
    text = (
        "<b>➲ <u>ʙᴏᴛ ꜱᴇᴛᴛɪɴɢꜱ</u></b>\n"
        "──────────────────\n"
        f"<blockquote><b>▸ ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ:</b> {protect}\n"
        f"<b>▸ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇʀ:</b> {auto_delete_display}\n"
        f"<b>▸ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ:</b> {len(client.fsub_dict) + len(client.flink_dict)}\n"
        f"<b>▸ ꜱʜᴏʀᴛɴᴇʀ:</b> {shortner}</blockquote>"
    )
    markup = InlineKeyboardMarkup([
        [
            styled_button("ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ", callback_data="set_menu_protect", style="primary"),
            styled_button("ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ", callback_data="set_menu_autodel", style="primary"),
        ],
        [
            styled_button("ꜰᴏʀᴄᴇ ꜱᴜʙ", callback_data="set_menu_fsub", style="danger"),
            styled_button("ꜱʜᴏʀᴛɴᴇʀ", callback_data="set_menu_shortner", style="danger"),
        ],
    ])
    return text, markup


def build_protect_panel(client: Client):
    is_on = client.settings.get("protect_content", False)
    on_label = f"{'🟢' if is_on else '○'} On"
    off_label = f"{'🟢' if not is_on else '○'} Off"
    text = (
        "<b>➲ ᴘʀᴏᴛᴇᴄᴛ ᴄᴏɴᴛᴇɴᴛ</b>\n\n"
        "<i>_ᴡʜᴇɴ ᴏɴ, ᴜꜱᴇʀꜱ ᴡᴏɴ'ᴛ ʙᴇ ᴀʙʟᴇ ᴛᴏ ꜰᴏʀᴡᴀʀᴅ ᴏʀ ꜱᴀᴠᴇ ꜰɪʟᴇꜱ ꜱᴇɴᴛ ʙʏ ᴛʜᴇ ʙᴏᴛ_</i>"
    )
    markup = InlineKeyboardMarkup([
        [
            styled_button(on_label, callback_data="set_protect_on", style="primary"),
            styled_button(off_label, callback_data="set_protect_off", style="primary"),
        ],
        [styled_button("◂ ʙᴀᴄᴋ", callback_data="set_menu_main", style="danger")],
    ])
    return text, markup


def build_fsub_panel(client: Client):
    real = [f"• {data.get('name')} (<code>{cid}</code>)" for cid, data in client.fsub_dict.items() if not data.get("fake")]
    fake = [f"• {data.get('name')} (<code>{cid}</code>)" for cid, data in client.fsub_dict.items() if data.get("fake")]
    text = (
        "<b>➲ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ</b>\n"
        "──────────────────\n\n"
        "<b>☰ ʀᴇᴀʟ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ ʟɪꜱᴛ:</b>\n" + ("\n".join(real) if real else "_No Channel added yet_") + "\n\n"
        "<b>☰ ꜰᴀᴋᴇ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ ʟɪꜱᴛ:</b>\n" + ("\n".join(fake) if fake else "_No Channel added yet_") + "\n\n"
        "<b>☰ ʟɪɴᴋ ꜰꜱᴜʙ ʟɪꜱᴛ:</b>\n" + ("<blockquote>" + "\n\n".join(flink_lines(client)) + "</blockquote>" if client.flink_dict else "_No Link added yet_")
    )
    markup = InlineKeyboardMarkup([
        [
            styled_button("ᴀᴅᴅ ᴄʜᴀɴɴᴇʟ", callback_data="set_fsub_add", style="primary"),
            styled_button("ʀᴇᴍᴏᴠᴇ ᴄʜᴀɴɴᴇʟ", callback_data="set_fsub_remove", style="primary"),
        ],
        [styled_button("◂ ʙᴀᴄᴋ", callback_data="set_menu_main", style="danger")],
    ])
    return text, markup


@Client.on_message(filters.command("settings") & filters.private)
async def settings_command(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    await ensure_settings_loaded(client)
    await ensure_fsub_loaded(client)
    text, markup = build_main_settings_panel(client)
    await send_styled(client, message.chat.id, text, reply_markup=markup, photo=SETTINGS_IMAGE or None)


@Client.on_callback_query(filters.regex("^set_menu_main$"))
async def settings_menu_main(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)
    await ensure_fsub_loaded(client)
    text, markup = build_main_settings_panel(client)
    await edit_styled(client, query.message, text, reply_markup=markup)
    await query.answer()


@Client.on_callback_query(filters.regex("^set_menu_protect$"))
async def settings_menu_protect(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)
    text, markup = build_protect_panel(client)
    await edit_styled(client, query.message, text, reply_markup=markup)
    await query.answer()


@Client.on_callback_query(filters.regex("^set_protect_(on|off)$"))
async def settings_toggle_protect(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)
    value = query.data.endswith("_on")
    client.settings["protect_content"] = value
    try:
        await update_settings({"protect_content": value})
    except Exception:
        logger.exception("Failed to persist protect_content setting")
    text, markup = build_protect_panel(client)
    await edit_styled(client, query.message, text, reply_markup=markup)
    await query.answer(f"Protect Content {'enabled' if value else 'disabled'}")


@Client.on_callback_query(filters.regex("^set_menu_autodel$"))
async def settings_menu_autodel(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)
    current = client.settings.get("auto_delete", 0)

    await edit_styled(
        client,
        query.message,
        "<b>➲ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇ</b>\n\n"
        f"<b>ᴄᴜʀʀᴇɴᴛ ᴛɪᴍᴇʀ:</b> {current}\n\n"
        "<i>_ᴇɴᴛᴇʀ ɴᴇᴡ ɪɴᴛᴇɢᴇʀ ᴠᴀʟᴜᴇ ᴏꜰ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ ᴛɪᴍᴇʀ, ᴋᴇᴇᴘ 0 ᴛᴏ ᴅɪꜱᴀʙʟᴇ ᴀᴜᴛᴏ ᴅᴇʟᴇᴛᴇ "
        "ᴀɴᴅ ᴡᴀɪᴛ ꜰᴏʀ 120 ꜱᴇᴄᴏɴᴅ ᴛɪᴍᴇᴏᴜᴛ ᴛᴏ ʙᴇ ᴄᴏᴍᴘʟᴇᴛᴇᴅ!_</i>",
    )
    await query.answer()

    reply_text = await _wait_for_reply(query.message.chat.id, query.from_user.id, timeout=60)

    if reply_text is None:
        text = "<b>😕 ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ʏᴏᴜ ᴅɪᴅɴ'ᴛ ᴀᴅᴅ ᴀɴʏ ᴛɪᴍᴇ ᴠᴀʟᴜᴇ. ꜱᴇᴀꜱᴏɴ ᴛɪᴍᴇᴅ ᴏᴜᴛ_</i>"
        markup = InlineKeyboardMarkup([[styled_button("◂ ʙᴀᴄᴋ", callback_data="set_menu_main", style="danger")]])
        await edit_styled(client, query.message, text, reply_markup=markup)
        return

    try:
        value = int(reply_text.strip())
    except ValueError:
        text = "<b>😵‍💫 ɪɴᴠᴀʟɪᴅ ᴠᴀʟᴜᴇ.</b> ᴘʟᴇᴀꜱᴇ ꜱᴇɴᴅ ᴀ ᴠᴀʟɪᴅ ɪɴᴛᴇɢᴇʀ"
        markup = InlineKeyboardMarkup([[styled_button("◂ ʙᴀᴄᴋ", callback_data="set_menu_main", style="danger")]])
        await edit_styled(client, query.message, text, reply_markup=markup)
        return

    if value != -1:
        timer = max(value, 0)
        client.settings["auto_delete"] = timer
        try:
            await update_settings({"auto_delete": timer})
        except Exception:
            logger.exception("Failed to persist auto_delete setting")

    text, markup = build_main_settings_panel(client)
    await edit_styled(client, query.message, text, reply_markup=markup)


@Client.on_callback_query(filters.regex("^set_menu_fsub$"))
async def settings_menu_fsub(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_fsub_loaded(client)
    text, markup = build_fsub_panel(client)
    await edit_styled(client, query.message, text, reply_markup=markup)
    await query.answer()


@Client.on_callback_query(filters.regex("^set_fsub_add$"))
async def settings_fsub_add(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_fsub_loaded(client)

    await edit_styled(
        client,
        query.message,
        "<b>Q. ʜᴏᴡ ᴛᴏ ᴀᴅᴅ ᴀ ᴄʜᴀɴɴᴇʟ?</b>\n\n"
        "ꜰɪʀꜱᴛ ꜱᴇɴᴅ ᴍᴇ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ᴅᴀᴛᴀ ɪɴ ᴛʜɪꜱ ꜰᴏʀᴍᴀᴛ:\n\n"
        "» {channel_id} yes/no Timer\n\n"
        "ᴀᴅᴅ X ᴀꜰᴛᴇʀ ᴛʜᴇ ᴛɪᴍᴇʀ ᴛᴏ ᴍᴀᴋᴇ ɪᴛ ᴀ ꜰᴀᴋᴇ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ\n\n"
        "ʟɪɴᴋ ᴏɴʟʏ: » {link} always/once\n\n"
        "<blockquote expandable><b><i>_ʜᴇʀᴇ ʏᴇꜱ ᴍᴇᴀɴꜱ ʀᴇQᴜᴇꜱᴛ ᴍᴏᴅᴇ ᴀɴᴅ ɴᴏ ᴍᴇᴀɴꜱ ᴅɪʀᴄᴛ ᴍᴏᴅᴇ."
        " ɪɴ ʀᴇQᴜᴇꜱᴛ ᴍᴏᴅᴇ ᴜꜱᴇʀ ꜱᴇɴᴅ ʀᴇQᴜᴇꜱᴛ ɪɴ ꜰꜱᴜʙ ᴄʜᴀɴɴᴇʟ ʙᴜᴛ ɪɴ ᴅɪʀᴄᴛ ᴍᴏᴅᴇ ᴛʜᴇʏ ᴀʀᴇ ᴀʟʟᴏᴡᴇᴅ ᴛᴏ ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ ᴅɪʀᴇᴄᴛʟʏ."
        "ᴀɴᴅ ᴛɪᴍᴇʀ ɪꜱ ᴜꜱᴇ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴀᴄᴄᴇꜱꜱɪʙʟᴇ ʟɪɴᴋ ꜰᴏʀ ᴛʜᴀᴛ ᴘᴀʀᴛɪᴄᴜʟᴀʀ ᴛɪᴍᴇ ᴘᴇʀɪᴏᴅ, ᴀꜰᴛᴇʀ ᴛʜᴀᴛ ʟɪɴᴋ ᴡɪʟʟ ᴇxᴘɪʀᴇ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ,"
        "ᴛᴏ ᴋᴇᴇᴘ ʟɪɴᴋ ɴᴏɴ ᴇxᴘɪʀʏ ʏᴏᴜ ᴄᴀɴ ᴘᴜᴛ 0 ᴀꜱ ᴛɪᴍᴇʀ ᴠᴀʟᴜᴇ_</i></b></blockquote>",
    )
    await query.answer()

    reply_text = await _wait_for_reply(query.message.chat.id, query.from_user.id, timeout=60)

    if reply_text is None:
        text = "<b>⚠️ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ꜱᴇᴀꜱᴏɴ ᴄᴀɴᴄᴇʟʟᴇᴅ ʙᴇᴄᴀᴜꜱᴇ ɴᴏ ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ ꜰʀᴏᴍ ᴜꜱᴇʀ!_</i>"
    else:
        text = await process_fsub_add(client, reply_text.split())

    markup = InlineKeyboardMarkup([[styled_button("◂ ʙᴀᴄᴋ", callback_data="set_menu_fsub", style="danger")]])
    await edit_styled(client, query.message, text, reply_markup=markup)


@Client.on_callback_query(filters.regex("^set_fsub_remove$"))
async def settings_fsub_remove(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_fsub_loaded(client)

    await edit_styled(
        client,
        query.message,
        "<b>➲ ʀᴇᴍᴏᴠᴇ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ</b>\n\n"
        "<i>ꜱᴇɴᴅ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ɪᴅ ᴛᴏ ʀᴇᴍᴏᴠᴇ_</i>",
    )
    await query.answer()

    reply_text = await _wait_for_reply(query.message.chat.id, query.from_user.id, timeout=60)

    if reply_text is None:
        text = "<b>⚠️ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ꜱᴇᴀꜱᴏɴ ᴄᴀɴᴄᴇʟʟᴇᴅ ʙᴇᴄᴀᴜꜱᴇ ɴᴏ ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ ꜰʀᴏᴍ ᴜꜱᴇʀ!_</i>"
    else:
        text = await process_fsub_remove(client, reply_text.strip())

    markup = InlineKeyboardMarkup([[styled_button("◂ ʙᴀᴄᴋ", callback_data="set_menu_fsub", style="danger")]])
    await edit_styled(client, query.message, text, reply_markup=markup)
    
