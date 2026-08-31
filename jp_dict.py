import os
import json
import time
import sqlite3
from dataclasses import dataclass, field
from typing import Any

import requests


# https://jisho.org/robots.txt
DELAY = 10

NUMBER_OF_YOJO_WORDS = 2136


@dataclass(frozen=True)
class JishoSentence:
    japanese: str
    english: str


def serialize_examples(
    examples: list[JishoSentence] | list[dict[str, str]] | list[Any],
) -> str:
    """Pure function: serialize list of JishoSentence dataclasses or dicts to JSON string."""
    items: list[dict[str, str]] = []
    for s in examples:
        if isinstance(s, JishoSentence):
            items.append({"japanese": s.japanese, "english": s.english})
        elif isinstance(s, dict):
            jp = str(s.get("japanese", "")).strip()
            en = str(s.get("english", "")).strip()
            if jp and en:
                items.append({"japanese": jp, "english": en})
    return json.dumps(items)


def deserialize_examples(raw_text: str | None) -> list[JishoSentence]:
    """Pure function: deserialize JSON string to list of JishoSentence dataclasses."""
    if not raw_text or not raw_text.strip():
        return []
    try:
        data = json.loads(raw_text)
        if not isinstance(data, list):
            return []
        results: list[JishoSentence] = []
        for item in data:
            if isinstance(item, dict):
                jp = str(item.get("japanese", "")).strip()
                en = str(item.get("english", "")).strip()
                if jp and en:
                    results.append(JishoSentence(japanese=jp, english=en))
        return results
    except Exception:
        return []


def _find_english_translation(translations: list) -> str:
    """Find the first English translation text from a Tatoeba v1 translations list."""
    fallback = ""
    for trans in translations:
        if not isinstance(trans, dict):
            continue
        text = str(trans.get("text", "")).strip()
        if not text:
            continue
        if trans.get("lang") == "eng":
            return text
        if not fallback:
            fallback = text
    return fallback


def parse_tatoeba_sentences_json(
    data: dict, max_results: int = 3
) -> list[JishoSentence]:
    results: list[JishoSentence] = []
    raw_val = data.get("data", [])
    if not isinstance(raw_val, list):
        return results

    for item in raw_val:
        if not isinstance(item, dict):
            continue
        jp_text = str(item.get("text", "")).strip()
        if not jp_text:
            continue

        translations = item.get("translations", [])
        en_text = (
            _find_english_translation(translations)
            if isinstance(translations, list)
            else ""
        )
        if not en_text:
            continue

        results.append(JishoSentence(japanese=jp_text, english=en_text))
        if len(results) >= max_results:
            break

    return results


def search_jisho_sentences(
    keyword: str, max_results: int = 3, session: requests.Session | None = None
) -> list[JishoSentence]:
    url = "https://api.tatoeba.org/v1/sentences"
    params: dict[str, str | int] = {
        "lang": "jpn",
        "q": keyword,
        "sort": "relevance",
        "trans:lang": "eng",
        "limit": max_results,
    }
    headers = {"User-Agent": "udsbot/1.0"}
    client = session or requests
    for attempt in range(5):
        try:
            resp = client.get(url, params=params, headers=headers, timeout=15)
            if resp.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
                continue
            if resp.status_code != 200:
                return []
            data = resp.json()
            return parse_tatoeba_sentences_json(data, max_results=max_results)
        except Exception:
            if attempt == 4:
                return []
            time.sleep(1.0)
    return []


def format_jisho_sentences(keyword: str, sentences: list[JishoSentence]) -> str:
    if not sentences:
        return f"No example sentences found for `{keyword}`."

    lines = [f"Example sentences for `{keyword}`:"]
    for idx, s in enumerate(sentences, start=1):
        lines.append(f"{idx}. {s.japanese}\n   {s.english}")

    url = f"https://tatoeba.org/en/sentences/search?from=jpn&to=eng&query={keyword}"
    lines.append(url)
    return "\n".join(lines)


def _extract_japanese_reading(japanese_list: list) -> str:
    """Extract comma-separated word:reading pairs from Jisho japanese list."""
    reading_parts: list[str] = []
    for item in japanese_list:
        if not isinstance(item, dict):
            continue
        word = str(item.get("word", ""))
        reading = str(item.get("reading", "no reading"))
        reading_parts.append(f"{word}:{reading}")
    return ", ".join(reading_parts)


def _extract_senses_meanings(senses: list) -> list[str]:
    """Extract English definitions list from Jisho senses list."""
    means: list[str] = []
    for sense in senses:
        if not isinstance(sense, dict):
            continue
        defs = sense.get("english_definitions", [])
        if isinstance(defs, list):
            means.append(", ".join(defs))
    return means


def parse_jisho_word_json(data: dict) -> dict[str, Any]:
    """Pure function: parse Jisho API word search response JSON into dictionary."""
    results = data.get("data", [])
    if not isinstance(results, list):
        return {"url": "", "reading": "", "means": []}

    for result in results:
        if not isinstance(result, dict):
            continue
        url = "https://jisho.org/word/{}".format(result.get("slug", ""))
        raw_jp = result.get("japanese", [])
        reading = _extract_japanese_reading(raw_jp) if isinstance(raw_jp, list) else ""

        raw_senses = result.get("senses", [])
        means = (
            _extract_senses_meanings(raw_senses) if isinstance(raw_senses, list) else []
        )

        return {
            "url": url,
            "reading": reading,
            "means": means,
        }
    return {"url": "", "reading": "", "means": []}


def search_jisho(word: str) -> dict:
    resp = requests.get(f"https://jisho.org/api/v1/search/words?keyword={word}").json()
    return parse_jisho_word_json(resp)


def format_jisho_result(
    keyword: str,
    reading: str,
    meanings: list[str],
    url: str,
    sentences: list[JishoSentence] | None = None,
    max_meanings: int = 5,
    max_examples: int = 2,
) -> str:
    """Pure function: format Jisho word lookup result with definitions and optional Tatoeba examples."""
    lines: list[str] = [f"Jisho result for `{keyword}`"]
    if reading:
        lines.append(f"Reading: {reading}")

    EACH_MEANING_LIMIT = 160
    for idx, meaning in enumerate(meanings):
        if idx == max_meanings:
            lines.append("...")
            break
        if len(meaning) > EACH_MEANING_LIMIT:
            meaning = f"{meaning[:EACH_MEANING_LIMIT]}..."
        lines.append(f"{idx + 1}. {meaning}")

    if sentences:
        lines.append("\nExamples:")
        for idx, s in enumerate(sentences[:max_examples], start=1):
            lines.append(f"{idx}. {s.japanese}\n   {s.english}")

    if url:
        lines.append(url)

    return "\n".join(lines)


def parse_kanji_node(html_text: str) -> dict[str, str]:
    """Pure function: parse a kanji_light_content HTML fragment into structured data."""
    import lxml.html

    doc = lxml.html.fromstring(html_text)

    kanji_el = doc.xpath('.//div[@class="literal_block"]//a')
    kanji = kanji_el[0].text_content().strip() if kanji_el else ""

    href = kanji_el[0].get("href", "") if kanji_el else ""
    url = href.lstrip("/")

    meaning_spans = doc.xpath('.//div[contains(@class, "meanings")]//span')
    meaning = "".join(s.text_content() for s in meaning_spans).strip().rstrip(",")

    reading_parts: list[str] = []
    for div in doc.xpath('.//div[contains(@class, "readings")]'):
        for span in div.xpath('.//span[contains(@class, "japanese_gothic")]'):
            reading_parts.append(span.text_content().strip().rstrip("、").strip())

    return {
        "kanji": kanji,
        "meaning": meaning,
        "reading": " ".join(reading_parts),
        "url": url,
    }


def fetch_jisho_grade_words(grade: int = 1):
    import lxml.html

    page = 1
    while True:
        url = "https://jisho.org/search/%23kanji%20%23grade:{}?page={}".format(
            grade, page
        )

        resp = requests.get(url, timeout=30)
        if resp.status_code != 200:
            return

        doc = lxml.html.fromstring(resp.text)
        nodes = doc.xpath('//div[@class="kanji_light_content"]')
        if not nodes:
            return

        for node in nodes:
            import lxml.html as lh

            node_html = lh.tostring(node, encoding="unicode")
            yield parse_kanji_node(node_html)

        page += 1
        time.sleep(DELAY)


def init_kanji_db(dbpath: str) -> sqlite3.Connection:
    if os.path.exists(dbpath):
        conn = sqlite3.connect(dbpath)
        return conn

    json_path = os.path.join(os.path.dirname(__file__), "joyo_final.json")
    ws = json.load(open(json_path))

    conn = sqlite3.connect(dbpath)

    conn.execute(
        "CREATE TABLE IF NOT EXISTS kanji_chars (id INTEGER PRIMARY KEY, kanji text, meaning text, reading text, grade text, url text, examples text);"
    )
    conn.executemany(
        "INSERT INTO kanji_chars(kanji, meaning, reading, grade, url, examples) VALUES (?, ?, ?, ?, ?, ?)",
        (
            (
                i["kanji"],
                i["meaning"],
                i["reading"],
                str(grade),
                i["url"],
                serialize_examples(i.get("examples", []))
                if isinstance(i.get("examples"), list)
                else "",
            )
            for grade, v in ws.items()
            for i in v
        ),
    )
    conn.commit()

    print("Initialized db ", dbpath)
    return conn


def get_db(dbpath: str) -> sqlite3.Connection:
    return sqlite3.connect(dbpath)


@dataclass
class Kanji:
    char: str
    meaning: str
    reading: str
    grade: str
    url: str
    examples: list[JishoSentence] = field(default_factory=list)


def format_kanji(k: Kanji, max_examples: int = 2) -> str:
    """Pure function: format Kanji dataclass with meaning, reading, and optional examples."""
    lines: list[str] = [f"{k.char}: {k.meaning}", k.reading]
    if k.examples:
        lines.append("Examples:")
        for idx, s in enumerate(k.examples[:max_examples], start=1):
            lines.append(f"{idx}. {s.japanese}\n   {s.english}")
    if k.url:
        lines.append(k.url)
    return "\n".join(lines)


def fetch_kanji_examples(
    kanji_char: str,
    max_results: int = 2,
    session: requests.Session | None = None,
) -> list[JishoSentence]:
    """Fetch Tatoeba example sentences for a kanji character."""
    return search_jisho_sentences(kanji_char, max_results=max_results, session=session)


class KanjiService:
    def __init__(self, conn: sqlite3.Connection):
        self.db = conn

    def chars_count_by_grade(self) -> dict[str, int]:
        return dict(
            self.db.execute("SELECT grade, count(*) from kanji_chars group by grade")
        )

    def get_kanji(self, grade: int = 2, nth: int = 1) -> Kanji:
        grades_chars = self.chars_count_by_grade()
        if str(grade) not in grades_chars:
            grade = 2
        # user count from 1, db count from 0
        if nth >= 1:
            nth = nth - 1

        nth = nth % grades_chars[str(grade)]

        r = self.db.execute(
            "SELECT kanji, meaning, reading, grade, url, examples FROM kanji_chars WHERE grade=? LIMIT 1 OFFSET ? ",
            (str(grade), nth),
        ).fetchone()
        url = "{}%20%23grade:{}".format(r[4], grade)
        examples = deserialize_examples(r[5]) if len(r) > 5 else []
        return Kanji(
            char=r[0],
            meaning=r[1],
            reading=r[2],
            grade=r[3],
            url=url,
            examples=examples,
        )

    def find_by_char(self, char: str) -> Kanji | None:
        r = self.db.execute(
            "SELECT kanji, meaning, reading, grade, url, examples FROM kanji_chars WHERE kanji=? LIMIT 1",
            (char,),
        ).fetchone()
        if not r:
            return None
        url = "{}%20%23grade:{}".format(r[4], r[3])
        examples = deserialize_examples(r[5]) if len(r) > 5 else []
        return Kanji(
            char=r[0],
            meaning=r[1],
            reading=r[2],
            grade=r[3],
            url=url,
            examples=examples,
        )

    def save_examples(self, char: str, examples: list[JishoSentence]) -> None:
        examples_json = serialize_examples(examples)
        self.db.execute(
            "UPDATE kanji_chars SET examples=? WHERE kanji=?",
            (examples_json, char),
        )
        self.db.commit()

    def get_examples_for_text(
        self, text: str, max_results: int = 2
    ) -> list[JishoSentence]:
        """Retrieve cached Tatoeba example sentences for kanji character(s) in text from SQLite DB."""
        if not text or not text.strip():
            return []

        # First try direct match
        direct = self.find_by_char(text.strip())
        if direct and direct.examples:
            return direct.examples[:max_results]

        # Try finding kanji characters contained in the text
        results: list[JishoSentence] = []
        seen: set[str] = set()
        for ch in text:
            if ch in seen:
                continue
            seen.add(ch)
            k = self.find_by_char(ch)
            if k and k.examples:
                for s in k.examples:
                    if s not in results:
                        results.append(s)
                    if len(results) >= max_results:
                        return results
        return results


def dump_kanji_db_to_dict(service: KanjiService) -> dict[str, list[dict[str, Any]]]:
    """Dump all kanji from DB to dictionary grouped by grade."""
    rows = service.db.execute(
        "SELECT kanji, meaning, reading, grade, url, examples FROM kanji_chars ORDER BY id ASC"
    ).fetchall()
    result: dict[str, list[dict[str, Any]]] = {}
    for kanji, meaning, reading, grade, url, examples_raw in rows:
        examples = deserialize_examples(examples_raw)
        entry: dict[str, Any] = {
            "kanji": kanji,
            "meaning": meaning,
            "reading": reading,
            "url": url,
            "examples": [
                {"japanese": s.japanese, "english": s.english} for s in examples
            ],
        }
        grade_str = str(grade)
        if grade_str not in result:
            result[grade_str] = []
        result[grade_str].append(entry)
    return result


def dump_kanji_db_to_json(
    service: KanjiService, output_path: str = "joyo_final.json"
) -> None:
    """Save all kanji and their examples from DB to JSON file."""
    data = dump_kanji_db_to_dict(service)
    with open(output_path, "wt") as f:
        json.dump(data, f, indent=4)


def enrich_kanji_db_with_tatoeba(
    service: KanjiService,
    grade: int | None = None,
    limit: int | None = None,
    max_workers: int = 2,
    session: requests.Session | None = None,
) -> int:
    """Populate missing examples for kanji in the database using Tatoeba API."""
    query = "SELECT kanji FROM kanji_chars WHERE examples IS NULL OR examples = '' OR examples = '[]'"
    params: list[Any] = []
    if grade is not None:
        query += " AND grade = ?"
        params.append(str(grade))
    if limit is not None and limit > 0:
        query += " LIMIT ?"
        params.append(limit)

    rows = service.db.execute(query, params).fetchall()
    if not rows:
        return 0

    chars = [char for (char,) in rows]
    count = 0

    if max_workers <= 1:
        s = session or requests.Session()
        for char in chars:
            sentences = fetch_kanji_examples(char, max_results=2, session=s)
            service.save_examples(char, sentences)
            count += 1
            if count % 20 == 0 or count == len(chars):
                print(f"Enriched {count}/{len(chars)} kanji entries...")
            time.sleep(0.3)
    else:
        from concurrent.futures import ThreadPoolExecutor, as_completed

        def fetch_one(char: str) -> tuple[str, list[JishoSentence]]:
            s = requests.Session()
            time.sleep(0.25)
            sentences = fetch_kanji_examples(char, max_results=2, session=s)
            return char, sentences

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_one, char): char for char in chars}
            for future in as_completed(futures):
                char, sentences = future.result()
                service.save_examples(char, sentences)
                count += 1
                if count % 50 == 0 or count == len(chars):
                    print(f"Enriched {count}/{len(chars)} kanji entries...")

    return count


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Jisho & Tatoeba kanji dataset and DB management."
    )
    parser.add_argument(
        "--enrich",
        action="store_true",
        help="Enrich SQLite DB and joyo_final.json with Tatoeba example sentences.",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Enrich ALL remaining kanji in the database.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Maximum number of kanji to enrich in this run (default: 50).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of concurrent worker threads (default: 2).",
    )
    parser.add_argument(
        "--grade",
        type=int,
        default=None,
        help="Specific grade level (1-8) to enrich.",
    )
    parser.add_argument(
        "--db",
        type=str,
        default="yojo.db",
        help="SQLite database path (default: yojo.db).",
    )
    parser.add_argument(
        "--save-json",
        action="store_true",
        default=True,
        help="Save enriched data back to joyo_final.json (default: True).",
    )

    args = parser.parse_args()

    conn = init_kanji_db(dbpath=args.db)
    ks = KanjiService(conn)

    if args.enrich or args.all:
        eff_limit = None if args.all or args.limit <= 0 else args.limit
        print(
            f"Enriching kanji DB ({args.db}) with Tatoeba examples (limit={eff_limit}, grade={args.grade}, workers={args.workers})..."
        )
        enriched = enrich_kanji_db_with_tatoeba(
            ks, grade=args.grade, limit=eff_limit, max_workers=args.workers
        )
        print(f"Enriched {enriched} kanji entries with example sentences.")
        if args.save_json:
            dump_kanji_db_to_json(ks, output_path="joyo_final.json")
            print("Updated joyo_final.json with enriched examples.")
    else:
        print("Kanji DB sample lookup:")
        print(format_kanji(ks.get_kanji(1, 1)))


if __name__ == "__main__":
    main()
