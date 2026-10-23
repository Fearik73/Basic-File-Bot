import logging
import os

from pyrogram import Client, filters
from pyrogram.types import Message

from config import ADMINS
from helper.messaging import safe_reply

logger = logging.getLogger(__name__)

LOG_FILE = "log.txt"


@Client.on_message(filters.command("logs") & filters.private)
async def logs_handler(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        await safe_reply(message, "<b>No logs found</b>")
        return
    try:
        await message.reply_document(LOG_FILE)
    except Exception:
        logger.exception("Failed to send log file")
        await safe_reply(message, "<b>Failed to send logs</b>")
