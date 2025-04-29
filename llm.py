import requests

from typing import Final


session: Final = requests.Session()
MODEL: Final = "gemma3:1b"
LLM_ENDPOINT: Final = "http://localhost:11434/api/generate"


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
        "prompt": f"""given word '{word_def}', create an example using the word, max 100 chars. Just write the example, do not add anything else, use same language the word belong.
         if input is english, write example in english, if input is japanese, write japanese example""",
        "stream": False,
    }
    msg = session.post(LLM_ENDPOINT, json=payload).json()["response"]
    return msg
