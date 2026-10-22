import logging

import aiohttp
from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pyrogram.errors import UserIsBlocked, InputUserDeactivated, PeerIdInvalid, UserDeactivated, UserDeactivatedBan

from config import BOT_TOKEN

logger = logging.getLogger(__name__)


def styled_button(text: str, callback_data: str = None, url: str = None, style: str = None) -> InlineKeyboardButton:
    btn = InlineKeyboardButton(text, callback_data=callback_data, url=url)
    if style:
        btn.style = style
    return btn


async def _http_session(client: Client) -> aiohttp.ClientSession:
    session = getattr(client, "_raw_http_session", None)
    if session is None or session.closed:
        session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        client._raw_http_session = session
    return session


def _keyboard_to_raw(markup: InlineKeyboardMarkup):
    if markup is None:
        return None
    rows = []
    for row in markup.inline_keyboard:
        raw_row = []
        for btn in row:
            b = {"text": btn.text}
            if getattr(btn, "callback_data", None):
                b["callback_data"] = btn.callback_data
            if getattr(btn, "url", None):
                b["url"] = btn.url
            style = getattr(btn, "style", None)
            if style:
                b["style"] = style
            raw_row.append(b)
        rows.append(raw_row)
    return rows


def _has_style(markup: InlineKeyboardMarkup) -> bool:
    if markup is None:
        return False
    return any(getattr(btn, "style", None) for row in markup.inline_keyboard for btn in row)


async def send_styled(client: Client, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup = None,
                       photo: str = None, message_effect_id: int = None):
    if not _has_style(reply_markup):
        kwargs = {"reply_markup": reply_markup}
        if message_effect_id:
            kwargs["message_effect_id"] = message_effect_id
        if photo:
            return await client.send_photo(chat_id, photo, caption=text, **kwargs)
        return await client.send_message(chat_id, text, **kwargs)

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    payload = {"chat_id": chat_id, "parse_mode": "HTML"}
    buttons_raw = _keyboard_to_raw(reply_markup)
    if buttons_raw:
        payload["reply_markup"] = {"inline_keyboard": buttons_raw}
    if message_effect_id:
        payload["message_effect_id"] = message_effect_id

    if photo:
        url = f"{base_url}/sendPhoto"
        payload["photo"] = photo
        payload["caption"] = text
    else:
        url = f"{base_url}/sendMessage"
        payload["text"] = text

    try:
        session = await _http_session(client)
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if data.get("ok"):
                return data.get("result")
            logger.warning("Raw Bot API send failed: %s", data)
    except Exception:
        logger.exception("Error sending raw styled message")

    kwargs = {"reply_markup": reply_markup}
    if message_effect_id:
        kwargs["message_effect_id"] = message_effect_id
    if photo:
        return await client.send_photo(chat_id, photo, caption=text, **kwargs)
    return await client.send_message(chat_id, text, **kwargs)


async def edit_styled(client: Client, message: Message, text: str, reply_markup: InlineKeyboardMarkup = None):
    is_media = bool(message.photo or message.video or message.document)
    if not _has_style(reply_markup):
        if is_media:
            return await message.edit_caption(text, reply_markup=reply_markup)
        return await message.edit_text(text, reply_markup=reply_markup)

    base_url = f"https://api.telegram.org/bot{BOT_TOKEN}"
    payload = {"chat_id": message.chat.id, "message_id": message.id, "parse_mode": "HTML"}
    buttons_raw = _keyboard_to_raw(reply_markup)
    if buttons_raw:
        payload["reply_markup"] = {"inline_keyboard": buttons_raw}

    if is_media:
        url = f"{base_url}/editMessageCaption"
        payload["caption"] = text
    else:
        url = f"{base_url}/editMessageText"
        payload["text"] = text

    try:
        session = await _http_session(client)
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            if data.get("ok"):
                return
            logger.warning("Raw Bot API edit failed: %s", data)
    except Exception:
        logger.exception("Error editing raw styled message")

    if is_media:
        await message.edit_caption(text, reply_markup=reply_markup)
    else:
        await message.edit_text(text, reply_markup=reply_markup)

_UNREACHABLE = (UserIsBlocked, InputUserDeactivated, UserDeactivated, UserDeactivatedBan, PeerIdInvalid)


async def safe_reply(message: Message, text: str):
    """Reply; returns None if the user blocked the bot / is deleted."""
    try:
        return await message.reply(text)
    except _UNREACHABLE:
        return None
    except Exception:
        logger.exception("reply with parse_mode failed, retrying as plain text")
        try:
            return await message.reply(text, parse_mode=ParseMode.DISABLED)
        except _UNREACHABLE:
            return None
