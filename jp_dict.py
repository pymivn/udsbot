import os
import json
import time
import sqlite3
from dataclasses import dataclass

import requests
import requests_html


# https://jisho.org/robots.txt
DELAY = 10

NUMBER_OF_YOJO_WORDS = 2136


def search_jisho(word):
    resp = requests.get(f"https://jisho.org/api/v1/search/words?keyword={word}").json()
    data = resp["data"]
    for result in data:
        # return only the first result if exists
        url = "https://jisho.org/word/{}".format(result["slug"])
        reading = ", ".join(
            i.get("word", "") + ":" + i.get("reading", "no reading")
            for i in result["japanese"]
        )
        means = [", ".join(s["english_definitions"]) for s in result["senses"]]

        res = {
            "url": url,
            "reading": reading,
            "means": means,
        }
        return res
    return {"url": "", "reading": "", "means": ""}


def fetch_jisho_grade_words(grade=1):
    sess = requests_html.HTMLSession()

    page = 1
    while True:
        url = "https://fetch_jisho_grade_words.org/search/%23kanji%20%23grade:{}?page={}".format(
            grade, page
        )

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


def init_kanji_db(dbpath):
    if os.path.exists(dbpath):
        print("dbpath already exists, skip")
        return

    json_path = os.path.join(os.path.dirname(__file__), "joyo_final.json")
    ws = json.load(open(json_path))

    conn = sqlite3.connect(dbpath)

    conn.execute(
        "CREATE TABLE IF NOT EXISTS kanji_chars (id INTEGER PRIMARY KEY, kanji text, meaning text, reading text, grade text, url text);"
    )
    conn.executemany(
        "INSERT INTO kanji_chars(kanji, meaning, reading, grade, url) VALUES (?, ?, ?, ?, ?)",
        (
            (i["kanji"], i["meaning"], i["reading"], grade, i["url"])
            for grade, v in ws.items()
            for i in v
        ),
    )
    conn.commit()

    print("Initialized db ", dbpath)
    return conn


def get_db(dbpath):
    return sqlite3.connect(dbpath)


@dataclass
class Kanji:
    char: str
    meaning: str
    reading: str
    grade: str
    url: str


class KanjiService:
    def __init__(self, conn):
        self.db = conn

    def chars_count_by_grade(self) -> dict[str, int]:
        return dict(
            self.db.execute("SELECT grade, count(*) from kanji_chars group by grade")
        )

    def get_kanji(self, grade=2, nth=1) -> Kanji:
        grades_chars = self.chars_count_by_grade()
        if str(grade) not in grades_chars:
            grade = 2
        # user count from 1, db count from 0
        if nth >= 1:
            nth = nth - 1

        nth = nth % grades_chars[str(grade)]

        r = self.db.execute(
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

    conn = init_kanji_db(dbpath="yojo.db")
    ks = KanjiService(conn)
    print(ks.get_kanji(1, 0))
    print(ks.get_kanji(2, 1))


if __name__ == "__main__":
    main()
