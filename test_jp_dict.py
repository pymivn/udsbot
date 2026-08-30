import unittest
from unittest.mock import MagicMock, patch

import jp_dict


SAMPLE_TATOEBA_V1_JSON = {
    "data": [
        {
            "id": 5254855,
            "text": "飲む",
            "lang": "jpn",
            "translations": [
                {
                    "id": 2283872,
                    "text": "I drink.",
                    "lang": "eng",
                    "is_direct": True,
                },
                {
                    "id": 3077684,
                    "text": "I'm drinking.",
                    "lang": "eng",
                    "is_direct": False,
                },
            ],
        },
        {
            "id": 12732640,
            "text": "飲んだら？",
            "lang": "jpn",
            "translations": [
                {
                    "id": 9979457,
                    "text": "Why don't you drink?",
                    "lang": "eng",
                    "is_direct": True,
                }
            ],
        },
    ],
    "paging": {"total": 2, "has_next": False},
}


class TestTatoebaV1Sentences(unittest.TestCase):
    def test_parse_tatoeba_sentences_json_success(self) -> None:
        sentences = jp_dict.parse_tatoeba_sentences_json(SAMPLE_TATOEBA_V1_JSON)
        self.assertEqual(len(sentences), 2)
        self.assertEqual(sentences[0].japanese, "飲む")
        self.assertEqual(sentences[0].english, "I drink.")
        self.assertEqual(sentences[1].japanese, "飲んだら？")
        self.assertEqual(sentences[1].english, "Why don't you drink?")

    def test_parse_tatoeba_sentences_json_limit(self) -> None:
        sentences = jp_dict.parse_tatoeba_sentences_json(
            SAMPLE_TATOEBA_V1_JSON, max_results=1
        )
        self.assertEqual(len(sentences), 1)
        self.assertEqual(sentences[0].japanese, "飲む")

    def test_parse_tatoeba_sentences_json_empty(self) -> None:
        sentences = jp_dict.parse_tatoeba_sentences_json({"data": []})
        self.assertEqual(sentences, [])

    def test_parse_tatoeba_sentences_json_no_translations(self) -> None:
        data = {
            "data": [
                {
                    "id": 1,
                    "text": "こんにちは",
                    "translations": [],
                }
            ]
        }
        sentences = jp_dict.parse_tatoeba_sentences_json(data)
        self.assertEqual(sentences, [])

    def test_format_example_sentences_with_results(self) -> None:
        sentences = [
            jp_dict.JishoSentence(
                japanese="飲む",
                english="I drink.",
            ),
            jp_dict.JishoSentence(
                japanese="飲んだら？",
                english="Why don't you drink?",
            ),
        ]
        msg = jp_dict.format_jisho_sentences("飲", sentences)
        self.assertIn("Example sentences for `飲`:", msg)
        self.assertIn("1. 飲む", msg)
        self.assertIn("   I drink.", msg)
        self.assertIn("2. 飲んだら？", msg)
        self.assertIn("   Why don't you drink?", msg)
        self.assertIn(
            "https://tatoeba.org/en/sentences/search?from=jpn&to=eng&query=飲", msg
        )

    def test_format_example_sentences_empty(self) -> None:
        msg = jp_dict.format_jisho_sentences("unknownword", [])
        self.assertEqual(msg, "No example sentences found for `unknownword`.")

    @patch("jp_dict.requests.get")
    def test_search_example_sentences_v1_success(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = SAMPLE_TATOEBA_V1_JSON
        mock_get.return_value = mock_resp

        sentences = jp_dict.search_jisho_sentences("飲", max_results=2)
        self.assertEqual(len(sentences), 2)
        mock_get.assert_called_once()
        self.assertIn("api.tatoeba.org/v1/sentences", mock_get.call_args[0][0])
        params = mock_get.call_args[1]["params"]
        self.assertEqual(params["lang"], "jpn")
        self.assertEqual(params["q"], "飲")
        self.assertEqual(params["sort"], "relevance")
        self.assertEqual(params["trans:lang"], "eng")

    @patch("jp_dict.requests.get")
    def test_search_example_sentences_http_error(self, mock_get: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        sentences = jp_dict.search_jisho_sentences("飲")
        self.assertEqual(sentences, [])


SAMPLE_KANJI_NODE_HTML = """\
<div class="kanji_light_content">
  <div class="debug">0.0029</div>
  <div class="info clearfix">
    <span class="strokes">4 strokes.</span>
    JLPT N5.
    Jōyō kanji, taught in grade 1.
  </div>
  <div class="literal_block">
    <span class="character literal japanese_gothic" lang="ja"><a href="//jisho.org/search/%E6%97%A5%20%23kanji">日</a></span>
  </div>
  <div class="meanings english sense">
    <span>day, </span>
    <span>sun, </span>
    <span>Japan, </span>
    <span>counter for days</span>
  </div>
  <div class="kun readings">
    <span class="type">Kun: </span>
    <span class="japanese_gothic"><a href="//jisho.org/search/foo">ひ</a>、 </span>
    <span class="japanese_gothic"><a href="//jisho.org/search/bar">-か</a></span>
  </div>
  <div class="on readings">
    <span class="type">On: </span>
    <span class="japanese_gothic"><a href="//jisho.org/search/baz">ニチ</a>、 </span>
    <span class="japanese_gothic"><a href="//jisho.org/search/qux">ジツ</a></span>
  </div>
</div>
"""


class TestParseKanjiNode(unittest.TestCase):
    def test_parse_kanji_node_extracts_kanji(self) -> None:
        result = jp_dict.parse_kanji_node(SAMPLE_KANJI_NODE_HTML)
        self.assertEqual(result["kanji"], "日")

    def test_parse_kanji_node_extracts_meaning(self) -> None:
        result = jp_dict.parse_kanji_node(SAMPLE_KANJI_NODE_HTML)
        self.assertEqual(result["meaning"], "day, sun, Japan, counter for days")

    def test_parse_kanji_node_extracts_readings(self) -> None:
        result = jp_dict.parse_kanji_node(SAMPLE_KANJI_NODE_HTML)
        # Readings should include both kun and on readings
        self.assertIn("ひ", result["reading"])
        self.assertIn("ニチ", result["reading"])

    def test_parse_kanji_node_extracts_url(self) -> None:
        result = jp_dict.parse_kanji_node(SAMPLE_KANJI_NODE_HTML)
        self.assertIn("jisho.org", result["url"])
        self.assertIn("kanji", result["url"])


class TestKanjiSerialization(unittest.TestCase):
    def test_serialize_and_deserialize_examples(self) -> None:
        examples = [
            jp_dict.JishoSentence(japanese="日が出る", english="The sun rises"),
            jp_dict.JishoSentence(japanese="日曜日", english="Sunday"),
        ]
        serialized = jp_dict.serialize_examples(examples)
        self.assertIsInstance(serialized, str)
        deserialized = jp_dict.deserialize_examples(serialized)
        self.assertEqual(deserialized, examples)

    def test_deserialize_empty_or_invalid(self) -> None:
        self.assertEqual(jp_dict.deserialize_examples(None), [])
        self.assertEqual(jp_dict.deserialize_examples(""), [])
        self.assertEqual(jp_dict.deserialize_examples("[]"), [])
        self.assertEqual(jp_dict.deserialize_examples("invalid json"), [])


class TestKanjiServiceWithExamples(unittest.TestCase):
    def setUp(self) -> None:
        import sqlite3

        self.conn = sqlite3.connect(":memory:")
        self.conn.execute(
            "CREATE TABLE kanji_chars (id INTEGER PRIMARY KEY, kanji text, meaning text, reading text, grade text, url text, examples text);"
        )
        examples_json = jp_dict.serialize_examples(
            [jp_dict.JishoSentence(japanese="日が出る", english="The sun rises")]
        )
        self.conn.execute(
            "INSERT INTO kanji_chars(kanji, meaning, reading, grade, url, examples) VALUES (?, ?, ?, ?, ?, ?)",
            (
                "日",
                "day, sun",
                "Kun: ひ On: ニチ",
                "1",
                "jisho.org/search/日",
                examples_json,
            ),
        )
        self.conn.execute(
            "INSERT INTO kanji_chars(kanji, meaning, reading, grade, url, examples) VALUES (?, ?, ?, ?, ?, ?)",
            ("月", "moon, month", "Kun: つき On: ゲツ", "1", "jisho.org/search/月", ""),
        )
        self.conn.commit()
        self.service = jp_dict.KanjiService(self.conn)

    def tearDown(self) -> None:
        self.conn.close()

    def test_get_kanji_returns_examples(self) -> None:
        k = self.service.get_kanji(grade=1, nth=1)
        self.assertEqual(k.char, "日")
        self.assertEqual(k.meaning, "day, sun")
        self.assertEqual(len(k.examples), 1)
        self.assertEqual(k.examples[0].japanese, "日が出る")
        self.assertEqual(k.examples[0].english, "The sun rises")

    def test_get_kanji_without_examples(self) -> None:
        k = self.service.get_kanji(grade=1, nth=2)
        self.assertEqual(k.char, "月")
        self.assertEqual(k.examples, [])

    def test_find_by_char(self) -> None:
        k = self.service.find_by_char("日")
        self.assertIsNotNone(k)
        if k:
            self.assertEqual(k.char, "日")
            self.assertEqual(len(k.examples), 1)

        none_k = self.service.find_by_char("猫")
        self.assertIsNone(none_k)

    def test_save_examples(self) -> None:
        new_examples = [jp_dict.JishoSentence(japanese="満月", english="full moon")]
        self.service.save_examples("月", new_examples)
        k = self.service.find_by_char("月")
        self.assertIsNotNone(k)
        if k:
            self.assertEqual(len(k.examples), 1)
            self.assertEqual(k.examples[0].japanese, "満月")

    def test_get_examples_for_text_direct(self) -> None:
        examples = self.service.get_examples_for_text("日")
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0].japanese, "日が出る")

    def test_get_examples_for_text_compound(self) -> None:
        # "日曜日" contains "日" and "月" (which has no examples initially)
        examples = self.service.get_examples_for_text("日曜日")
        self.assertEqual(len(examples), 1)
        self.assertEqual(examples[0].japanese, "日が出る")

    def test_get_examples_for_text_none_found(self) -> None:
        examples = self.service.get_examples_for_text("猫")
        self.assertEqual(examples, [])

    def test_dump_kanji_db_to_dict(self) -> None:
        data = jp_dict.dump_kanji_db_to_dict(self.service)
        self.assertIn("1", data)
        self.assertEqual(len(data["1"]), 2)
        self.assertEqual(data["1"][0]["kanji"], "日")
        self.assertEqual(len(data["1"][0]["examples"]), 1)


class TestFormatJishoResult(unittest.TestCase):
    def test_format_jisho_result_with_examples(self) -> None:
        sentences = [
            jp_dict.JishoSentence(japanese="水を飲む。", english="Drink water."),
            jp_dict.JishoSentence(japanese="薬を飲む。", english="Take medicine."),
        ]
        result = jp_dict.format_jisho_result(
            keyword="飲む",
            reading="飲む:のむ",
            meanings=["to drink", "to swallow"],
            url="https://jisho.org/word/飲む",
            sentences=sentences,
        )
        self.assertIn("Jisho result for `飲む`", result)
        self.assertIn("Reading: 飲む:のむ", result)
        self.assertIn("1. to drink", result)
        self.assertIn("2. to swallow", result)
        self.assertIn("Examples:", result)
        self.assertIn("1. 水を飲む。", result)
        self.assertIn("   Drink water.", result)
        self.assertIn("2. 薬を飲む。", result)
        self.assertIn("   Take medicine.", result)
        self.assertIn("https://jisho.org/word/飲む", result)

    def test_format_jisho_result_without_examples(self) -> None:
        result = jp_dict.format_jisho_result(
            keyword="飲む",
            reading="飲む:のむ",
            meanings=["to drink"],
            url="https://jisho.org/word/飲む",
            sentences=[],
        )
        self.assertIn("Jisho result for `飲む`", result)
        self.assertNotIn("Examples:", result)
        self.assertIn("https://jisho.org/word/飲む", result)


class TestFormatKanji(unittest.TestCase):
    def test_format_kanji_with_examples(self) -> None:
        k = jp_dict.Kanji(
            char="日",
            meaning="day, sun",
            reading="Kun: ひ On: ニチ",
            grade="1",
            url="https://jisho.org/search/日%20%23grade:1",
            examples=[
                jp_dict.JishoSentence(japanese="日が出る", english="The sun rises")
            ],
        )
        msg = jp_dict.format_kanji(k)
        self.assertIn("日: day, sun", msg)
        self.assertIn("Kun: ひ On: ニチ", msg)
        self.assertIn("Examples:", msg)
        self.assertIn("1. 日が出る", msg)
        self.assertIn("   The sun rises", msg)
        self.assertIn("https://jisho.org/search/日%20%23grade:1", msg)

    def test_format_kanji_without_examples(self) -> None:
        k = jp_dict.Kanji(
            char="月",
            meaning="moon, month",
            reading="Kun: つき On: ゲツ",
            grade="1",
            url="https://jisho.org/search/月%20%23grade:1",
            examples=[],
        )
        msg = jp_dict.format_kanji(k)
        self.assertIn("月: moon, month", msg)
        self.assertIn("Kun: つき On: ゲツ", msg)
        self.assertNotIn("Examples:", msg)
        self.assertIn("https://jisho.org/search/月%20%23grade:1", msg)


class TestParseJishoWordJson(unittest.TestCase):
    def test_parse_jisho_word_json_success(self) -> None:
        sample_json = {
            "data": [
                {
                    "slug": "飲む",
                    "japanese": [{"word": "飲む", "reading": "のむ"}],
                    "senses": [{"english_definitions": ["to drink", "to gulp"]}],
                }
            ]
        }
        res = jp_dict.parse_jisho_word_json(sample_json)
        self.assertEqual(res["url"], "https://jisho.org/word/飲む")
        self.assertEqual(res["reading"], "飲む:のむ")
        self.assertEqual(res["means"], ["to drink, to gulp"])

    def test_parse_jisho_word_json_empty(self) -> None:
        res = jp_dict.parse_jisho_word_json({"data": []})
        self.assertEqual(res["url"], "")
        self.assertEqual(res["reading"], "")
        self.assertEqual(res["means"], [])


class TestEnrichKanjiDb(unittest.TestCase):
    @patch("jp_dict.fetch_kanji_examples")
    def test_enrich_kanji_db_with_tatoeba(self, mock_fetch: MagicMock) -> None:
        import sqlite3

        mock_fetch.return_value = [
            jp_dict.JishoSentence(japanese="満月", english="full moon")
        ]
        conn = sqlite3.connect(":memory:")
        conn.execute(
            "CREATE TABLE kanji_chars (id INTEGER PRIMARY KEY, kanji text, meaning text, reading text, grade text, url text, examples text);"
        )
        conn.execute(
            "INSERT INTO kanji_chars(kanji, meaning, reading, grade, url, examples) VALUES (?, ?, ?, ?, ?, ?)",
            ("月", "moon", "つき", "1", "url", ""),
        )
        conn.commit()
        service = jp_dict.KanjiService(conn)
        count = jp_dict.enrich_kanji_db_with_tatoeba(service, limit=1)
        self.assertEqual(count, 1)
        k = service.find_by_char("月")
        self.assertIsNotNone(k)
        if k:
            self.assertEqual(len(k.examples), 1)
            self.assertEqual(k.examples[0].japanese, "満月")
        conn.close()


if __name__ == "__main__":
    unittest.main()
