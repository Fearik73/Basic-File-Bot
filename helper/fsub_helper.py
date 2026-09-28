import asyncio
import logging
from datetime import datetime, timedelta

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant

from config import FSUB_MESSAGE, FSUB_PHOTO
from database import add_fsub_channel, get_all_fsub_channels, remove_fsub_channel, has_join_request
from helper.styling import styled_button, send_styled, safe_reply

logger = logging.getLogger(__name__)


async def check_subscription(client: Client, user_id: int) -> dict:
    statuses = {}
    for channel_id, data in client.fsub_dict.items():
        if data.get("request"):
            try:
                if await has_join_request(channel_id, user_id):
                    statuses[channel_id] = True
                    continue
            except Exception:
                logger.exception("Error checking join-request record for channel_id=%s", channel_id)

        try:
            member = await client.get_chat_member(channel_id, user_id)
            statuses[channel_id] = member.status in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            )
        except UserNotParticipant:
            statuses[channel_id] = False
        except Exception:
            logger.exception("Error checking fsub status for channel_id=%s", channel_id)
            statuses[channel_id] = True
    return statuses


_fsub_load_lock = asyncio.Lock()


async def ensure_fsub_loaded(client: Client):
    if getattr(client, "_fsub_loaded", False):
        return
    async with _fsub_load_lock:
        if getattr(client, "_fsub_loaded", False):
            return
        try:
            client.fsub_dict = await get_all_fsub_channels()
            logger.info("Loaded %d Fsub channel(s)", len(client.fsub_dict))
        except Exception:
            logger.exception("Failed to load Fsub channels from MongoDB")
        client._fsub_loaded = True


def force_sub(func):
    async def wrapper(client: Client, message: Message):
        await ensure_fsub_loaded(client)
        if not client.fsub_dict:
            return await func(client, message)

        checking_msg = await safe_reply(message, "<b>Checking Subscription.....</b>")

        raw_payload = message.command[1] if len(message.command) > 1 else None

        is_retry = False
        original_payload = raw_payload
        if raw_payload == "retry":
            is_retry = True
            original_payload = None
        elif raw_payload and raw_payload.startswith("retry_"):
            is_retry = True
            original_payload = raw_payload[len("retry_"):]

        is_file_request = bool(original_payload) and original_payload.lower().startswith(("single_", "batch_"))
        consider_fake = is_file_request and not is_retry

        user_id = message.from_user.id
        statuses = await check_subscription(client, user_id)

        real_statuses = [statuses.get(cid, False) for cid, data in client.fsub_dict.items() if not data.get("fake")]
        fake_statuses = [statuses.get(cid, False) for cid, data in client.fsub_dict.items() if data.get("fake")]

        if all(real_statuses) and (not consider_fake or all(fake_statuses)):
            try:
                await checking_msg.delete()
            except Exception:
                pass
            if is_retry:
                message.command = [message.command[0], original_payload] if original_payload else [message.command[0]]
            return await func(client, message)

        buttons_raw = []
        idx = 0

        for channel_id, data in client.fsub_dict.items():
            if data.get("fake") and not consider_fake:
                continue

            joined = statuses.get(channel_id, False)
            if joined:
                continue

            link = data.get("link")
            if data.get("timer", 0) > 0:
                try:
                    invite = await client.create_chat_invite_link(
                        channel_id,
                        expire_date=datetime.now() + timedelta(minutes=data["timer"]),
                        creates_join_request=data.get("request", False),
                    )
                    link = invite.invite_link
                except Exception:
                    logger.exception("Error creating invite link for channel_id=%s", channel_id)

            idx += 1
            buttons_raw.append({"text": f"Channel {idx:02d}", "url": link, "style": "primary"})

        try_again_payload = f"retry_{original_payload}" if original_payload else "retry"
        try_again_link = f"https://t.me/{client.me.username}?start={try_again_payload}"
        buttons_raw.append({"text": "Try Again", "url": try_again_link, "style": "danger"})

        rows = [buttons_raw[i:i + 2] for i in range(0, len(buttons_raw), 2)]
        markup = InlineKeyboardMarkup(
            [[styled_button(b["text"], url=b["url"], style=b["style"]) for b in row] for row in rows]
        )

        try:
            await checking_msg.delete()
        except Exception:
            pass

        await send_styled(
            client,
            message.chat.id,
            FSUB_MESSAGE,
            reply_markup=markup,
            photo=FSUB_PHOTO or None,
        )

    return wrapper


async def process_fsub_add(client: Client, args: list) -> str:
    if not args:
        return "<b>Invalid format</b>"

    fake = args[-1].lower() == "x"
    if fake:
        args = args[:-1]
    if len(args) != 3:
        return "<b>Invalid format</b>"

    channel_id_raw, mode_raw, timer_raw = args

    try:
        channel_id = int(channel_id_raw)
    except ValueError:
        return "<b>Invalid channel ID</b>"

    mode = mode_raw.lower()
    if mode == "yes":
        request = True
    elif mode == "no":
        request = False
    else:
        return "<b>Mode must be 'yes' or 'no'</b>"

    if not timer_raw.isdigit():
        return "<b>Timer must be a non-negative integer</b>"
    timer = int(timer_raw)

    try:
        chat, member = await asyncio.gather(
            client.get_chat(channel_id),
            client.get_chat_member(channel_id, "me"),
        )
    except Exception as e:
        return f"<b>Error:</b> <code>{e}</code>"

    if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
        return "<b>I must be an admin in that channel first</b>"

    link = None
    if timer == 0:
        try:
            invite = await client.create_chat_invite_link(channel_id, creates_join_request=request)
            link = invite.invite_link
        except Exception as e:
            return f"<b>Error creating invite link:</b> <code>{e}</code>"

    data = {"name": chat.title, "link": link, "request": request, "timer": timer, "fake": fake}

    try:
        await add_fsub_channel(channel_id, data)
    except Exception:
        logger.exception("Failed to save fsub channel_id=%s to MongoDB", channel_id)

    client.fsub_dict[channel_id] = data

    return (
        "<b>✅ ꜰᴏʀᴄᴇ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ ᴀᴅᴅᴇᴅ</b>\n\n"
        f"<b>ᴄʜᴀɴɴᴇʟ:</b> {chat.title}\n"
        f"<b>ɪᴅ:</b> <code>{channel_id}</code>\n"
        f"<b>ᴍᴏᴅᴇ:</b> {'Request' if request else 'Direct'}\n"
        f"<b>ᴇxᴘɪʀʏ:</b> {f'{timer}m' if timer > 0 else 'Never'}\n\n"
        + ("<b>❗ᴀᴅᴅᴇᴅ ᴛʜɪꜱ ᴄʜᴀɴɴᴇʟ ɪɴᴛᴏ ꜰᴀᴋᴇ ꜰ-ꜱᴜʙ ʟɪꜱᴛ</b>" if fake else "")
    )


async def process_fsub_remove(client: Client, channel_id_raw: str) -> str:
    try:
        channel_id = int(channel_id_raw.strip())
    except ValueError:
        return "<b>Invalid channel ID</b>"

    if channel_id not in client.fsub_dict:
        return "<b>This channel isn't in the Force-Sub list</b>"

    name = client.fsub_dict[channel_id].get("name", str(channel_id))

    try:
        await remove_fsub_channel(channel_id)
    except Exception:
        logger.exception("Failed to remove fsub channel_id=%s from MongoDB", channel_id)

    client.fsub_dict.pop(channel_id, None)

    return (
        "<b>✅ ꜰ-ꜱᴜʙ ᴄʜᴀɴɴᴇʟ ʀᴇᴍᴏᴠᴇᴅ</b>\n\n"
        f"<b>ᴄʜᴀɴɴᴇʟ:</b> {name}\n"
        f"<b>ɪᴅ:</b> <code>{channel_id}</code>"
    )
    
