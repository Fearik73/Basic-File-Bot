import asyncio
import logging

from pymongo import MongoClient

from config import (
    MONGO_URI, MONGO_DB_NAME, SHORT_URL, SHORT_API, SHORT_TUT,
    USERS_COLLECTION, FSUB_COLLECTION, REQUEST_COLLECTION, SETTINGS_COLLECTION,
)

logger = logging.getLogger(__name__)

client = MongoClient(MONGO_URI)
db = client[MONGO_DB_NAME]
users = db[USERS_COLLECTION]
fsub_channels = db[FSUB_COLLECTION]

try:
    client.admin.command("ping")
    logger.info("Connected to MongoDB db=%s", MONGO_DB_NAME)
except Exception:
    logger.exception("Could not reach MongoDB — check MONGO_URI/network access")


def _add_user_sync(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {
            "username": username,
            "name": f"{first_name} {last_name}",
            "source": None,
        }},
        upsert=True,
    )


def _del_user_sync(user_id: int):
    users.delete_one({"_id": user_id})


def _full_userbase_sync() -> list:
    return [doc["_id"] for doc in users.find()]


def _userbase_range_sync(start: int, count: int) -> list:
    cursor = users.find({}, {"_id": 1}).skip(start - 1).limit(count)
    return [doc["_id"] for doc in cursor]


def _total_users_sync() -> int:
    return users.count_documents({})


async def add_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    await asyncio.to_thread(_add_user_sync, user_id, username, first_name, last_name)


async def del_user(user_id: int):
    await asyncio.to_thread(_del_user_sync, user_id)


async def full_userbase() -> list:
    return await asyncio.to_thread(_full_userbase_sync)


async def full_userbase_range(start: int, count: int) -> list:
    return await asyncio.to_thread(_userbase_range_sync, start, count)


async def total_users() -> int:
    return await asyncio.to_thread(_total_users_sync)


def _add_fsub_channel_sync(channel_id: int, data: dict):
    fsub_channels.update_one({"_id": channel_id}, {"$set": data}, upsert=True)


def _get_all_fsub_channels_sync() -> dict:
    return {doc["_id"]: doc for doc in fsub_channels.find()}


async def add_fsub_channel(channel_id: int, data: dict):
    await asyncio.to_thread(_add_fsub_channel_sync, channel_id, data)


async def get_all_fsub_channels() -> dict:
    return await asyncio.to_thread(_get_all_fsub_channels_sync)


def _remove_fsub_channel_sync(channel_id: int):
    fsub_channels.delete_one({"_id": channel_id})


async def remove_fsub_channel(channel_id: int):
    await asyncio.to_thread(_remove_fsub_channel_sync, channel_id)



join_requests = db[REQUEST_COLLECTION]


def _add_join_request_sync(channel_id: int, user_id: int):
    join_requests.update_one(
        {"_id": f"{channel_id}:{user_id}"},
        {"$set": {"channel_id": channel_id, "user_id": user_id}},
        upsert=True,
    )


def _has_join_request_sync(channel_id: int, user_id: int) -> bool:
    return join_requests.find_one({"_id": f"{channel_id}:{user_id}"}) is not None


async def add_join_request(channel_id: int, user_id: int):
    await asyncio.to_thread(_add_join_request_sync, channel_id, user_id)


async def has_join_request(channel_id: int, user_id: int) -> bool:
    return await asyncio.to_thread(_has_join_request_sync, channel_id, user_id)


bot_settings = db[SETTINGS_COLLECTION]


def _get_settings_sync() -> dict:
    doc = bot_settings.find_one({"_id": "settings"}) or {}
    return {
        "protect_content": doc.get("protect_content", False),
        "auto_delete": doc.get("auto_delete", 0),
        "shortner_enabled": doc.get("shortner_enabled", False),
        "short_url": doc.get("short_url", SHORT_URL),
        "short_api": doc.get("short_api", SHORT_API),
        "tutorial_link": doc.get("tutorial_link", SHORT_TUT),
    }


def _update_settings_sync(data: dict):
    bot_settings.update_one({"_id": "settings"}, {"$set": data}, upsert=True)


async def get_settings() -> dict:
    return await asyncio.to_thread(_get_settings_sync)


async def update_settings(data: dict):
    await asyncio.to_thread(_update_settings_sync, data)

