import requests

from typing import Final


session: Final = requests.Session()
MODEL: Final = "gemma3:1b"
LLM_ENDPOINT: Final = "http://localhost:11434/api/generate"
SYSTEM_PROMPT_GEN_EXAMPLE: Final = """
You are a multilingual language model specialized in generating clear and natural example sentences.
Given a single word (in English or Japanese), generate a simple and appropriate example sentence that uses the word naturally.
Requirements:

    Detect the input language (English or Japanese) automatically.

    Write the example sentence in the same language as the input word.

    Ensure the sentence is correct, natural, and understandable by beginner to intermediate learners.

    If the word has multiple meanings, choose the most common or basic meaning unless specified otherwise.

    Output only the example sentence, no explanations or extra text.

Examples:

    Input: "happy" → Output: "She felt happy after hearing the good news."

    Input: "学校" → Output: "私は毎日学校に通います。"
"""


def gen_joke() -> str:
    payload = {
        "model": MODEL,
        "prompt": "tell me a joke, add nothing else to the response, no emoji, max 240 chars",
        "stream": False,
        "options": {"temperature": 0.8, "top_p": 0.9},
    }
    msg = session.post(LLM_ENDPOINT, json=payload).json()["response"]
    return msg


def translate(word) -> str:
    if len(word) > 30:
        return f"Word {word} is too long"
    payload = {
        "model": MODEL,
        "prompt": f"""define {word}, with IPA pronounce, short, max 240 chars, add 1 example. Format: word /IPA/ meaning
example:""",
        "stream": False,
    }
    msg = session.post(LLM_ENDPOINT, json=payload).json()["response"]
    return msg


def gen_example(word_def: str) -> str:
    payload = {
        "model": MODEL,
        "prompt": f"""given word '{word_def}', write an example, and a line to translate it to English if it is non English""",
        "stream": False,
    }
    msg = session.post(LLM_ENDPOINT, json=payload).json()["response"]
    return msg
