import logging

from pyrogram import Client
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, UserIsBlocked, InputUserDeactivated, PeerIdInvalid, UserDeactivated, UserDeactivatedBan

logger = logging.getLogger(__name__)


def styled_button(text: str, callback_data: str = None, url: str = None) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=callback_data, url=url)


def _clean_markup(markup: InlineKeyboardMarkup):
    if markup is None:
        return None
    rows = []
    for row in markup.inline_keyboard:
        row = [b for b in row if getattr(b, "url", None) or getattr(b, "callback_data", None)]
        if row:
            rows.append(row)
    return InlineKeyboardMarkup(rows) if rows else None


async def send_styled(client: Client, chat_id: int, text: str, reply_markup: InlineKeyboardMarkup = None,
                       photo: str = None, message_effect_id: int = None):
    kwargs = {"reply_markup": _clean_markup(reply_markup)}
    if message_effect_id:
        kwargs["message_effect_id"] = message_effect_id
    if photo:
        return await client.send_photo(chat_id, photo, caption=text, **kwargs)
    return await client.send_message(chat_id, text, **kwargs)


async def edit_styled(client: Client, message: Message, text: str, reply_markup: InlineKeyboardMarkup = None):
    reply_markup = _clean_markup(reply_markup)
    is_media = bool(message.photo or message.video or message.document)
    try:
        if is_media:
            return await message.edit_caption(text, reply_markup=reply_markup)
        return await message.edit_text(text, reply_markup=reply_markup)
    except MessageNotModified:
        return None


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
            
