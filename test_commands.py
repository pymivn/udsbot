import os
import unittest
from unittest.mock import MagicMock, patch

os.environ.setdefault("BOT_TOKEN", "DUMMY_BOT_TOKEN")
os.environ.setdefault("WEATHER_TOKEN", "DUMMY_WEATHER_TOKEN")

import commands


class TestKeywordExtraction(unittest.TestCase):
    def test_extract_keyword_from_joyo_kanji(self) -> None:
        joyo_msg = (
            "飲: drink, smoke, take\n"
            "イン, -いん, の.む, -の.み\n"
            "https://jisho.org/search/%E9%A3%B2%20%23grade:3"
        )
        self.assertEqual(commands.extract_keyword_from_text(joyo_msg), "飲")

    def test_extract_keyword_from_joyo_kanji_compound(self) -> None:
        joyo_msg = "漢字: China, Sino-\nカン\nhttps://jisho.org"
        self.assertEqual(commands.extract_keyword_from_text(joyo_msg), "漢字")

    def test_extract_keyword_from_jisho_result(self) -> None:
        jisho_msg = (
            "Jisho result for `inryou`\n"
            "Reading: 飲料:いんりょう\n"
            "1. beverage; drink\n"
            "https://jisho.org/word/飲料"
        )
        self.assertEqual(commands.extract_keyword_from_text(jisho_msg), "inryou")

    def test_extract_keyword_from_cambridge_result(self) -> None:
        cam_msg = (
            "Cambridge result for `run`\n"
            "IPA: rən\n"
            "1. (v) move fast\n"
            "https://dictionary.cambridge.org/dictionary/english/run"
        )
        self.assertEqual(commands.extract_keyword_from_text(cam_msg), "run")

    def test_extract_keyword_from_french_result(self) -> None:
        fr_msg = (
            "French dictionary result for `maison`\n"
            "1. (n) a house\n"
            "https://dictionary.cambridge.org/dictionary/french-english/maison"
        )
        self.assertEqual(commands.extract_keyword_from_text(fr_msg), "maison")

    def test_extract_keyword_from_plain_single_word(self) -> None:
        self.assertEqual(commands.extract_keyword_from_text("飲む"), "飲む")
        self.assertEqual(commands.extract_keyword_from_text(" happy "), "happy")

    def test_extract_keyword_from_empty_or_none(self) -> None:
        self.assertEqual(commands.extract_keyword_from_text(""), "")
        self.assertEqual(commands.extract_keyword_from_text("   "), "")


class TestParseXCommand(unittest.TestCase):
    def setUp(self) -> None:
        self.available_cmds = {"ji", "cam", "fr", "lt", "jo", "uds"}

    def test_parse_with_subcmd_and_word(self) -> None:
        parsed = commands.parse_x_command(
            "/x ji inryou", reply_text=None, available_commands=self.available_cmds
        )
        self.assertEqual(parsed.sub_cmd, "ji")
        self.assertEqual(parsed.keyword, "inryou")

    def test_parse_with_direct_word(self) -> None:
        parsed = commands.parse_x_command(
            "/x inryou", reply_text=None, available_commands=self.available_cmds
        )
        self.assertIsNone(parsed.sub_cmd)
        self.assertEqual(parsed.keyword, "inryou")

    def test_parse_with_reply_no_args(self) -> None:
        reply = "飲: drink, smoke, take\nイン, の.む\nhttps://jisho.org"
        parsed = commands.parse_x_command(
            "/x", reply_text=reply, available_commands=self.available_cmds
        )
        self.assertIsNone(parsed.sub_cmd)
        self.assertEqual(parsed.keyword, "飲")

    def test_parse_with_reply_and_subcmd(self) -> None:
        reply = "飲: drink, smoke, take\nイン, の.む\nhttps://jisho.org"
        parsed = commands.parse_x_command(
            "/x ji", reply_text=reply, available_commands=self.available_cmds
        )
        self.assertEqual(parsed.sub_cmd, "ji")
        self.assertEqual(parsed.keyword, "飲")

    def test_parse_empty(self) -> None:
        parsed = commands.parse_x_command(
            "/x", reply_text=None, available_commands=self.available_cmds
        )
        self.assertIsNone(parsed.sub_cmd)
        self.assertEqual(parsed.keyword, "")


class TestDispatcherCommands(unittest.TestCase):
    def setUp(self) -> None:
        self.mock_session = MagicMock()
        self.dispatcher = commands.Dispatcher(session=self.mock_session)

    @patch("commands.send_message")
    @patch("commands.llm.gen_example", return_value="私は水を一杯飲みます。")
    def test_dispatch_x_ai_reply(
        self, mock_gen: MagicMock, mock_send: MagicMock
    ) -> None:
        reply = "飲: drink, smoke, take\nイン, の.む\nhttps://jisho.org"
        self.dispatcher.dispatch_x("/x ai", chat_id=123, from_id=456, reply_text=reply)

        mock_gen.assert_called_once_with("飲")
        mock_send.assert_called_once_with(
            session=self.mock_session,
            chat_id=123,
            text="私は水を一杯飲みます。",
        )

    @patch("commands.send_message")
    @patch("commands.llm.gen_example", return_value="She felt happy.")
    def test_dispatch_x_ai_direct_word(
        self, mock_gen: MagicMock, mock_send: MagicMock
    ) -> None:
        self.dispatcher.dispatch_x("/x ai happy", chat_id=123, from_id=456)

        mock_gen.assert_called_once_with("happy")
        mock_send.assert_called_once_with(
            session=self.mock_session,
            chat_id=123,
            text="She felt happy.",
        )

    @patch("commands.send_message")
    @patch(
        "commands.jp_dict.search_jisho_sentences",
        return_value=[
            commands.jp_dict.JishoSentence(
                japanese="飲料水 は 不足 している。",
                english="Drinking water is in short supply.",
            )
        ],
    )
    def test_dispatch_x_with_subcmd(
        self, mock_search: MagicMock, mock_send: MagicMock
    ) -> None:
        with patch.object(self.dispatcher, "dispatch") as mock_dispatch:
            self.dispatcher.dispatch_x("/x ji 飲料", chat_id=123, from_id=456)

            mock_dispatch.assert_called_once_with("ji 飲料", 123, 456)
            mock_search.assert_called_once_with("飲料", session=self.mock_session)

    @patch("commands.send_message")
    def test_dispatch_x_no_keyword_shows_usage(self, mock_send: MagicMock) -> None:
        self.dispatcher.dispatch_x("/x", chat_id=123, from_id=456, reply_text=None)
        mock_send.assert_called_once()
        self.assertIn("Usage:", mock_send.call_args[1]["text"])

    @patch("commands.send_message")
    @patch(
        "commands.jp_dict.search_jisho_sentences",
        return_value=[
            commands.jp_dict.JishoSentence(
                japanese="車を運転するなら、酒を飲んではいけません。",
                english="If you drive a car, you must not drink alcohol.",
            )
        ],
    )
    def test_dispatch_x_default_reply(
        self, mock_search: MagicMock, mock_send: MagicMock
    ) -> None:
        reply = "飲: drink, smoke, take\nイン, の.む\nhttps://jisho.org"
        self.dispatcher.dispatch_x("/x", chat_id=123, from_id=456, reply_text=reply)

        mock_search.assert_called_once_with("飲", session=self.mock_session)
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[1]["text"]
        self.assertIn("Example sentences for `飲`:", sent_text)
        self.assertIn("車を運転するなら、酒を飲んではいけません。", sent_text)

    @patch("commands.send_message")
    @patch(
        "commands.jp_dict.search_jisho_sentences",
        return_value=[
            commands.jp_dict.JishoSentence(
                japanese="飲料水 は 不足 している。",
                english="Drinking water is in short supply.",
            )
        ],
    )
    def test_dispatch_x_default_direct_word(
        self, mock_search: MagicMock, mock_send: MagicMock
    ) -> None:
        self.dispatcher.dispatch_x("/x 飲料", chat_id=123, from_id=456)

        mock_search.assert_called_once_with("飲料", session=self.mock_session)
        mock_send.assert_called_once()
        sent_text = mock_send.call_args[1]["text"]
        self.assertIn("Example sentences for `飲料`:", sent_text)
        self.assertIn("飲料水 は 不足 している。", sent_text)

    @patch("commands.send_message")
    @patch("commands.jp_dict.search_jisho")
    def test_dispatch_ji_reply(
        self, mock_search: MagicMock, mock_send: MagicMock
    ) -> None:
        mock_search.return_value = {
            "url": "https://jisho.org/word/飲む",
            "reading": "飲:の.む",
            "means": ["to drink"],
        }
        reply = "飲: drink, smoke, take\nイン\nhttps://jisho.org"
        self.dispatcher.dispatch_ji("/ji", chat_id=123, from_id=456, reply_text=reply)

        mock_search.assert_called_once_with("飲")
        mock_send.assert_called_once()
        self.assertIn("Jisho result for `飲`", mock_send.call_args[1]["text"])

    @patch("commands.send_message")
    @patch("commands.dict_lookup.lookup_word")
    def test_dispatch_cam_reply(
        self, mock_lookup: MagicMock, mock_send: MagicMock
    ) -> None:
        mock_lookup.return_value = {
            "url": "https://cambridge.org/run",
            "ipa": "rən",
            "means": ["(v) to run"],
        }
        reply = "Cambridge result for `run`\nIPA: rən\n..."
        self.dispatcher.dispatch_cam("/cam", chat_id=123, from_id=456, reply_text=reply)

        mock_lookup.assert_called_once_with("run")
        mock_send.assert_called_once()
        self.assertIn("Cambridge result for `run`", mock_send.call_args[1]["text"])


if __name__ == "__main__":
    unittest.main()
