import asyncio
import html
import json
import logging
import time

from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from config import ADMINS
from database import import_users_batch, total_users

logger = logging.getLogger(__name__)

BATCH_SIZE = 1000
EDIT_INTERVAL = 3
MAX_LOG_LINES = 14

_running = False


def clean_ids(data) -> tuple:
    """Returns (valid_ids, channel_or_invalid_count, duplicate_count)."""
    valid = []
    bad = 0
    for x in data:
        if isinstance(x, bool):
            bad += 1
            continue
        if isinstance(x, str) and x.strip().lstrip("-").isdigit():
            x = int(x.strip())
        if not isinstance(x, int) or x <= 0:
            bad += 1
            continue
        valid.append(x)
    unique = list(dict.fromkeys(valid))
    return unique, bad, len(valid) - len(unique)


class LiveLog:
    def __init__(self, msg: Message):
        self.msg = msg
        self.lines = []
        self.footer = ""
        self.last_edit = 0.0

    def _render(self) -> str:
        body = "\n".join(self.lines[-MAX_LOG_LINES:])
        if self.footer:
            body += "\n\n" + self.footer
        return f"<pre>{html.escape(body)}</pre>"

    async def push(self, line: str = None, footer: str = None, force: bool = False):
        if line:
            self.lines.append(f"[{time.strftime('%H:%M:%S')}] {line}")
        if footer is not None:
            self.footer = footer
        now = time.time()
        if not force and now - self.last_edit < EDIT_INTERVAL:
            return
        self.last_edit = now
        try:
            await self.msg.edit_text(self._render())
        except FloodWait as e:
            await asyncio.sleep(e.value)
        except Exception:
            pass


@Client.on_message(filters.command("updl") & filters.private)
async def updl_import(client: Client, message: Message):
    global _running
    if message.from_user.id not in ADMINS:
        return

    doc = message.document or (message.reply_to_message.document if message.reply_to_message else None)
    if not doc:
        return await message.reply(
            "<b>Send userdata.json with caption</b> <code>/updl</code> <b>or reply to it with</b> <code>/updl</code>"
        )
    if _running:
        return await message.reply("<b>⚠️ Ek import pehle se chal raha ha, wait karo.</b>")

    _running = True
    started = time.time()
    log = LiveLog(await message.reply("<pre>Starting...</pre>"))
    try:
        await log.push(f"Downloading {doc.file_name or 'file'}...", force=True)
        buf = await client.download_media(doc, in_memory=True)
        raw = bytes(buf.getbuffer())
        await log.push(f"Downloaded {len(raw) / 1024:.1f} KB", force=True)

        await log.push("Parsing JSON...", force=True)
        data = await asyncio.to_thread(json.loads, raw.decode("utf-8"))
        if not isinstance(data, list):
            raise ValueError("JSON must be a list of user IDs")
        await log.push(f"Found {len(data)} entries", force=True)

        ids, bad, dups = await asyncio.to_thread(clean_ids, data)
        await log.push(f"Removed {bad} channel/invalid IDs", force=True)
        await log.push(f"Removed {dups} duplicate IDs in file", force=True)
        total = len(ids)
        if not total:
            raise ValueError("No valid user IDs found")
        batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
        await log.push(f"Importing {total} users ({batches} batches of {BATCH_SIZE})", force=True)

        added = skipped = failed = done = 0
        for n in range(batches):
            batch = ids[n * BATCH_SIZE:(n + 1) * BATCH_SIZE]
            try:
                ins, skp = await import_users_batch(batch)
                added += ins
                skipped += skp
                line = f"Batch {n + 1}/{batches} | +{ins} new | {skp} already exist"
            except Exception as e:
                failed += len(batch)
                logger.exception("updl batch %s failed", n + 1)
                line = f"Batch {n + 1}/{batches} FAILED: {str(e)[:60]}"
            done += len(batch)
            speed = done / max(time.time() - started, 0.1)
            footer = (
                f"Processed: {done}/{total} ({done * 100 // total}%)\n"
                f"Added: {added} | Skipped: {skipped} | Failed: {failed}\n"
                f"Speed: {speed:.0f} ids/s"
            )
            await log.push(line, footer=footer)

        await log.push("Done ✅", force=True)
        users_now = await total_users()
        summary = (
            f"\n<b>✅ ɪᴍᴘᴏʀᴛ ᴄᴏᴍᴘʟᴇᴛᴇᴅ</b>\n"
            f"<b>ᴀᴅᴅᴇᴅ :</b> {added}\n"
            f"<b>ꜱᴋɪᴘᴘᴇᴅ (ᴅᴜᴘʟɪᴄᴀᴛᴇ) :</b> {skipped}\n"
            f"<b>ꜰᴀɪʟᴇᴅ :</b> {failed}\n"
            f"<b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ ɴᴏᴡ :</b> {users_now}\n"
            f"<b>ᴛɪᴍᴇ :</b> {time.time() - started:.1f}s"
        )
        try:
            await log.msg.edit_text(log._render() + summary)
        except Exception:
            await message.reply(summary)
    except Exception as e:
        logger.exception("Error in /updl")
        await log.push(f"ERROR: {e}", force=True)
    finally:
        _running = False
