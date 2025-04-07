import logging
import os
import json
import time
import datetime
import hashlib
import random
from typing import MutableMapping, BinaryIO, cast

import requests
import uds
import jp_dict
import cronjob

import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

BOT_TOKEN = os.environ["BOT_TOKEN"]
# get temp token from https://openweathermap.org/
API_TEMP = os.environ["WEATHER_TOKEN"]
AOC_SESSION = os.environ.get("AOC_SESSION")

os.environ["TZ"] = "Asia/Ho_Chi_Minh"


dbpath = ":memory:"
db = jp_dict.init_kanji_db(dbpath)
kanji_service = jp_dict.KanjiService(db)


def aoc21(topn: int = 10) -> str:
    cookies = {"session": AOC_SESSION}

    if not isinstance(AOC_SESSION, str):
        raise ValueError("AOC_SESSION must be a non-empty string")

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

        # Filter out None values
        cookies = {key: value for key, value in cookies.items() if value is not None}
        # Cast to the expected type that requests.get() requires
        typed_cookies: MutableMapping[str, str] = cast(
            MutableMapping[str, str], cookies
        )
        r = requests.get(
            "https://adventofcode.com/2024/leaderboard/private/view/416592.json",
            cookies=typed_cookies,
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


def _get_coin_name(code: str) -> str:
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


def get_aqi_hanoi() -> tuple:
    resp = requests.get(
        "https://api.waqi.info/mapq/bounds/?bounds=20.96111901161895,105.75405120849611,21.09571147652958,105.91609954833986"
    )
    locs = resp.json()
    for i in locs:
        if "BVMT" in i["city"]:
            us_embassy = i
            break
    return us_embassy["city"], us_embassy["aqi"], us_embassy["utime"]


def get_aqi_hcm() -> tuple:
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


def get_aqi_jp() -> tuple:
    resp = requests.get(
        "https://api.waqi.info/mapq/bounds/?bounds=35.2002957,139.2889003,35.4002958,139.5889103"
    )
    locs = resp.json()
    if locs == []:
        return "", "", ""
    us_embassy = locs[0]
    return us_embassy["city"], us_embassy["aqi"], us_embassy["utime"]


def send_message(session: requests.Session, chat_id: int, text: str = "hi") -> None:
    msg = {
        "chat_id": chat_id,
        "text": text,
    }
    session.post(config.TELEGRAM_BASE_URL + "sendMessage", json=msg, timeout=10)


def send_photo(chat_id: int, file_opened: BinaryIO) -> requests.Response:
    method = "sendPhoto"
    params = {"chat_id": chat_id}
    files = {"photo": file_opened}
    resp = requests.post(config.TELEGRAM_BASE_URL + method, params, files=files)
    return resp


def fit_meanings_to_message(url: str, meanings: list) -> str:
    result = []
    EACH_MEANING_LIMIT = 160
    for idx, meaning in enumerate(meanings):
        if idx == 5:
            result.append("...")
            break

        if len(meaning) > EACH_MEANING_LIMIT:
            meaning = f"{meaning[:EACH_MEANING_LIMIT]}..."
        msg = f"{idx + 1}. {meaning}"
        result.append(msg)
    result.append(url)
    return "\n".join(result)


def get_temp(cities: list) -> list:
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


def get_price_btc(coin: str = "bitcoin") -> dict:
    """
    Fetches the current Bitcoin price in USD, market cap, and 24-hour price change from the CoinGecko API.
    Returns the data as a JSON object.
    """
    url = f"https://api.coingecko.com/api/v3/simple/price?ids={coin}&vs_currencies=usd&include_market_cap=true&include_24hr_change=true"

    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise an error for bad responses (4xx and 5xx)
        data = response.json()

        # Extract Bitcoin price, market cap, and 24-hour change
        btc_data = {
            "price_usd": data[coin]["usd"],
            "market_cap_usd": data[coin]["usd_market_cap"],
            "change_24h_percent": data[coin]["usd_24h_change"],
        }

        return btc_data
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}


def create_chart(coin: str = "bitcoin") -> None:
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

    df.index = pd.to_datetime(df["Timestamp"], unit="ms")  # type: ignore
    df["date"] = df.index.date  # type: ignore

    analyzed = pd.DataFrame()
    analyzed["High"] = df.groupby("date")["Price"].max()
    analyzed["Low"] = df.groupby("date")["Price"].min()
    analyzed["Date"] = df.groupby("date").max()["Price"].index
    analyzed["Open_Timestamp"] = df.groupby("date")["Timestamp"].min()
    analyzed["Close_Timestamp"] = df.groupby("date")["Timestamp"].max()
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


def kanji(grade: int = 2, nth: int = -1) -> str:
    if nth == -1:
        nth = random.randrange(jp_dict.NUMBER_OF_YOJO_WORDS)
    k = kanji_service.get_kanji(grade=grade, nth=nth)

    return "{}: {}\n{}\n{}".format(k.char, k.meaning, k.reading, k.url)


class Dispatcher:
    def __init__(self, session: requests.Session) -> None:
        self.session = session

    def dispatch_uds(self, text: str, chat_id: int, from_id: int) -> None:
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

    def dispatch_cam(self, text: str, chat_id: int, from_id: int) -> None:
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

    def dispatch_hi(self, text: str, chat_id: int, from_id: int) -> None:
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

    def dispatch_jo(self, text: str, chat_id: int, from_id: int) -> None:
        parts = text.split(" ")
        if len(parts) == 2:
            grade = int(parts[1])  # Convert to int
            nth = -1
        elif len(parts) == 3:
            _cmd, grade_str, nth_str = parts
            grade = int(grade_str)  # Convert to int
            try:
                nth = int(nth_str)
            except ValueError:
                nth = -1
        else:
            grade = 3
            nth = -1
            logger.info("Get joyo kanji grade: %d #%d", grade, nth)
        send_message(session=self.session, chat_id=chat_id, text=kanji(grade, int(nth)))

    def dispatch_fr(self, text: str, chat_id: int, from_id: int) -> None:
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

    def dispatch_ji(self, text: str, chat_id: int, from_id: int) -> None:
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

    def dispatch_aqi(self, text: str, chat_id: int, from_id: int) -> None:
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

    def dispatch_tem(self, text: str, chat_id: int, from_id: int) -> None:
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

    def dispatch_btc(self, text: str, chat_id: int, from_id: int) -> None:
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
                text=f"""{coin_code.upper()} ${prices_data[coin_code]["usd"]}
    Cap ${round(prices_data[coin_code]["usd_market_cap"] / 1000000000, 1)}B
    24h {round(prices_data[coin_code]["usd_24h_change"], 1)}% """,
            )

    def dispatch_c(self, text: str, chat_id: int, from_id: int) -> None:
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

    def dispatch_aoc(self, text: str, chat_id: int, from_id: int) -> None:
        try:
            _cmd, topn_str = text.split(" ", 1)
            topn = int(topn_str)
        except Exception:
            topn = 10
        send_message(session=self.session, chat_id=chat_id, text=aoc21(topn))

    def dispatch_cron(self, text: str, chat_id: int, from_id: int) -> None:
        try:
            job_uuid = cronjob.add_job(text, chat_id, from_id)
        except Exception as e:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"Add cron job failed with error: {e}, {type(e)}",
            )
        else:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"Cron job added successfully! To delete this job: /delcron {job_uuid}",
            )

    def dispatch_delcron(self, text: str, chat_id: int, from_id: int) -> None:
        try:
            cronjob.del_job(text, chat_id, from_id)
        except Exception as e:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"Delete cron job failed with error: {e}, {type(e)}",
            )
        else:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="Cron job deleted successfully!",
            )

    def dispatch_listcron(self, text: str, chat_id: int, from_id: int) -> None:
        try:
            jobs = cronjob.list_job(text, chat_id, from_id)
        except Exception as e:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"List cron jobs failed with error: {e}, {type(e)}",
            )
        else:
            jobs_str = "\n".join(
                [f"{job.uuid} - {job.hour}:{job.minute} {job.command}" for job in jobs]
            )
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=jobs_str,
            )

    def dispatch(self, text: str, chat_id: int, from_id: int) -> None:
        cmd, *_ = text.split()
        pure_cmd = cmd.strip().lstrip("/")
        func = getattr(self, f"dispatch_{pure_cmd}", print)
        if func is None:
            logger.warn(f"dispatch_{pure_cmd} method not exist, skip from {text}")
            return
        logger.info(f"dispatching {func.__name__} from {text}")
        func(text, chat_id, from_id)
