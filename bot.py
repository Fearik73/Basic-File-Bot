import logging
import time

import pyrogram.utils
from pyrogram import Client, idle
from pyrogram.enums import ParseMode

from config import API_ID, API_HASH, BOT_TOKEN, CLIENT_NAME, WORKERS

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)
logging.getLogger("pyrogram").setLevel(logging.WARNING)

app = Client(
    CLIENT_NAME,
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workers=WORKERS,
    parse_mode=ParseMode.HTML,
    plugins=dict(root="plugins"),
)
app.fsub_dict = {}
app.flink_dict = {}
app.settings = {"protect_content": False, "auto_delete": 0}
app.start_time = time.time()


async def main():
    await app.start()
    me = await app.get_me()
    logger.info("✅ Bot started successfully — running as @%s", me.username)
    await idle()
    await app.stop()


if __name__ == "__main__":
    app.run(main())

