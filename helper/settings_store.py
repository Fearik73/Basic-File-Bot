import logging

from pyrogram import Client

from database import get_settings

logger = logging.getLogger(__name__)


async def ensure_settings_loaded(client: Client):
    if getattr(client, "_settings_loaded", False):
        return
    try:
        client.settings = await get_settings()
    except Exception:
        logger.exception("Failed to load settings from MongoDB")
    client._settings_loaded = True
