import io
import json
import logging

from pyrogram import Client, filters
from pyrogram.types import Message

from config import ADMINS
from database import full_userbase, total_users

logger = logging.getLogger(__name__)


@Client.on_message(filters.command("stats") & filters.private)
async def stats_export(client: Client, message: Message):
    if message.from_user.id not in ADMINS:
        return

    try:
        users_count = await total_users()

        if client.fsub_dict:
            channel_lines = []
            for index, (channel_id, data) in enumerate(client.fsub_dict.items(), start=1):
                name = data.get("name", "Unknown")
                mode = "ʀᴇQᴜᴇꜱᴛ" if data.get("request") else "ᴅɪʀᴇᴄᴛ"
                channel_lines.append(
                    f"{index}.\n<b>ɴᴀᴍᴇ</b> - {name}\n<b>ᴄʜᴀɴɴᴇʟ ɪᴅ</b> - <code>{channel_id}</code>\n<b>ᴍᴏᴅᴇ</b> - {mode}"
                )
            fsub_display = "\n\n".join(channel_lines)
        else:
            fsub_display = "ɴᴏ ꜰ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ"

        stats_text = (
            "<blockquote><b>➲ <u>ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ ꜰᴏʀ ʙᴏᴛ:</u></b>\n\n"
            f"ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ ɪɴ ʙᴏᴛ: {users_count}\n\n"
            "<b>➲ <u>ꜰ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ ɴᴀᴍᴇ &amp; ɪᴅ:</u></b>\n\n"
            f"{fsub_display}</blockquote>"
        )
        await message.reply_text(stats_text, disable_web_page_preview=True)

        export_notice = await message.reply("<b>Exporting userdata...</b>")

        user_ids = await full_userbase()
        json_bytes = json.dumps(user_ids, indent=2).encode("utf-8")
        file = io.BytesIO(json_bytes)
        file.name = "userdata.json"

        await client.send_document(
            chat_id=message.chat.id,
            document=file,
            file_name="userdata.json",
            caption=f"<b>ᴛᴏᴛᴀʟ ᴜꜱᴇʀꜱ</b> : {users_count}"
        )
        await export_notice.delete()
    except Exception as e:
        logger.exception("Error in /stats export")
        return await message.reply(f"✗ <b>Error:</b> <code>{e}</code>")
        
