#!/usr/bin/env python
import time
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
            logger.info("Processing %s from %s in chat %s", text, from_id, chat_id)
            dispatcher = Dispatcher(session=session)
            try:
                dispatcher.dispatch(text, chat_id, from_id)
            except Exception as e:
                send_message(
                    session, chat_id, "Failed, error: {} {}".format(type(e), e)
                )

            with open(config.OFFSET_FILE, "w") as f:
                f.write(str(update_id))


if __name__ == "__main__":
    logger.info("Bot is starting")
    while True:
        with requests.Session() as S:
            fetch_message_and_process(session=S)
            dispatcher = Dispatcher(session=S)
            cronjob.run_cron(dispatcher.dispatch)
            time.sleep(60)
