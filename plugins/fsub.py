import logging
import time

from pyrogram import Client, filters
from pyrogram.enums import ChatMemberStatus
from pyrogram.types import ChatJoinRequest, ChatMemberUpdated, Message

from config import ADMINS
from database import add_join_request, update_join_request_status, remove_join_request, total_users
from helper.delivery import format_duration
from helper.fsub_helper import ensure_fsub_loaded, process_fsub_add, process_fsub_remove, process_flink_add, flink_lines


logger = logging.getLogger(__name__)

_ACTIVE = {ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER}


@Client.on_chat_join_request()
async def fsub_join_request(client: Client, chat_join_request: ChatJoinRequest):
    try:
        await ensure_fsub_loaded(client)
        channel_id = chat_join_request.chat.id
        if channel_id not in client.fsub_dict:
            return
        await add_join_request(channel_id, chat_join_request.from_user.id)
    except Exception:
        logger.exception("Join request save failed")


@Client.on_chat_member_updated()
async def fsub_member_update(client: Client, update: ChatMemberUpdated):
    try:
        await ensure_fsub_loaded(client)
        channel_id = update.chat.id
        if channel_id not in client.fsub_dict:
            return
        affected = update.new_chat_member or update.old_chat_member
        if not affected or not affected.user or affected.user.id == client.me.id:
            return
        user_id = affected.user.id
        old = update.old_chat_member.status if update.old_chat_member else None
        new = update.new_chat_member.status if update.new_chat_member else None

        if new in _ACTIVE and old not in _ACTIVE:
            await update_join_request_status(channel_id, user_id, "approved", only_if="pending")
        elif old in _ACTIVE and new not in _ACTIVE:
            await remove_join_request(channel_id, user_id)
    except Exception:
        logger.exception("Member update handling failed")


@Client.on_message(filters.command("fsub") & filters.private)
async def fsub_command(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    await ensure_fsub_loaded(client)
    if len(message.command) < 4:
        return

    status_msg = await message.reply("<b>Adding Force-Sub Channel.....</b>")
    result = await process_fsub_add(client, message.command[1:])
    await status_msg.edit(result)


@Client.on_message(filters.command("ffsub") & filters.private)
async def ffsub_command(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    await ensure_fsub_loaded(client)
    if len(message.command) < 2:
        return
    result = await process_flink_add(client, message.command[1:])
    await message.reply(result)


@Client.on_message(filters.command("status") & filters.private)
async def fsub_status(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return

    start = time.monotonic()
    sent = await message.reply("<b>Pinging.....</b>")
    ping_ms = (time.monotonic() - start) * 1000

    uptime = format_duration(int(time.time() - getattr(client, "start_time", time.time())))
    users_count = await total_users()

    await ensure_fsub_loaded(client)

    text = (
        "<b>⧉ <u>ʙᴏᴛ ꜱᴛᴀᴛᴜꜱ</u></b>\n\n"
        f"<b>┠ ᴘɪɴɢ:</b> {ping_ms:.2f} ms\n"
        f"<b>┠ ᴜᴘᴛɪᴍᴇ:</b> {uptime}\n"
        f"<b>┠ ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ:</b> {users_count}\n\n"
    )

    if not client.fsub_dict:
        text += "<b>⧉ <u>ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ</u>:</b>\n<i>_ɴᴏ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ ᴀᴅᴅᴇᴅ ʏᴇᴛ_</i>"
    else:
        lines = []
        for idx, (channel_id, data) in enumerate(client.fsub_dict.items(), start=1):
            kind = "Fake" if data.get("fake") else "Real"
            mode = "Request" if data.get("request") else "Direct"
            expiry = f"{data.get('timer', 0)}m" if data.get("timer", 0) > 0 else "Never"
            lines.append(
                f"{idx}. <b>{data.get('name')}</b> — <code>{channel_id}</code>\n"
                f"<b>▸ ᴛʏᴘᴇ:</b> {kind}\n<b>▸ ᴍᴏᴅᴇ:</b> {mode}\n<b>▸ ᴇxᴘɪʀʏ:</b> {expiry}"
            )
        text += "<b>⧉ <u>ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟꜱ</u>:</b>\n\n" + "<blockquote>" + "\n\n".join(lines) + "</blockquote>"

    links = flink_lines(client)
    if links:
        text += "\n\n<b>⧉ <u>ʟɪɴᴋ ꜰ-ꜱᴜʙ</u>:</b>\n\n" + "<blockquote>" + "\n\n".join(links) + "</blockquote>"

    await sent.edit(text)


@Client.on_message(filters.command("rmf") & filters.private)
async def fsub_remove(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    if len(message.command) != 2:
        return

    await ensure_fsub_loaded(client)
    result = await process_fsub_remove(client, message.command[1])
    await message.reply(result)


