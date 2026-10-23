import asyncio
import logging
import os
import sys

from pyrogram import Client, filters
from pyrogram.types import Message

from config import ADMINS
from helper.messaging import safe_reply

logger = logging.getLogger(__name__)

RESTART_FILE = "restart.txt"


@Client.on_message(filters.command("restart") & filters.private)
async def restart_handler(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    notice = await safe_reply(message, "<b>Restarting...</b>")
    try:
        with open(RESTART_FILE, "w") as f:
            f.write(f"{message.chat.id} {notice.id if notice else 0}")
    except Exception:
        logger.exception("Failed to write restart marker")
    await asyncio.sleep(1)
    os.execl(sys.executable, sys.executable, *sys.argv)


async def notify_restart(client: Client):
    if not os.path.exists(RESTART_FILE):
        return
    try:
        with open(RESTART_FILE) as f:
            chat_id, msg_id = map(int, f.read().split())
        os.remove(RESTART_FILE)
        if msg_id:
            try:
                await client.delete_messages(chat_id, msg_id)
            except Exception:
                pass
        await client.send_message(chat_id, "<b>Bot restarted Successfully</b>")
    except Exception:
        logger.exception("Failed to send restart notification")
