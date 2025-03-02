#!/usr/bin/env python

import logging
import os
import json
import time
import datetime
import hashlib
import random

import requests
import uds
import jp_dict
import cronjob


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

OFFSET_FILE = "/tmp/uds_telegrambot_offset"
BOT_TOKEN = os.environ["BOT_TOKEN"]
# get temp token from https://openweathermap.org/
API_TEMP = os.environ["WEATHER_TOKEN"]
AOC_SESSION = os.environ.get("AOC_SESSION")

base = f"https://api.telegram.org/bot{BOT_TOKEN}/"

os.environ["TZ"] = "Asia/Ho_Chi_Minh"


dbpath = ":memory:"
db = jp_dict.init_kanji_db(dbpath)
kanji_service = jp_dict.KanjiService(db)


def aoc21(topn=10):
    cookies = {"session": AOC_SESSION}

    h = hashlib.sha256(AOC_SESSION.encode("utf-8")).hexdigest()
    datafile = f"/tmp/uds_aoc_{h}"

    d = {}
    timestamp = ""
    try:
        if os.stat(datafile).st_mtime > time.time() - 15 * 60:
            logger.info("AOC: Cache fresh, use it")

            timestamp = time.strftime(
                "%Y%m%d %H:%M", time.gmtime(os.stat(datafile).st_mtime)
            )

            with open(datafile) as f:
                d = json.load(f)
    except IOError:
        pass

    if not d:
        timestamp = datetime.datetime.now().strftime("%Y%m%d %H:%M")
        logger.info("AOC: Getting newest data")
        r = requests.get(
            "https://adventofcode.com/2024/leaderboard/private/view/416592.json",
            cookies=cookies,
        )
        d = r.json()
        with open(datafile, "wt") as f:
            json.dump(d, f)

    scoreboard = [
        (e["name"], e["local_score"], e["stars"])
        for e in sorted(
            d["members"].values(), key=lambda i: i["local_score"], reverse=True
        )
        if e["stars"] > 0
    ]

    lines = [
        f"{idx}. " + " ".join((str(p) for p in i))
        for idx, i in enumerate(scoreboard[:topn], start=1)
    ]

    return f"AoC PyMi At {timestamp}UTC - refresh each 15m\n" + "\n".join(lines)


def _get_coin_name(code):
    return dict(
        [
            ("btc", "bitcoin"),
            ("eth", "ethereum"),
            ("usdt", "tether"),
            ("bnb", "binancecoin"),
            ("ada", "cardano"),
            ("doge", "dogecoin"),
            ("sol", "solana"),
            ("xrm", "monero"),
            ("xrp", "xrp"),
            ("ltc", "litecoin"),
            ("link", "chainlink"),
            ("xlm", "stellar"),
        ]
    )[code]


def get_aqi_hanoi():
    resp = requests.get(
        "https://api.waqi.info/mapq/bounds/?bounds=20.96111901161895,105.75405120849611,21.09571147652958,105.91609954833986"
    )
    locs = resp.json()
    for i in locs:
        if "US Embassy" in i["city"]:
            us_embassy = i
            break
    return us_embassy["city"], us_embassy["aqi"], us_embassy["utime"]


def get_aqi_hcm():
    url = "https://airnet.waqi.info/airnet/map/bounds"
    data = {
        "bounds": "106.65545867915007,10.773554342818551,106.71194267422896,10.788963661784884",
        "zoom": 16,
        "xscale": 61493.52564648868,
        "width": 2481,
    }

    resp = requests.post(url, json=data)
    locs = resp.json()
    us_embassy = locs["data"][0]

    us_embassy.update(
        {
            "utime": datetime.datetime.utcfromtimestamp(us_embassy["u"]).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
        }
    )
    return us_embassy["n"], us_embassy["a"], us_embassy["utime"]


def get_aqi_jp():
    resp = requests.get(
        "https://api.waqi.info/mapq/bounds/?bounds=35.2002957,139.2889003,35.4002958,139.5889103"
    )
    locs = resp.json()
    if locs == []:
        return "", "", ""
    us_embassy = locs[0]
    return us_embassy["city"], us_embassy["aqi"], us_embassy["utime"]


def send_message(session, chat_id, text="hi"):
    msg = {
        "chat_id": chat_id,
        "text": text,
    }
    session.post(base + "sendMessage", json=msg, timeout=10)


def send_photo(chat_id, file_opened):
    method = "sendPhoto"
    params = {"chat_id": chat_id}
    files = {"photo": file_opened}
    resp = requests.post(base + method, params, files=files)
    return resp


def fit_meanings_to_message(url, meanings):
    result = []
    EACH_MEANING_LIMIT = 160
    for idx, meaning in enumerate(meanings):
        if idx == 5:
            result.append("...")
            break

        if len(meaning) > EACH_MEANING_LIMIT:
            meaning = f"{meaning[:EACH_MEANING_LIMIT]}..."
        msg = f"{idx+1}. {meaning}"
        result.append(msg)
    result.append(url)
    return "\n".join(result)


def get_temp(cities):
    results = []
    for city in cities:
        data_temp = requests.get(
            "https://api.openweathermap.org/data/2.5/weather?q={}&appid={}".format(
                city, API_TEMP
            )
        ).json()
        results.append(
            {
                "name": data_temp["name"],
                "temp_now": round(data_temp["main"]["temp"] - 273.15),
                "feels_like": round(data_temp["main"]["feels_like"] - 273.15),
                "humidity": data_temp["main"]["humidity"],
                "weather": data_temp["weather"][0]["description"],
            }
        )
    return results


def get_price_btc(coin="bitcoin"):
    """
    Fetches the current Bitcoin price in USD, market cap, and 24-hour price change from the CoinGecko API.
    Returns the data as a JSON object.
    """
    url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd&include_market_cap=true&include_24hr_change=true"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses (4xx and 5xx)
        data = response.json()
        
        # Extract Bitcoin price, market cap, and 24-hour change
        btc_data = {
            "price_usd": data["bitcoin"]["usd"],
            "market_cap_usd": data["bitcoin"]["usd_market_cap"],
            "change_24h_percent": data["bitcoin"]["usd_24h_change"]
        }
        
        return btc_data   
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def create_chart(coin="bitcoin"):
    import pandas as pd
    import plotly.graph_objects as go

    def opents2price(row):
        ts = row["Open_Timestamp"]
        rs = float(df[df["Timestamp"] == ts]["Price"].values)
        return rs

    def closets2price(row):
        ts = row["Close_Timestamp"]
        rs = float(df[df["Timestamp"] == ts]["Price"].values)
        return rs

    data = requests.get(
        f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=60",
        timeout=7,
    ).json()

    df = pd.DataFrame(
        data["prices"],
        columns=["Timestamp", "Price"],
    )

    df.index = pd.to_datetime(df["Timestamp"], unit="ms")

    analyzed = pd.DataFrame()
    analyzed["High"] = df.groupby(df.index.date).max("Price")["Price"]
    analyzed["Low"] = df.groupby(df.index.date).min("Price")["Price"]
    analyzed["Date"] = df.groupby(df.index.date).max("Price").index
    analyzed["Open_Timestamp"] = df.groupby(df.index.date).min("Timestamp")["Timestamp"]
    analyzed["Close_Timestamp"] = df.groupby(df.index.date).max("Timestamp")[
        "Timestamp"
    ]
    analyzed["Open"] = analyzed.apply(opents2price, axis=1)
    analyzed["Close"] = analyzed.apply(closets2price, axis=1)

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=analyzed["Date"],
                open=analyzed["Open"],
                high=analyzed["High"],
                low=analyzed["Low"],
                close=analyzed["Close"],
            )
        ]
    )

    fig.update_layout(
        plot_bgcolor="#333333",
        paper_bgcolor="#333333",
        font=dict(color="white"),
        xaxis={"showgrid": False},
        width=900,
        height=600,
    )

    fig.write_image("/tmp/chartimage.png")


def kanji(grade=2, nth=-1):
    if nth == -1:
        nth = random.randrange(jp_dict.NUMBER_OF_YOJO_WORDS)
    k = kanji_service.get_kanji(grade=grade, nth=nth)

    return "{}: {}\n{}\n{}".format(k.char, k.meaning, k.reading, k.url)


class Dispatcher:
    def __init__(self, session):
        self.session = session

    def dispatch_uds(self, text, chat_id, from_id):
        _uds, keyword = text.split(" ", 1)

        try:
            result = uds.urbandictionary(keyword)
            url, meanings = result["url"], result["means"]

        except Exception:
            logger.exception(keyword)
        else:
            msg = fit_meanings_to_message(url, meanings)
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"UrbanDictionary result for `{keyword}`\n" + msg,
            )
            logger.info("UDS: served keyword %s", keyword)

    def dispatch_cam(self, text, chat_id, from_id):
        _cam, keyword = text.split(" ", 1)

        try:
            result = uds.cambridge(keyword)
            url, ipa, meanings = (
                result["url"],
                result["ipa"],
                result["means"],
            )
        except Exception:
            logger.exception(keyword)
        else:
            msg = fit_meanings_to_message(url, meanings)
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"Cambridge result for `{keyword}`\nIPA: {ipa}\n" + msg,
            )
            logger.info("UDS: served cam keyword %s", keyword)

    def dispatch_hi(self, text, chat_id, from_id):
        if not API_TEMP:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="To show weather data, you need a key api and set `WEATHER_TOKEN` env, go to https://openweathermap.org/api to get one.",
            )
        else:
            cities = ["Yokohama", "Ho Chi Minh", "Hanoi"]
            temp_cities = get_temp(cities)
            for temp in temp_cities:
                send_message(
                    session=self.session,
                    chat_id=chat_id,
                    text=f"Weather in {temp['name']} is {temp['weather']}, temp now: {temp['temp_now']}, feels like: {temp['feels_like']}, humidity:  {temp['humidity']}%",
                )
                logger.info("Temp: served city %s", temp["name"])
            city = "jp&hcm&hn"
            location, value, utime = get_aqi_jp()
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"PM2.5 {value} at {location} at {utime}",
            )
            location, value, utime = get_aqi_hcm()
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"PM2.5 {value} at {location} at {utime}",
            )
            location, value, utime = get_aqi_hanoi()
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"PM2.5 {value} at {location} at {utime}",
            )
            logger.info("AQI: served city %s", city)

    def dispatch_jo(self, text, chat_id, from_id):
        parts = text.split(" ")
        if len(parts) == 2:
            grade = parts[1]
            nth = -1
        elif len(parts) == 3:
            _cmd, grade, nth = parts
            nth = -1
        else:
            grade = 3
            nth = -1
            logger.info("Get joyo kanji grade: %d #%d", grade, nth)
        send_message(session=self.session, chat_id=chat_id, text=kanji(grade, int(nth)))

    def dispatch_fr(self, text, chat_id, from_id):
        _cam, keyword = text.split(" ", 1)

        try:
            result = uds.cambridge_fr(keyword)
            url, ipa, meanings = (
                result["url"],
                result["ipa"],
                result["means"],
            )
        except Exception:
            logger.exception(keyword)
        else:
            msg = fit_meanings_to_message(url, meanings)
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"Cambridge result for `{keyword}`\nIPA: {ipa}\n" + msg,
            )
            logger.info("UDS: served camfr keyword %s", keyword)

    def dispatch_ji(self, text, chat_id, from_id):
        _cam, keyword = text.split(" ", 1)

        try:
            result = jp_dict.search_jisho(keyword)
            url, ipa, meanings = (
                result["url"],
                result["reading"],
                result["means"],
            )
        except Exception:
            logger.exception(keyword)
        else:
            msg = fit_meanings_to_message(url, meanings)
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"Jisho result for `{keyword}`\nReading: {ipa}\n" + msg,
            )
            logger.info("Jisho: served ji keyword %s", keyword)

    def dispatch_aqi(self, text, chat_id, from_id):
        city = "hn&hcm&jp"
        location, value, utime = get_aqi_hanoi()
        send_message(
            session=self.session,
            chat_id=chat_id,
            text=f"PM2.5 {value} at {location} at {utime}",
        )

        location, value, utime = get_aqi_hcm()
        send_message(
            session=self.session,
            chat_id=chat_id,
            text=f"PM2.5 {value} at {location} at {utime}",
        )
        location, value, utime = get_aqi_jp()
        send_message(
            session=self.session,
            chat_id=chat_id,
            text=f"PM2.5 {value} at {location} at {utime}",
        )
        logger.info("AQI: served city %s", city)

    def dispatch_tem(self, text, chat_id, from_id):
        if not API_TEMP:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="To show weather data, you need a key api and set `WEATHER_TOKEN` env, go to https://openweathermap.org/api to get one.",
            )
        else:
            cities = ["Yokohama", "Ho Chi Minh"]
            temp_cities = get_temp(cities)
            for temp in temp_cities:
                send_message(
                    session=self.session,
                    chat_id=chat_id,
                    text=f"Weather in {temp['name']} is {temp['weather']}, temp now: {temp['temp_now']}, feels like: {temp['feels_like']}, humidity:  {temp['humidity']}%",
                )
                logger.info("Temp: served city %s", temp["name"])

    def dispatch_btc(self, text, chat_id, from_id):
        try:
            code = text.split(" ")[1].lower()
        except IndexError:
            code = "btc"

        try:
            coin_code = _get_coin_name(code)
        except KeyError:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="Try coin in list:[btc, eth, usdt, bnb, ada, doge, xrp, ltc, link, xlm]",
            )
        else:
            prices_data = get_price_btc(coin_code)
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"""{coin_code.upper()} ${prices_data["price_usd"]}
    Cap ${round(prices_data["market_cap_usd"]/1000000000,1)}B
    24h {round(prices_data["change_24h_percent"],1)}% """,
            )

    def dispatch_c(self, text, chat_id, from_id):
        try:
            code = text.split(" ")[1].lower()
        except IndexError:
            code = "btc"

        try:
            coin_code = _get_coin_name(code)
        except KeyError:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="Try coin in list:[btc, eth, usdt, bnb, ada, doge, xrp, ltc, link, xlm]",
            )

        try:
            create_chart(coin_code)
            imgfile = "/tmp/chartimage.png"
            with open(imgfile, "rb") as f:
                send_photo(chat_id, f)
            logger.info("Get price of %s", coin_code)
        except Exception as e:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"Create chart failed with error: {e}, {type(e)}",
            )

    def dispatch_aoc(self, text, chat_id, from_id):
        try:
            _cmd, topn = text.split(" ", 1)
            topn = int(topn)
        except Exception:
            topn = 10
        send_message(session=self.session, chat_id=chat_id, text=aoc21(topn))

    def dispatch_cron(self, text, chat_id, from_id):
        cronjob.add_job(text, chat_id, from_id)

    def dispatch(self, text, chat_id, from_id):
        cmd, *_ = text.split()
        pure_cmd = cmd.strip().lstrip("/")
        func = getattr(self, f"dispatch_{pure_cmd}", print)
        logger.info(f"dispatching {func.__name__} from {text}")
        func(text, chat_id, from_id)


def fetch_message_and_process(session):
    try:
        with open(OFFSET_FILE) as f:
            offset = int(f.read().strip())
            params = {"offset": offset + 1}
    except IOError:
        params = None

    resp = session.get(base + "getUpdates", json=params, timeout=20)
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

            if text.startswith(
                (
                    "/uds ",
                    "/cam ",
                    "/fr ",
                    "/aqi",
                    "/tem",
                    "/hi",
                    "/btc",
                    "/c ",
                    "/aoc",
                    "/jo",
                    "/cron ",
                    "/ji ",
                )
            ):
                dispatcher.dispatch(text, chat_id, from_id)

            with open(OFFSET_FILE, "w") as f:
                f.write(str(update_id))


if __name__ == "__main__":
    while True:
        with requests.Session() as S:
            fetch_message_and_process(session=S)
            dispatcher = Dispatcher(session=S)
            cronjob.run_cron(dispatcher.dispatch)
            time.sleep(60)
