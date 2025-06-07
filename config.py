import os


BOT_TOKEN: str = os.environ["BOT_TOKEN"]
TELEGRAM_BASE_URL: str = f"https://api.telegram.org/bot{BOT_TOKEN}/"
OFFSET_FILE: str = "/tmp/uds_telegrambot_offset"
