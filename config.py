import os

from dotenv import load_dotenv

load_dotenv("config.env")

MESSAGE_EFFECT_ID = 5104841245755180586
BROADCAST_EFFECT_ID = 5046509860389126442

API_ID = int(os.environ.get("API_ID", ""))
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")

DB_CHANNEL_ID = int(os.environ.get("DB_CHANNEL_ID", ""))

MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "")
MONGO_URI = os.environ.get("MONGO_URI", "")

USERS_COLLECTION = os.environ.get("USERS_COLLECTION", "users")
FSUB_COLLECTION = os.environ.get("FSUB_COLLECTION", "fsub")
REQUEST_COLLECTION = os.environ.get("REQUEST_COLLECTION", "req")
SETTINGS_COLLECTION = os.environ.get("SETTINGS_COLLECTION", "settings")


_admins_raw = os.environ.get("ADMINS", "7375326036")
ADMINS = [int(x.strip()) for x in _admins_raw.split(",") if x.strip()]


WORKERS = int(os.environ.get("WORKERS", "200"))

SEASON_NAME = os.environ.get("SEASON_NAME", "filebot")
CLIENT_NAME = SEASON_NAME

START_MESSAGE = os.environ.get(
    "START_MESSAGE",
    "<b>Hello Dear,\n\nI can store private files in Specified Channel and other users can access it from special link.\n\n<blockquote>Visit - @Od3ns_Animes</blockquote></b>",
)

FSUB_MESSAGE = os.environ.get(
    "FSUB_MESSAGE",
    "<b>⚠️ Subscription Required...</b>\n\nYou haven't joined the required channel(s) yet! Please join them to use me.",
)


START_IMAGE = os.environ.get("START_IMAGE", "")
FSUB_PHOTO = os.environ.get("FSUB_PHOTO", "")
SETTINGS_IMAGE = os.environ.get("SETTINGS_IMAGE", "https://files.catbox.moe/3yxex9.jpg")


SHORT_URL = os.environ.get("SHORT_URL", "")
SHORT_API = os.environ.get("SHORT_API", "")
SHORT_TUT = os.environ.get("SHORT_TUT", "")


START_BUTTONS = [
    {"label": "Ongoing Anime", "url": "http://t.me/Od3nsLinks_bot?start=18LTEwMDI2NzQyMDM5NTu9cVY="},
    {"label": "Finished Anime", "url": "http://t.me/Od3nsLinks_bot?start=16LTEwMDI2NjMwODUzH19vNzg="},
]
