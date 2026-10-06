import asyncio
import logging
import time

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, UserIsBlocked, InputUserDeactivated, ChannelInvalid, PeerIdInvalid
from pyrogram.types import Message

from config import ADMINS
from database import full_userbase, del_user

logger = logging.getLogger(__name__)

PROGRESS_EDIT_INTERVAL = 4


def _progress_text(done: int, total: int, successful: int, blocked: int, deleted: int, unsuccessful: int) -> str:
    return (
        "<blockquote><b>📢 ʙʀᴏᴀᴅᴄᴀꜱᴛɪɴɢ...</b></blockquote>\n"
        f"<b>ᴘʀᴏᴄᴇꜱꜱᴇᴅ :</b> {done}/{total}\n"
        f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ :</b> {successful}\n"
        f"<b>ʙʟᴏᴄᴋᴇᴅ :</b> {blocked}\n"
        f"<b>ᴅᴇʟᴇᴛᴇᴅ :</b> {deleted}\n"
        f"<b>ᴜɴꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ :</b> {unsuccessful}"
    )


def _final_text(total: int, successful: int, blocked: int, deleted: int, unsuccessful: int) -> str:
    return (
        "<blockquote><b>ʙʀᴏᴀᴅᴄᴀꜱᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ</b></blockquote>\n"
        f"<b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ :</b> {total}\n"
        f"<b>ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ :</b> {successful}\n"
        f"<b>ʙʟᴏᴄᴋᴇᴅ :</b> {blocked}\n"
        f"<b>ᴅᴇʟᴇᴛᴇᴅ :</b> {deleted}\n"
        f"<b>ᴜɴꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ :</b> {unsuccessful}"
    )


async def _run_broadcast(client: Client, status_msg: Message, broadcast_msg: Message, pin: bool = False):
    user_ids = await full_userbase()
    total = len(user_ids)
    done = successful = blocked = deleted = unsuccessful = 0
    last_edit = 0.0

    async def _update_progress(force: bool = False):
        nonlocal last_edit
        now = time.monotonic()
        if not force and (now - last_edit) < PROGRESS_EDIT_INTERVAL:
            return
        last_edit = now
        try:
            await status_msg.edit(_progress_text(done, total, successful, blocked, deleted, unsuccessful))
        except Exception:
            pass

    for chat_id in user_ids:
        try:
            sent = await broadcast_msg.copy(chat_id, reply_markup=broadcast_msg.reply_markup)
            successful += 1
            if pin:
                try:
                    await client.pin_chat_message(chat_id=chat_id, message_id=sent.id, both_sides=True)
                except Exception:
                    logger.exception("Failed to pin broadcast message in chat_id=%s", chat_id)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            try:
                sent = await broadcast_msg.copy(chat_id, reply_markup=broadcast_msg.reply_markup)
                successful += 1
                if pin:
                    try:
                        await client.pin_chat_message(chat_id=chat_id, message_id=sent.id, both_sides=True)
                    except Exception:
                        logger.exception("Failed to pin broadcast message in chat_id=%s", chat_id)
            except Exception:
                logger.exception("Failed to broadcast to chat_id=%s after FloodWait", chat_id)
                unsuccessful += 1
        except UserIsBlocked:
            await del_user(chat_id)
            blocked += 1
        except (InputUserDeactivated, ChannelInvalid, PeerIdInvalid):
            await del_user(chat_id)
            deleted += 1
        except Exception:
            logger.exception("Failed to broadcast to chat_id=%s", chat_id)
            unsuccessful += 1

        done += 1
        await _update_progress()

    await _update_progress(force=True)
    try:
        await status_msg.edit(_final_text(total, successful, blocked, deleted, unsuccessful))
    except Exception:
        logger.exception("Failed to send final broadcast status")


async def _require_reply(message: Message) -> bool:
    if message.reply_to_message:
        return True
    warn = await message.reply("<b>❗Reply to a message to broadcast it.</b>")
    await asyncio.sleep(8)
    await warn.delete()
    return False


@Client.on_message(filters.private & filters.command("broadcast"))
async def broadcast_command(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    if not await _require_reply(message):
        return

    status_msg = await message.reply("<blockquote><i>Broadcasting message.. this will take some time</i></blockquote>")
    await _run_broadcast(client, status_msg, message.reply_to_message, pin=False)


@Client.on_message(filters.private & filters.command("pbroadcast"))
async def pin_broadcast_command(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    if not await _require_reply(message):
        return

    status_msg = await message.reply("<blockquote><i>Broadcasting message.. this will take some time</i></blockquote>")
    await _run_broadcast(client, status_msg, message.reply_to_message, pin=True)
    
