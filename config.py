import os


BOT_TOKEN = os.environ["BOT_TOKEN"]
TELEGRAM_BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/"
OFFSET_FILE = "/tmp/uds_telegrambot_offset"
