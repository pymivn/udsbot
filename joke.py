import requests


def gen_joke() -> str:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": "gemma3:1b",
        "prompt": "tell me a joke, add nothing else to the response, no emoji, max 240 chars",
        "stream": False,
        "options": {"temperature": 0.8, "top_p": 0.9},
    }
    msg = requests.post(url, json=payload).json()["response"]
    return msg
