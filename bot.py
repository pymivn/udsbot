#!/usr/bin/env python
import time
import traceback
import logging

import requests

import cronjob
import config
from commands import Dispatcher, send_message

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()


def fetch_message_and_process(session):
    try:
        with open(config.OFFSET_FILE) as f:
            offset = int(f.read().strip())
            params = {"offset": offset + 1}
    except IOError:
        params = None

    resp = session.get(config.TELEGRAM_BASE_URL + "getUpdates", json=params, timeout=20)
    d = resp.json()

    try:
        rs = d["result"]
    except KeyError:
        print(d)
        exit("Looks like a bad token")

    update_id = None
    for r in rs:
        update_id = r["update_id"]
        try:
            message = r["message"]
            timestamp = message["date"]
            # skip message older than 5 min
            if time.time() - timestamp > 5 * 60:
                continue
        except KeyError:
            continue
        if "text" in message:
            chat_id = r["message"]["chat"]["id"]
            from_id = r["message"]["from"]["id"]
            text = r["message"]["text"].strip()
            reply_to_message = message.get("reply_to_message")
            reply_text = (
                reply_to_message.get("text")
                if isinstance(reply_to_message, dict)
                else None
            )
            logger.info(
                "Processing %s from %s in chat %s (reply: %s)",
                text,
                from_id,
                chat_id,
                bool(reply_text),
            )
            dispatcher = Dispatcher(session=session)
            try:
                dispatcher.dispatch(text, chat_id, from_id, reply_text=reply_text)
            except Exception as e:
                send_message(
                    session,
                    chat_id,
                    "Failed, error: {} {}: tb: {}".format(
                        type(e), e, traceback.format_tb(e.__traceback__, limit=1)
                    ),
                )

            with open(config.OFFSET_FILE, "w") as f:
                f.write(str(update_id))


if __name__ == "__main__":
    logger.info("Bot is starting")
    try:
        import dict_lookup

        dict_lookup._ensure_databases()
    except Exception:
        logger.exception("Failed to initialize dictionary databases at startup")

    while True:
        with requests.Session() as S:
            fetch_message_and_process(session=S)
            dispatcher = Dispatcher(session=S)
            cronjob.run_cron(dispatcher.dispatch)
            time.sleep(60)
