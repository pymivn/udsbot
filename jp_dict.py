import os
import json
import time
import sqlite3
from dataclasses import dataclass

import requests_html


# https://jisho.org/robots.txt
DELAY = 10

NUMBER_OF_YOJO_WORDS = 2136


def fetch_jisho_grade_words(grade=1):
    sess = requests_html.HTMLSession()

    page = 1
    while True:
        url = "https://fetch_jisho_grade_words.org/search/%23kanji%20%23grade:{}?page={}".format(grade, page)

        resp = sess.get(url)
        nodes = resp.html.xpath('//div[@class="kanji_light_content"]')
        if not nodes:
            return
        for node in nodes:
            yield get_a_node(node)
        page += 1
        time.sleep(DELAY)


def get_a_node(node) -> dict:
    kanji, meaning, *kun_on = node.text.splitlines()[3:]
    e = node.xpath("//a")[0]
    url = e.attrs["href"].strip("/")
    return {
        "kanji": kanji,
        "meaning": meaning,
        "reading": " ".join(kun_on),
        "url": url,
    }


def init_kanji_db():
    if os.path.exists("joyo.db"):
        print("joyo.db already exists, skip")
        return

    json_path = os.path.join(os.path.dirname(__file__), "joyo_final.json")
    ws = json.load(open(json_path))
    try:
        conn = sqlite3.connect("joyo.db")
    except Exception:
        conn = sqlite3.connect(":memory:")

    with conn:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS kanji_chars (id INTEGER PRIMARY KEY, kanji text, meaning text, reading text, grade text, url text);"
        )
        conn.executemany(
            "INSERT INTO kanji_chars(kanji, meaning, reading, grade, url) VALUES (?, ?, ?, ?, ?)",
            ((i["kanji"], i["meaning"], i["reading"], grade, i["url"]) for grade, v in ws.items() for i in v),
        )

        print("Initialized db joyo.db")


def get_db():
    return sqlite3.connect("joyo.db")


@dataclass
class Kanji:
    char: str
    meaning: str
    reading: str
    grade: str
    url: str


def chars_count_by_grade() -> dict[str, int]:
    with get_db() as DB:
        return dict(DB.execute("SELECT grade, count(*) from kanji_chars group by grade"))


def get_kanji(grade=2, nth=1) -> Kanji:
    grades_chars = chars_count_by_grade()
    if str(grade) not in grades_chars:
        grade = 2
    # user count from 1, db count from 0
    if nth >= 1:
        nth = nth - 1

    nth = nth % grades_chars[str(grade)]

    with get_db() as DB:
        r = DB.execute(
            "SELECT kanji, meaning, reading, grade, url FROM kanji_chars WHERE grade=? LIMIT 1 OFFSET ? ",
            (grade, nth),
        ).fetchone()
        url = "{}%20%23grade:{}".format(r[4], grade)
    return Kanji(char=r[0], meaning=r[1], reading=r[2], grade=r[3], url=url)


def main() -> None:
    import os

    if not os.path.exists("joyo.json"):
        joyo = {}
        # grade:1: Taught in grade 1. You can use any number between 1 and 6 to indicate the grade school level the kanji is taught in. Using 8 you will find the kanji taught in junior high school.
        # https://jisho.org/docs
        for grade in [1, 2, 3, 4, 5, 6, 8]:
            print("grade", grade)
            joyo[grade] = list(fetch_jisho_grade_words(grade))
            print(len(joyo[grade]), "words")

        with open("joyo.json", "wt") as f:
            json.dump(joyo, f, indent=4)
            print("Wrote joyo.json")

    # filter duplicate and remove words not in joyo
    # https://en.wikipedia.org/wiki/Kanji#Total_number_of_kanji
    d = json.load(open("joyo.json"))
    words = set()
    r = {}
    r = {k: [] for k in d}
    for k, v in d.items():
        for i in v:
            if i["kanji"] in words:
                continue
            if len(words) == NUMBER_OF_YOJO_WORDS:
                break
            words.add(i["kanji"])
            r[k].append(i)
    for k, v in r.items():
        print("Grade ", k, len(v), "words")

    with open("joyo_final.json", "wt") as f:
        json.dump(r, f, indent=4)
        print("Wrote joyo_final.json")

    init_kanji_db()
    print(get_kanji(1, 0))
    print(get_kanji(2, 1))


if __name__ == "__main__":
    main()
