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


if __name__ == "__main__":
    unittest.main()
