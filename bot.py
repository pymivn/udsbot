#!/usr/bin/env python

import logging
import os
import time

import requests
import uds


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger()

OFFSET_FILE = "/tmp/uds_telegrambot_offset"
BOT_TOKEN = os.environ["BOT_TOKEN"]
# get temp token from https://openweathermap.org/
API_TEMP = os.environ["WEATHER_TOKEN"]
AOC_SESSION = os.environ.get("AOC_SESSION")

base = f"https://api.telegram.org/bot{BOT_TOKEN}/"

os.environ["TZ"] = "Asia/Ho_Chi_Minh"

def aoc21(topn=10):
    cookies = {
      "session": AOC_SESSION
    }

    r = requests.get('https://adventofcode.com/2021/leaderboard/private/view/416592.json',
                     cookies=cookies)
    d = r.json()
    scoreboard = [(e['name'], e['local_score'],e['stars'])
     for e in sorted(d["members"].values(), key=lambda i: i['local_score'], reverse=True) if e['stars'] > 0]

    lines = [
        f"{idx}. " + " ".join((str(p) for p in i))
        for idx, i in enumerate(scoreboard[:topn])
    ]

    return ("\n".join(lines))


def _get_coin_name(code):
    return dict([
        ("btc", "bitcoin"),
        ("eth", "ethereum"),
        ("usdt", "tether"),
        ("bnb", "binancecoin"),
        ("ada", "cardano"),
        ("doge", "dogecoin"),
        ("xrp", "xrp"),
        ("ltc", "litecoin"),
        ("link", "chainlink"),
        ("xlm", "stellar"),
    ])[code]

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
    resp = requests.get(
        "https://api.waqi.info/mapq/bounds/?bounds=9.96885060854611,105.71594238281251,12.232654837013484,108.30871582031251"
    )
    locs = resp.json()
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
    for idx, meaning in enumerate(meanings):
        if idx == 3:
            result.append("...")
            break

        if len(meaning) > 140:
            meaning = f"{meaning[:140]}..."
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
    # only get btc_price
    # resp = requests.get("https://api.coindesk.com/v1/bpi/currentprice.json").json()
    # btc_price = "".join(resp["bpi"]["USD"]["rate"].split(".")[0].split(","))
    # return btc_price
    from pycoingecko import CoinGeckoAPI

    cg = CoinGeckoAPI()
    data = cg.get_price(
        ids=coin,
        vs_currencies="usd",
        include_market_cap=True,
        include_24hr_vol=True,
        include_24hr_change=True,
        include_last_updated_at=True,
    )
    return data


def create_chart(coin="bitcoin"):
    import pandas as pd
    from datetime import datetime
    import plotly.graph_objects as go

    def opents2price(row):
        ts = row['Open_Timestamp']
        rs = float(df[df['Timestamp'] == ts]['Price'].values)
        return rs

    def closets2price(row):
        ts = row['Close_Timestamp']
        rs = float(df[df['Timestamp'] == ts]['Price'].values)
        return rs

    data = requests.get(
        f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart?vs_currency=usd&days=60",
        timeout=7
    ).json()

    df = pd.DataFrame(
        data["prices"],
        columns=["Timestamp", "Price"],
    )

    df.index = pd.to_datetime(df['Timestamp'], unit='ms')

    analyzed = pd.DataFrame()
    analyzed['High'] = df.groupby(df.index.date).max('Price')['Price']
    analyzed['Low'] = df.groupby(df.index.date).min('Price')['Price']
    analyzed['Date'] = df.groupby(df.index.date).max('Price').index
    analyzed['Open_Timestamp'] = df.groupby(df.index.date).min('Timestamp')['Timestamp']
    analyzed['Close_Timestamp'] = df.groupby(df.index.date).max('Timestamp')['Timestamp']
    analyzed['Open'] = analyzed.apply(opents2price, axis=1)
    analyzed['Close'] = analyzed.apply(closets2price, axis=1)

    fig = go.Figure(data=[go.Candlestick(x=analyzed['Date'],
            open=analyzed['Open'],
            high=analyzed['High'],
            low=analyzed['Low'],
            close=analyzed['Close'])])

    fig.update_layout(plot_bgcolor="#333333",
                    paper_bgcolor="#333333",
                    font=dict(color="white"),
                    xaxis={'showgrid':False},
                    width=900, height=600)

    fig.write_image("/tmp/chartimage.png")

def main():
    with requests.Session() as S:
        try:
            with open(OFFSET_FILE) as f:
                offset = int(f.read().strip())
                params = {"offset": offset + 1}
        except IOError:
            params = None

        resp = S.get(base + "getUpdates", json=params, timeout=20)
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
            except KeyError:
                continue
            if "text" in message:
                chat_id = r["message"]["chat"]["id"]
                text = r["message"]["text"].strip()

                if text.startswith("/aoc21 "):
                    _cmd, topn = text.split(" ", 1)
                    topn = int(topn)
                    send_message(
                        session=S,
                        chat_id=chat_id,
                        text=aoc21(topn)
                        )

                if text.startswith("/uds "):
                    _uds, keyword = text.split(" ", 1)

                    try:
                        result = uds.urbandictionary(keyword)
                        url, meanings = result["url"], result["means"]

                    except Exception:
                        logger.exception(keyword)
                    else:
                        msg = fit_meanings_to_message(url, meanings)
                        send_message(
                            session=S,
                            chat_id=chat_id,
                            text=f"UrbanDictionary result for `{keyword}`\n" + msg,
                        )
                        logger.info("UDS: served keyword %s", keyword)

                elif text.startswith("/cam "):
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
                            session=S,
                            chat_id=chat_id,
                            text=f"Cambridge result for `{keyword}`\nIPA: {ipa}\n"
                            + msg,
                        )
                        logger.info("UDS: served cam keyword %s", keyword)

                elif text.startswith("/fr "):
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
                            session=S,
                            chat_id=chat_id,
                            text=f"Cambridge result for `{keyword}`\nIPA: {ipa}\n"
                            + msg,
                        )
                        logger.info("UDS: served camfr keyword %s", keyword)

                elif text.startswith("/aqi"):
                    # _aqi, city = text.split(" ", 1)
                    city = "hn&hcm"
                    location, value, utime = get_aqi_hanoi()
                    send_message(
                        session=S,
                        chat_id=chat_id,
                        text=f"PM2.5 {value} at {location} at {utime}",
                    )

                    location, value, utime = get_aqi_hcm()
                    send_message(
                        session=S,
                        chat_id=chat_id,
                        text=f"PM2.5 {value} at {location} at {utime}",
                    )
                    logger.info("AQI: served city %s", city)

                elif text.startswith("/tem"):

                    if not API_TEMP:
                        send_message(
                            session=S,
                            chat_id=chat_id,
                            text="To show weather data, you need a key api and set `WEATHER_TOKEN` env, go to https://openweathermap.org/api to get one.",
                        )
                    else:
                        cities = ["Hanoi", "Ho Chi Minh"]
                        temp_cities = get_temp(cities)
                        for temp in temp_cities:
                            send_message(
                                session=S,
                                chat_id=chat_id,
                                text=f"Weather in {temp['name']} is {temp['weather']}, temp now: {temp['temp_now']}, feels like: {temp['feels_like']}, humidity:  {temp['humidity']}%",
                            )
                            logger.info("Temp: served city %s", temp["name"])
                elif text.startswith("/hi"):
                    if not API_TEMP:
                        send_message(
                            session=S,
                            chat_id=chat_id,
                            text="To show weather data, you need a key api and set `WEATHER_TOKEN` env, go to https://openweathermap.org/api to get one.",
                        )
                    else:
                        cities = ["Hanoi", "Ho Chi Minh"]
                        temp_cities = get_temp(cities)
                        for temp in temp_cities:
                            send_message(
                                session=S,
                                chat_id=chat_id,
                                text=f"Weather in {temp['name']} is {temp['weather']}, temp now: {temp['temp_now']}, feels like: {temp['feels_like']}, humidity:  {temp['humidity']}%",
                            )
                            logger.info("Temp: served city %s", temp["name"])
                        city = "hn&hcm"
                        location, value, utime = get_aqi_hanoi()
                        send_message(
                            session=S,
                            chat_id=chat_id,
                            text=f"PM2.5 {value} at {location} at {utime}",
                        )

                        location, value, utime = get_aqi_hcm()
                        send_message(
                            session=S,
                            chat_id=chat_id,
                            text=f"PM2.5 {value} at {location} at {utime}",
                        )
                        logger.info("AQI: served city %s", city)

                elif text.startswith("/btc"):
                    try:
                        code = text.split(" ")[1].lower()
                    except IndexError:
                        code = "btc"

                    try:
                        coin_code = _get_coin_name(code)
                    except KeyError:
                        send_message(
                            session=S,
                            chat_id=chat_id,
                            text="Try coin in list:[btc, eth, usdt, bnb, ada, doge, xrp, ltc, link, xlm]",
                        )
                    prices_data = get_price_btc(coin_code)
                    send_message(
                        session=S,
                        chat_id=chat_id,
                        text=f"""{coin_code.upper()} ${prices_data[coin_code]['usd']}
Cap ${round(prices_data[coin_code]['usd_market_cap']/1000000000,1)}B
24h {round(prices_data[coin_code]['usd_24h_change'],1)}% """,
                    )

                elif text == "/c" or text.startswith("/c "):
                    try:
                        code = text.split(" ")[1].lower()
                    except IndexError:
                        code = "btc"

                    try:
                        coin_code = _get_coin_name(code)
                    except KeyError:
                        send_message(
                            session=S,
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
                        send_message(session=S, chat_id=chat_id, text=f"Create chart failed with error: {e}, {type(e)}")
                else:
                    logger.info("Unknown command: %s", text)

                with open(OFFSET_FILE, "w") as f:
                    f.write(str(update_id))

    time.sleep(30)


if __name__ == "__main__":
    while True:
        main()
