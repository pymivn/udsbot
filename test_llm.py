import unittest

import llm


class TestExtractGeminiText(unittest.TestCase):
    def test_extract_success(self) -> None:
        resp = {"candidates": [{"content": {"parts": [{"text": "Hello world"}]}}]}
        self.assertEqual(llm.extract_gemini_text(resp), "Hello world")

    def test_extract_no_candidates_key(self) -> None:
        resp = {"error": {"message": "API key invalid"}}
        self.assertEqual(llm.extract_gemini_text(resp), "")

    def test_extract_empty_candidates(self) -> None:
        resp: dict = {"candidates": []}
        self.assertEqual(llm.extract_gemini_text(resp), "")

    def test_extract_blocked_no_content(self) -> None:
        resp = {
            "candidates": [{"finishReason": "SAFETY"}],
            "promptFeedback": {"blockReason": "SAFETY"},
        }
        self.assertEqual(llm.extract_gemini_text(resp), "")

    def test_extract_empty_parts(self) -> None:
        resp: dict = {"candidates": [{"content": {"parts": []}}]}
        self.assertEqual(llm.extract_gemini_text(resp), "")


if __name__ == "__main__":
    unittest.main()
