import asyncio
import logging

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import BulkWriteError, DuplicateKeyError

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


counters = db["counters"]


def _reserve_uids_sync(n: int) -> int:
    """Reserve n sequential uids, returns the first one of the block."""
    if counters.find_one({"_id": "uid"}) is None:
        top = users.find_one({"uid": {"$exists": True}}, sort=[("uid", -1)])
        try:
            counters.update_one(
                {"_id": "uid"},
                {"$setOnInsert": {"seq": top["uid"] if top else 0}},
                upsert=True,
            )
        except DuplicateKeyError:
            pass
    doc = counters.find_one_and_update(
        {"_id": "uid"},
        {"$inc": {"seq": n}},
        return_document=ReturnDocument.AFTER,
    )
    return doc["seq"] - n + 1


def _add_user_sync(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    if users.find_one({"_id": user_id}, {"_id": 1}):
        return
    uid = _reserve_uids_sync(1)
    users.update_one(
        {"_id": user_id},
        {"$setOnInsert": {
            "username": username,
            "name": f"{first_name} {last_name}",
            "uid": uid,
            "source": None,
        }},
        upsert=True,
    )


def _import_users_batch_sync(ids: list) -> tuple:
    """Insert only new ids (with sequential uid). Returns (inserted, skipped)."""
    existing = {d["_id"] for d in users.find({"_id": {"$in": ids}}, {"_id": 1})}
    new_ids = [i for i in ids if i not in existing]
    if not new_ids:
        return 0, len(ids)
    start = _reserve_uids_sync(len(new_ids))
    docs = [
        {"_id": i, "username": None, "name": None, "uid": start + k, "source": None}
        for k, i in enumerate(new_ids)
    ]
    try:
        inserted = len(users.insert_many(docs, ordered=False).inserted_ids)
    except BulkWriteError as e:
        inserted = e.details.get("nInserted", 0)
    return inserted, len(ids) - inserted


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


async def import_users_batch(ids: list) -> tuple:
    return await asyncio.to_thread(_import_users_batch_sync, ids)


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
    return {doc["_id"]: doc for doc in fsub_channels.find({"type": {"$ne": "link"}})}


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


def _get_all_flinks_sync() -> dict:
    return {doc["_id"]: doc for doc in fsub_channels.find({"type": "link"}).sort("added_at", 1)}


def _add_flink_sync(link_id: str, data: dict):
    fsub_channels.update_one({"_id": link_id}, {"$set": data}, upsert=True)


def _remove_flink_sync(link_id: str):
    fsub_channels.delete_one({"_id": link_id})
    join_requests.delete_many({"channel_id": link_id})


def _has_flink_seen_sync(link_id: str, user_id: int) -> bool:
    return join_requests.find_one({"_id": f"{link_id}:{user_id}"}) is not None


def _mark_flink_seen_sync(link_id: str, user_id: int):
    join_requests.update_one(
        {"_id": f"{link_id}:{user_id}"},
        {"$set": {"channel_id": link_id, "user_id": user_id}},
        upsert=True,
    )


async def get_all_flinks() -> dict:
    return await asyncio.to_thread(_get_all_flinks_sync)


async def add_flink(link_id: str, data: dict):
    await asyncio.to_thread(_add_flink_sync, link_id, data)


async def remove_flink(link_id: str):
    await asyncio.to_thread(_remove_flink_sync, link_id)


async def has_flink_seen(link_id: str, user_id: int) -> bool:
    return await asyncio.to_thread(_has_flink_seen_sync, link_id, user_id)


async def mark_flink_seen(link_id: str, user_id: int):
    await asyncio.to_thread(_mark_flink_seen_sync, link_id, user_id)
    
