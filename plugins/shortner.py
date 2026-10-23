import logging
import random
import string

import aiohttp
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from config import ADMINS
from database import update_settings
from helper.messaging import edit_msg
from helper.settings_store import ensure_settings_loaded

logger = logging.getLogger(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}



_shortened_urls_cache = {}


def _generate_alias() -> str:
    characters = string.ascii_letters + string.digits
    return "".join(random.choice(characters) for _ in range(8))


async def get_short(url: str, client: Client) -> str:
    await ensure_settings_loaded(client)
    settings = client.settings

    if not settings.get("shortner_enabled", False):
        return url

    short_url = settings.get("short_url", "")
    short_api = settings.get("short_api", "")
    if not short_url or not short_api:
        return url

    cache_key = f"{short_url}|{short_api}|{url}"
    if cache_key in _shortened_urls_cache:
        return _shortened_urls_cache[cache_key]

    try:
        alias = _generate_alias()
        api_url = f"https://{short_url}/api?api={short_api}&url={url}&alias={alias}"
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, headers=HEADERS, timeout=10) as response:
                try:
                    rjson = await response.json(content_type=None)
                except ValueError:
                    logger.warning("Shortener returned non-JSON response (status %s)", response.status)
                    return url

                if response.status == 200 and rjson.get("status") == "success":
                    result = rjson.get("shortenedUrl", url)
                    _shortened_urls_cache[cache_key] = result
                    return result
                logger.warning("Shortener API responded but not success: %s", rjson)
    except Exception:
        logger.exception("Error while shortening url=%s", url)

    return url


def build_shortner_panel(client: Client):
    settings = client.settings
    enabled = settings.get("shortner_enabled", False)
    short_url = settings.get("short_url", "") or "Not set"
    short_api = settings.get("short_api", "") or "Not set"
    tutorial_link = settings.get("tutorial_link", "") or "Not set"

    enabled_text = "ᴇɴᴀʙʟᴇᴅ" if enabled else "ᴅɪꜱᴀʙʟᴇᴅ"
    toggle_label = "ᴏꜰꜰ" if enabled else "ᴏɴ"

    text = (
        "<b>➲ <u>ꜱʜᴏʀᴛɴᴇʀ ꜱᴇᴛᴛɪɴɢꜱ</u></b>\n"
        "──────────────────\n"
        f"<blockquote><b>▸ ꜱᴛᴀᴛᴜꜱ:</b> {enabled_text}\n"
        f"<b>▸ ꜱʜᴏʀᴛɴᴇʀ ᴜʀʟ:</b> {short_url}\n"
        f"<b>▸ ꜱʜᴏʀᴛɴᴇʀ ᴀᴘɪ:</b> {short_api}\n"
        f"<b>▸ ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ:</b> {tutorial_link}</blockquote>"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{toggle_label} ꜱʜᴏʀᴛɴᴇʀ", callback_data="set_shortner_toggle"),
            InlineKeyboardButton("ꜱᴇᴛ ᴜʀʟ/ᴀᴘɪ", callback_data="set_shortner_seturl"),
        ],
        [
            InlineKeyboardButton("ꜱᴇᴛ ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ", callback_data="set_shortner_tutorial"),
            InlineKeyboardButton("ᴛᴇꜱᴛ ꜱʜᴏʀᴛɴᴇʀ", callback_data="set_shortner_test"),
        ],
        [InlineKeyboardButton("◂ ʙᴀᴄᴋ", callback_data="set_menu_main")],
    ])
    return text, markup


@Client.on_callback_query(filters.regex("^set_menu_shortner$"))
async def settings_menu_shortner(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)
    text, markup = build_shortner_panel(client)
    await edit_msg(client, query.message, text, reply_markup=markup)
    await query.answer()


@Client.on_callback_query(filters.regex("^set_shortner_toggle$"))
async def settings_shortner_toggle(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)
    value = not client.settings.get("shortner_enabled", False)
    client.settings["shortner_enabled"] = value
    try:
        await update_settings({"shortner_enabled": value})
    except Exception:
        logger.exception("Failed to persist shortner_enabled setting")

    text, markup = build_shortner_panel(client)
    await edit_msg(client, query.message, text, reply_markup=markup)
    await query.answer(f"Shortener {'enabled' if value else 'disabled'}")


@Client.on_callback_query(filters.regex("^set_shortner_seturl$"))
async def settings_shortner_seturl(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)

    from plugins.settings import _wait_for_reply

    await edit_msg(
        client,
        query.message,
        "<b>➲ ꜱᴇᴛ ꜱʜᴏʀᴛɴᴇʀ ᴜʀʟ/ᴀᴘɪ</b>\n\n"
        "<i>_ꜱᴇɴᴅ ᴛʜᴇ ɴᴇᴡ ᴜʀʟ ᴀɴᴅ ᴀᴘɪ ᴋᴇʏ ɪɴ ᴛʜɪꜱ ꜰᴏʀᴍᴀᴛ, ᴡᴀɪᴛ ꜰᴏʀ 60 ꜱᴇᴄᴏɴᴅ ᴛɪᴍᴇᴏᴜᴛ_</i>\n\n"
        "<b>ꜰᴏʀᴍᴀᴛ:</b> url api\n"
        "<b>ᴇxᴀᴍᴘʟᴇ:</b> inshorturl.com 9435xxxxxxxxxxxxxxxx",
    )
    await query.answer()

    reply_text = await _wait_for_reply(query.message.chat.id, query.from_user.id, timeout=60)

    if reply_text is None:
        text = "<b>⚠️ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ɴᴏ ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ ꜰʀᴏᴍ ᴜꜱᴇʀ!_</i>"
    else:
        parts = reply_text.strip().split()
        if len(parts) >= 2:
            new_url = parts[0].replace("https://", "").replace("http://", "").replace("/", "")
            new_api = " ".join(parts[1:])
            if new_url and "." in new_url and new_api:
                client.settings["short_url"] = new_url
                client.settings["short_api"] = new_api
                _shortened_urls_cache.clear()
                try:
                    await update_settings({"short_url": new_url, "short_api": new_api})
                except Exception:
                    logger.exception("Failed to persist shortener url/api settings")
                text = f"<b>ꜱʜᴏʀᴛɴᴇʀ ᴜᴘᴅᴀᴛᴇᴅ!</b>\n\n<b>ᴜʀʟ:</b> `{new_url}`\n<b>ᴀᴘɪ:</b> `{new_api[:20]}...`"
            else:
                text = "<b>ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ! ᴄʜᴇᴄᴋ ᴜʀʟ ᴀɴᴅ ᴀᴘɪ ᴋᴇʏ.</b>"
        else:
            text = "<b>ɪɴᴠᴀʟɪᴅ ꜰᴏʀᴍᴀᴛ! ᴜꜱᴇ:</b> url api"

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("◂ ʙᴀᴄᴋ", callback_data="set_menu_shortner")]])
    await edit_msg(client, query.message, text, reply_markup=markup)


@Client.on_callback_query(filters.regex("^set_shortner_tutorial$"))
async def settings_shortner_tutorial(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)

    from plugins.settings import _wait_for_reply

    await edit_msg(
        client,
        query.message,
        "<b>➲ ꜱᴇᴛ ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ</b>\n\n"
        "<i>_ꜱᴇɴᴅ ᴛʜᴇ ɴᴇᴡ ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ, ᴡᴀɪᴛ ꜰᴏʀ 60 ꜱᴇᴄᴏɴᴅ ᴛɪᴍᴇᴏᴜᴛ_</i>\n\n"
        "<b>ᴇxᴀᴍᴘʟᴇ:</b> https://t.me/How_to_Download_9999999",
    )
    await query.answer()

    reply_text = await _wait_for_reply(query.message.chat.id, query.from_user.id, timeout=60)

    if reply_text is None:
        text = "<b>⚠️ ᴛɪᴍᴇᴅ ᴏᴜᴛ</b>\n\n<i>_ɴᴏ ᴅᴀᴛᴀ ʀᴇᴄᴇɪᴠᴇᴅ ꜰʀᴏᴍ ᴜꜱᴇʀ!_</i>"
    else:
        new_link = reply_text.strip()
        if new_link.startswith("https://") or new_link.startswith("http://"):
            client.settings["tutorial_link"] = new_link
            try:
                await update_settings({"tutorial_link": new_link})
            except Exception:
                logger.exception("Failed to persist tutorial_link setting")
            text = "<b>ᴛᴜᴛᴏʀɪᴀʟ ʟɪɴᴋ ᴜᴘᴅᴀᴛᴇᴅ!</b>"
        else:
            text = "<b>ɪɴᴠᴀʟɪᴅ ʟɪɴᴋ! ᴍᴜꜱᴛ ꜱᴛᴀʀᴛ ᴡɪᴛʜ https:// ᴏʀ http://</b>"

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("◂ ʙᴀᴄᴋ", callback_data="set_menu_shortner")]])
    await edit_msg(client, query.message, text, reply_markup=markup)


@Client.on_callback_query(filters.regex("^set_shortner_test$"))
async def settings_shortner_test(client: Client, query: CallbackQuery):
    if query.from_user.id not in ADMINS:
        return await query.answer("Not authorized", show_alert=True)
    await ensure_settings_loaded(client)
    await query.answer()

    await edit_msg(client, query.message, "<b>🔄 ᴛᴇꜱᴛɪɴɢ ꜱʜᴏʀᴛɴᴇʀ...</b>")

    short_url = client.settings.get("short_url", "")
    short_api = client.settings.get("short_api", "")

    if not short_url or not short_api:
        text = "<b>❌ ꜱʜᴏʀᴛɴᴇʀ ᴜʀʟ/ᴀᴘɪ ɴᴏᴛ ꜱᴇᴛ ʏᴇᴛ!</b>"
    else:
        try:
            alias = _generate_alias()
            api_url = f"https://{short_url}/api?api={short_api}&url=https://google.com&alias={alias}"
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, headers=HEADERS, timeout=10) as response:
                    rjson = await response.json(content_type=None)
                    if response.status == 200 and rjson.get("status") == "success":
                        text = (
                            "<b>✅ ꜱʜᴏʀᴛɴᴇʀ ᴛᴇꜱᴛ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟ!</b>\n\n"
                            f"<b>ꜱʜᴏʀᴛ ᴜʀʟ:</b> `{rjson.get('shortenedUrl', '')}`"
                        )
                    else:
                        text = (
                            "<b>❌ Shortner Test Failed!</b>\n\n"
                            f"<b>ᴇʀʀᴏʀ:</b> {rjson.get('message', 'Unknown error')}"
                        )
        except Exception as e:
            text = f"<b>❌ Shortner Test Failed</b>\n\n<b>Error:</b> {e}"

    markup = InlineKeyboardMarkup([[InlineKeyboardButton("◂ ʙᴀᴄᴋ", callback_data="set_menu_shortner")]])
    await edit_msg(client, query.message, text, reply_markup=markup)
            
