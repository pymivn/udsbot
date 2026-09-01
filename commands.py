import logging
import os
import json
import time
import datetime
import hashlib
import random
import re
from dataclasses import dataclass
from typing import BinaryIO

import requests
import dict_lookup
import jp_dict
import cronjob
import llm
import jp_podcast

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
        clean_cookies = {
            key: value for key, value in cookies.items() if value is not None
        }
        r = requests.get(
            "https://adventofcode.com/2024/leaderboard/private/view/416592.json",
            cookies=clean_cookies,
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
    if len(locs) > 0:
        for i in locs:
            if i["aqi"].isdigit() and int(i["aqi"]) > 0:
                return i["city"], i["aqi"], i["utime"]
        return locs[0]["city"], None, locs[0]["utime"]
    else:
        return "Hanoi", None, None


def get_aqi_singapore() -> tuple:
    resp = requests.get(
        "https://api.waqi.info/mapq/bounds/?bounds=1.156,103.605,1.494,104.084",
        timeout=10,
    )
    locs = resp.json()
    if len(locs) > 0:
        for i in locs:
            if i["aqi"].isdigit() and int(i["aqi"]) > 0:
                return i["city"], i["aqi"], i["utime"]
        return locs[0]["city"], None, locs[0]["utime"]
    else:
        return "Singapore", None, None


def get_aqi_hcm() -> tuple:
    url = "https://airnet.waqi.info/airnet/map/bounds"

    tz_hcm = datetime.timezone(datetime.timedelta(hours=7))
    current_time = datetime.datetime.now(datetime.timezone.utc).isoformat()

    data = {
        "bounds": "106.57606490366962,10.710644309189911,106.83509113187337,10.906718682210693",
        "zoom": "11",
        "xscale": "1303.4747344074406",
        "width": "678",
        "time": current_time,
    }

    response = requests.post(url, data=data)
    locs = response.json()["data"]

    if len(locs) > 0:
        highest_aqi = max(locs, key=lambda x: x["u"] if isinstance(x["u"], int) else 0)

        if highest_aqi:
            name = highest_aqi["n"]
            aqi_value = highest_aqi["a"]
            utime = datetime.datetime.fromtimestamp(
                highest_aqi["u"], tz=tz_hcm
            ).strftime("%Y-%m-%d %H:%M:%S")
            return name, aqi_value, utime

    return "Ho Chi Minh City", None, None


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

    df.index = pd.to_datetime(df["Timestamp"], unit="ms")
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

    return jp_dict.format_kanji(k)


def extract_keyword_from_text(text: str) -> str:
    if not text or not text.strip():
        return ""

    lines = [line.strip() for line in text.strip().splitlines() if line.strip()]
    if not lines:
        return ""

    first_line = lines[0]

    # Check for backticked word e.g. "Jisho result for `inryou`" or "Cambridge result for `run`"
    backtick_match = re.search(r"`([^`]+)`", first_line)
    if backtick_match:
        return backtick_match.group(1).strip()

    # Check for colon-separated line e.g. "飲: drink, smoke, take" or "漢字: China, Sino-"
    if ":" in first_line:
        before_colon, _ = first_line.split(":", 1)
        cleaned_before = before_colon.strip()
        # If the part before colon is 1-2 words and not excessively long, treat as keyword/kanji
        if (
            cleaned_before
            and len(cleaned_before.split()) <= 2
            and len(cleaned_before) <= 30
        ):
            return cleaned_before

    # Fallback to the first word/token of the first line
    words = first_line.split()
    if words:
        return words[0]
    return first_line


@dataclass(frozen=True)
class ParsedXCommand:
    sub_cmd: str | None
    keyword: str


def parse_x_command(
    text: str,
    reply_text: str | None = None,
    available_commands: set[str] | None = None,
) -> ParsedXCommand:
    parts = text.strip().split()
    args = parts[1:] if len(parts) > 1 else []

    sub_cmd: str | None = None
    keyword = ""

    if (
        available_commands
        and args
        and args[0].lstrip("/").lower() in available_commands
    ):
        sub_cmd = args[0].lstrip("/").lower()
        args = args[1:]

    if args:
        keyword = " ".join(args).strip()
    elif reply_text:
        keyword = extract_keyword_from_text(reply_text)

    return ParsedXCommand(sub_cmd=sub_cmd, keyword=keyword)


class Dispatcher:
    def __init__(self, session: requests.Session) -> None:
        self.session = session

    def dispatch_cam(
        self,
        text: str,
        chat_id: int,
        from_id: int,
        reply_text: str | None = None,
    ) -> None:
        parts = text.split(" ", 1)
        keyword = (
            parts[1].strip()
            if len(parts) > 1 and parts[1].strip()
            else extract_keyword_from_text(reply_text or "")
        )
        if not keyword:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="Usage: /cam <word> or reply to a message with /cam",
            )
            return

        try:
            result = dict_lookup.lookup_word(keyword)
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

    def dispatch_fr(
        self,
        text: str,
        chat_id: int,
        from_id: int,
        reply_text: str | None = None,
    ) -> None:
        parts = text.split(" ", 1)
        keyword = (
            parts[1].strip()
            if len(parts) > 1 and parts[1].strip()
            else extract_keyword_from_text(reply_text or "")
        )
        if not keyword:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="Usage: /fr <word> or reply to a message with /fr",
            )
            return

        try:
            result = dict_lookup.lookup_word_fr(keyword)
            url, meanings = (
                result["url"],
                result["means"],
            )
        except Exception:
            logger.exception(keyword)
        else:
            msg = fit_meanings_to_message(url, meanings)
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"French dictionary result for `{keyword}`\n" + msg,
            )
            logger.info("UDS: served fr keyword %s", keyword)

    def dispatch_hi(self, text: str, chat_id: int, from_id: int) -> None:
        if not API_TEMP:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="To show weather data, you need a key api and set `WEATHER_TOKEN` env, go to https://openweathermap.org/api to get one.",
            )
        else:
            cities = ["Ho Chi Minh", "Hanoi", "Singapore"]
            temp_cities = get_temp(cities)
            for temp in temp_cities:
                send_message(
                    session=self.session,
                    chat_id=chat_id,
                    text=f"Weather in {temp['name']} is {temp['weather']}, temp now: {temp['temp_now']}, feels like: {temp['feels_like']}, humidity:  {temp['humidity']}%",
                )
                logger.info("Temp: served city %s", temp["name"])
            city = "hcm&hn&sg"

            location, value, utime = get_aqi_hcm()
            if location is not None or value is not None or utime is not None:
                send_message(
                    session=self.session,
                    chat_id=chat_id,
                    text=f"PM2.5 {value} at {location} at {utime}",
                )
            else:
                send_message(
                    session=self.session,
                    chat_id=chat_id,
                    text="No AQI available for Ho Chi Minh City",
                )

            location, value, utime = get_aqi_hanoi()
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=f"PM2.5 {value} at {location} at {utime}",
            )

            location, value, utime = get_aqi_singapore()
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

    def dispatch_jk(self, text: str, chat_id: int, from_id: int) -> None:
        msg = llm.gen_joke()
        send_message(session=self.session, chat_id=chat_id, text=msg[:300])
        logger.info("served a joke")

    def dispatch_nikkei(self, text: str, chat_id: int, from_id: int) -> None:
        episodes = jp_podcast.get_latest_podcast_episodes()
        latest = episodes[0]

        msg = llm.translate_sentence(latest.name)
        send_message(session=self.session, chat_id=chat_id, text=f"{msg}\n{latest.url}")
        logger.info("served nikkeime")

    def dispatch_lt(
        self,
        text: str,
        chat_id: int,
        from_id: int,
        reply_text: str | None = None,
    ) -> None:
        parts = text.split(" ", 1)
        keyword = (
            parts[1].strip()
            if len(parts) > 1 and parts[1].strip()
            else extract_keyword_from_text(reply_text or "")
        )
        if not keyword:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="Usage: /lt <word> or reply to a message with /lt",
            )
            return
        msg = llm.translate(keyword)
        send_message(session=self.session, chat_id=chat_id, text=msg[:300])
        logger.info(f"LLM translated {text}")

    def dispatch_ji(
        self,
        text: str,
        chat_id: int,
        from_id: int,
        reply_text: str | None = None,
    ) -> None:
        parts = text.split(" ", 1)
        keyword = (
            parts[1].strip()
            if len(parts) > 1 and parts[1].strip()
            else extract_keyword_from_text(reply_text or "")
        )
        if not keyword:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="Usage: /ji <word> or reply to a message with /ji",
            )
            return

        try:
            result = jp_dict.search_jisho(keyword)
            url, reading, meanings = (
                result["url"],
                result["reading"],
                result["means"],
            )
            sentences = kanji_service.get_examples_for_text(keyword, max_results=2)
        except Exception:
            logger.exception(keyword)
        else:
            msg = jp_dict.format_jisho_result(
                keyword=keyword,
                reading=reading,
                meanings=meanings,
                url=url,
                sentences=sentences,
            )
            send_message(
                session=self.session,
                chat_id=chat_id,
                text=msg,
            )
            logger.info("Jisho: served ji keyword %s", keyword)

    def dispatch_aqi(self, text: str, chat_id: int, from_id: int) -> None:
        city = "hn&hcm&sg"
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

        location, value, utime = get_aqi_singapore()
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
            cities = ["Ho Chi Minh", "Hanoi", "Singapore"]
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
                text=f"""{coin_code.upper()} ${prices_data["price_usd"]}
    Cap ${round(prices_data["market_cap_usd"] / 1000000000, 1)}B
    24h {round(prices_data["change_24h_percent"], 1)}% """,
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

    def _get_available_commands(self) -> set[str]:
        return {
            name.removeprefix("dispatch_")
            for name in dir(self)
            if name.startswith("dispatch_")
            and name not in {"dispatch_x", "dispatch_xj", "dispatch_ex"}
        }

    def dispatch_x(
        self,
        text: str,
        chat_id: int,
        from_id: int,
        reply_text: str | None = None,
    ) -> None:
        parsed = parse_x_command(
            text,
            reply_text=reply_text,
            available_commands=self._get_available_commands() | {"ai"},
        )

        if not parsed.keyword:
            send_message(
                session=self.session,
                chat_id=chat_id,
                text="Usage: /x <word> or reply to a message with /x",
            )
            return

        # Dispatch sub-command first (e.g., /x ji 飲料 runs /ji then shows AI example)
        if parsed.sub_cmd and parsed.sub_cmd != "ai":
            self.dispatch(f"{parsed.sub_cmd} {parsed.keyword}", chat_id, from_id)

        msg = llm.gen_example(parsed.keyword)
        send_message(session=self.session, chat_id=chat_id, text=msg[:300])
        logger.info("x ai for keyword %s", parsed.keyword)

    def dispatch(
        self,
        text: str,
        chat_id: int,
        from_id: int,
        reply_text: str | None = None,
    ) -> None:
        if not text or not text.strip():
            logger.warning("Received empty message, skipping")
            return

        cmd, *_ = text.split()
        pure_cmd = cmd.strip().lstrip("/")
        func = getattr(self, f"dispatch_{pure_cmd}", None)
        if func is None:
            logger.warning("dispatch_%s method not exist, skip from %s", pure_cmd, text)
            return
        logger.info(
            "dispatching %s from %s", getattr(func, "__name__", str(func)), text
        )

        import inspect

        try:
            sig = inspect.signature(func)
            if "reply_text" in sig.parameters:
                func(text, chat_id, from_id, reply_text=reply_text)
            else:
                func(text, chat_id, from_id)
        except (ValueError, TypeError):
            func(text, chat_id, from_id)
