import asyncio
import logging

from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait

from config import DB_CHANNEL_ID
from helper.settings_store import ensure_settings_loaded

logger = logging.getLogger(__name__)

CHUNK_SIZE = 200


async def get_messages_chunk(client: Client, message_ids: list):
    try:
        msgs = await client.get_messages(DB_CHANNEL_ID, message_ids=message_ids)
        return [msg for msg in msgs if msg is not None]
    except FloodWait as e:
        logger.warning("FloodWait %ss while fetching %d message(s)", e.value, len(message_ids))
        await asyncio.sleep(e.value)
        return await get_messages_chunk(client, message_ids)
    except Exception:
        logger.exception("Failed to fetch messages %s", message_ids)
        return []


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "0 seconds"
    units = [
        ("year", 31536000),
        ("day", 86400),
        ("hour", 3600),
        ("minute", 60),
        ("second", 1),
    ]
    for name, unit_secs in units:
        if seconds >= unit_secs:
            value = seconds // unit_secs
            return f"{value} {name}{'s' if value != 1 else ''}"
    return f"{seconds} seconds"


def convert_time(duration_seconds: int) -> str:
    periods = [
        ('Yᴇᴀʀ', 60 * 60 * 24 * 365),
        ('Mᴏɴᴛʜ', 60 * 60 * 24 * 30),
        ('Day', 60 * 60 * 24),
        ('Hour', 60 * 60),
        ('Minute', 60),
        ('Second', 1)
    ]

    parts = []
    for period_name, period_seconds in periods:
        if duration_seconds >= period_seconds:
            num_periods = duration_seconds // period_seconds
            duration_seconds %= period_seconds
            parts.append(f"{num_periods} {period_name}{'s' if num_periods > 1 else ''}")

    if len(parts) == 0:
        return "0 Sᴇᴄᴏɴᴅ"
    elif len(parts) == 1:
        return parts[0]
    else:
        return ', '.join(parts[:-1]) + ' ᴀɴᴅ ' + parts[-1]

DEL_MSG = """<blockquote><b><i>This File is automatically deleted in {time}. Forward in your Saved Messages..!</i></b></blockquote>"""

async def _schedule_auto_delete(msg: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def _schedule_notice_expiry(notice: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await notice.edit_text("<b><i>Time is over Your files has been deleted. ✅</i></b>")
    except Exception:
        pass


async def _schedule_delete(client: Client, sent: Message):
    if not sent:
        return
    timer = client.settings.get("auto_delete", 0)
    if timer <= 0:
        return
    asyncio.create_task(_schedule_auto_delete(sent, timer))


async def _send_autodelete_notice(client: Client, chat_id: int, reply_to: Message = None):
    timer = client.settings.get("auto_delete", 0)
    if timer <= 0:
        return
    try:
        text = DEL_MSG.format(time=convert_time(timer))
        if reply_to:
            notice = await reply_to.reply_text(text, disable_web_page_preview=True)
        else:
            notice = await client.send_message(chat_id, text=text, disable_web_page_preview=True)
        asyncio.create_task(_schedule_notice_expiry(notice, timer))
    except Exception:
        logger.exception("Failed to send auto-delete warning to chat_id=%s", chat_id)


async def _warn_and_schedule_delete(client: Client, chat_id: int, sent: Message):
    if not sent:
        return
    await _send_autodelete_notice(client, chat_id, reply_to=sent)
    await _schedule_delete(client, sent)


async def copy_with_retry(msg, chat_id: int, protect_content: bool = False):
    try:
        return await msg.copy(chat_id, reply_markup=msg.reply_markup, protect_content=protect_content)
    except FloodWait as e:
        logger.warning("FloodWait %ss while delivering message_id=%s -> chat_id=%s", e.value, msg.id, chat_id)
        await asyncio.sleep(e.value)
        try:
            return await msg.copy(chat_id, reply_markup=msg.reply_markup, protect_content=protect_content)
        except Exception:
            logger.exception("Failed to deliver message_id=%s -> chat_id=%s", msg.id, chat_id)
            return None
    except Exception:
        logger.exception("Failed to deliver message_id=%s -> chat_id=%s", msg.id, chat_id)
        return None


async def deliver(client: Client, chat_id: int, message_id: int, status_msg: Message = None):
    await ensure_settings_loaded(client)
    msgs = await get_messages_chunk(client, [message_id])
    if status_msg:
        try:
            await status_msg.delete()
        except Exception:
            pass
    if not msgs:
        return
    sent = await copy_with_retry(msgs[0], chat_id, protect_content=client.settings.get("protect_content", False))
    await _warn_and_schedule_delete(client, chat_id, sent)


async def send_batch(client: Client, chat_id: int, first_id: int, last_id: int, status_msg: Message = None):
    await ensure_settings_loaded(client)
    all_ids = list(range(first_id, last_id + 1))
    fetched = 0
    any_sent = False
    while fetched != len(all_ids):
        chunk_ids = all_ids[fetched: fetched + CHUNK_SIZE]
        msgs = await get_messages_chunk(client, chunk_ids)
        if status_msg:
            try:
                await status_msg.delete()
            except Exception:
                pass
            status_msg = None
        for msg in msgs:
            sent = await copy_with_retry(msg, chat_id, protect_content=client.settings.get("protect_content", False))
            await _schedule_delete(client, sent)
            if sent:
                any_sent = True
        fetched += len(chunk_ids)

    if any_sent:
        await _send_autodelete_notice(client, chat_id)
        
