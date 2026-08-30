import unittest
from unittest.mock import MagicMock, patch

import llm


class TestExtractChatText(unittest.TestCase):
    def test_extract_success(self) -> None:
        resp = {"choices": [{"message": {"content": "Hello world"}}]}
        self.assertEqual(llm.extract_chat_text(resp), "Hello world")

    def test_extract_no_choices_key(self) -> None:
        resp = {"error": {"message": "API key invalid"}}
        self.assertEqual(llm.extract_chat_text(resp), "")

    def test_extract_empty_choices(self) -> None:
        resp: dict = {"choices": []}
        self.assertEqual(llm.extract_chat_text(resp), "")

    def test_extract_no_message(self) -> None:
        resp = {"choices": [{"finish_reason": "stop"}]}
        self.assertEqual(llm.extract_chat_text(resp), "")

    def test_extract_empty_content(self) -> None:
        resp = {"choices": [{"message": {"content": ""}}]}
        self.assertEqual(llm.extract_chat_text(resp), "")

    def test_extract_strips_whitespace(self) -> None:
        resp = {"choices": [{"message": {"content": "  hello  \n"}}]}
        self.assertEqual(llm.extract_chat_text(resp), "hello")


class TestParseModelList(unittest.TestCase):
    def test_default_models_when_none_or_empty(self) -> None:
        self.assertEqual(llm.parse_model_list(None), llm.DEFAULT_FALLBACK_MODELS)
        self.assertEqual(llm.parse_model_list(""), llm.DEFAULT_FALLBACK_MODELS)
        self.assertEqual(llm.parse_model_list("   "), llm.DEFAULT_FALLBACK_MODELS)

    def test_single_model(self) -> None:
        self.assertEqual(
            llm.parse_model_list("liquid/lfm-2.5-2.6b:free"),
            ["liquid/lfm-2.5-2.6b:free"],
        )

    def test_multiple_comma_separated_models(self) -> None:
        raw = "google/gemma-4-31b-it:free, liquid/lfm-2.5-2.6b:free, meta-llama/llama-3.3-70b-instruct:free"
        expected = [
            "google/gemma-4-31b-it:free",
            "liquid/lfm-2.5-2.6b:free",
            "meta-llama/llama-3.3-70b-instruct:free",
        ]
        self.assertEqual(llm.parse_model_list(raw), expected)

    def test_filter_empty_entries(self) -> None:
        raw = "  model1 , ,  model2  "
        self.assertEqual(llm.parse_model_list(raw), ["model1", "model2"])


class TestBuildChatPayload(unittest.TestCase):
    def test_payload_structure(self) -> None:
        models = ["model1", "model2"]
        payload = llm.build_chat_payload(models, "system text", "user text")
        self.assertEqual(payload["models"], models)
        self.assertEqual(
            payload["messages"],
            [
                {"role": "system", "content": "system text"},
                {"role": "user", "content": "user text"},
            ],
        )


class TestChunkModels(unittest.TestCase):
    def test_chunk_models_empty(self) -> None:
        self.assertEqual(llm._chunk_models([]), [])

    def test_chunk_models_less_than_chunk_size(self) -> None:
        self.assertEqual(llm._chunk_models(["m1", "m2"]), [["m1", "m2"]])

    def test_chunk_models_exact_chunk_size(self) -> None:
        self.assertEqual(llm._chunk_models(["m1", "m2", "m3"]), [["m1", "m2", "m3"]])

    def test_chunk_models_multiple_chunks(self) -> None:
        models = ["m1", "m2", "m3", "m4", "m5", "m6"]
        expected = [["m1", "m2", "m3"], ["m4", "m5", "m6"]]
        self.assertEqual(llm._chunk_models(models, chunk_size=3), expected)


class TestMergeFallbackModels(unittest.TestCase):
    def test_merge_includes_openrouter_free(self) -> None:
        primary = ["google/gemma-4-31b-it:free", "liquid/lfm-2.5-2.6b:free"]
        result = llm.merge_fallback_models(primary)
        expected = [
            "google/gemma-4-31b-it:free",
            "liquid/lfm-2.5-2.6b:free",
            "openrouter/free",
        ]
        self.assertEqual(result, expected)

    def test_merge_already_contains_openrouter_free(self) -> None:
        primary = ["google/gemma-4-31b-it:free", "openrouter/free"]
        result = llm.merge_fallback_models(primary)
        expected = ["google/gemma-4-31b-it:free", "openrouter/free"]
        self.assertEqual(result, expected)

    def test_merge_without_router_fallback(self) -> None:
        primary = ["google/gemma-4-31b-it:free"]
        result = llm.merge_fallback_models(primary, include_router_fallback=False)
        expected = ["google/gemma-4-31b-it:free"]
        self.assertEqual(result, expected)


class TestChatCompletion(unittest.TestCase):
    @patch("llm.session")
    def test_chat_completion_primary_success(self, mock_session: MagicMock) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "Test response"}}]
        }
        mock_session.post.return_value = mock_resp

        res = llm._chat_completion("sys", "user")
        self.assertEqual(res, "Test response")
        mock_session.post.assert_called()
        self.assertEqual(mock_session.post.call_args.kwargs["timeout"], 30)

    @patch("llm.session")
    def test_chat_completion_fallback_to_second_batch(
        self, mock_session: MagicMock
    ) -> None:
        fail_resp = MagicMock()
        fail_resp.json.return_value = {"error": "Batch 1 rate limited"}

        success_resp = MagicMock()
        success_resp.json.return_value = {
            "choices": [{"message": {"content": "Batch 2 response"}}]
        }

        mock_session.post.side_effect = [fail_resp, success_resp]

        res = llm._chat_completion("sys", "user")
        self.assertEqual(res, "Batch 2 response")
        self.assertEqual(mock_session.post.call_count, 2)

    @patch("llm.session")
    def test_chat_completion_all_fail(self, mock_session: MagicMock) -> None:
        mock_session.post.side_effect = Exception("Connection error")

        res = llm._chat_completion("sys", "user")
        self.assertEqual(res, "")


if __name__ == "__main__":
    unittest.main()
