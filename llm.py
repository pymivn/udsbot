import logging
import requests
import os
from typing import Final

logger = logging.getLogger(__name__)


session: Final = requests.Session()


# Local Ollama
MODEL: Final = "gemma3:1b"
LLM_ENDPOINT: Final = "http://localhost:11434/api/generate"

# OpenRouter API (OpenAI-compatible)
DEFAULT_FALLBACK_MODELS: Final[list[str]] = [
    "google/gemma-4-31b-it:free",
    "liquid/lfm-2.5-2.6b:free",
    "google/gemma-4-26b-a4b-it:free",
    "minimax/minimax-m3:free",
    "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
    "minimax/minimax-m2.7:free",
]
OPENROUTER_API_KEY: Final = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_ENDPOINT: Final = "https://openrouter.ai/api/v1/chat/completions"


def parse_model_list(model_str: str | None) -> list[str]:
    """Pure function: parse comma-separated models string or return defaults."""
    if not model_str or not model_str.strip():
        return list(DEFAULT_FALLBACK_MODELS)
    models = [m.strip() for m in model_str.split(",") if m.strip()]
    if not models:
        return list(DEFAULT_FALLBACK_MODELS)
    return models


def build_chat_payload(models: list[str], system_prompt: str, user_prompt: str) -> dict:
    """Pure function: construct OpenRouter chat payload with models fallback list."""
    return {
        "models": models,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }


def extract_chat_text(resp: dict) -> str:
    """Pure function: safely extract text from an OpenAI-compatible chat response."""
    choices = resp.get("choices", [])
    if not choices:
        logger.error("OpenRouter API: no choices in response: %s", resp)
        return ""
    message = choices[0].get("message", {})
    content = message.get("content", "")
    if not content:
        logger.error("OpenRouter API: no content in message: %s", choices[0])
        return ""
    return str(content).strip()


def merge_fallback_models(
    primary_models: list[str],
    include_router_fallback: bool = True,
) -> list[str]:
    """Pure function: merge primary models with the openrouter/free router fallback."""
    result: list[str] = []
    seen: set[str] = set()

    for m in primary_models:
        if m and m not in seen:
            result.append(m)
            seen.add(m)

    if include_router_fallback and "openrouter/free" not in seen:
        result.append("openrouter/free")

    return result


def _chunk_models(models: list[str], chunk_size: int = 3) -> list[list[str]]:
    """Pure function: chunk a list of models into batches of up to chunk_size."""
    return [models[i : i + chunk_size] for i in range(0, len(models), chunk_size)]


def _chat_completion(system_prompt: str, user_prompt: str) -> str:
    """Send a chat completion request to OpenRouter with automatic model fallbacks."""
    api_key = os.environ.get("OPENROUTER_API_KEY", OPENROUTER_API_KEY)
    models_env = os.environ.get("OPENROUTER_MODEL") or os.environ.get(
        "OPENROUTER_MODELS"
    )
    primary_models = parse_model_list(models_env)
    all_models = merge_fallback_models(primary_models)
    batches = _chunk_models(all_models, chunk_size=3)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    for batch in batches:
        payload = build_chat_payload(batch, system_prompt, user_prompt)
        try:
            resp = session.post(
                OPENROUTER_ENDPOINT, json=payload, headers=headers, timeout=30
            ).json()
            text = extract_chat_text(resp)
            if text:
                return text
        except Exception:
            logger.exception("OpenRouter API request failed for batch %s", batch)

    return ""


SYSTEM_PROMPT_GEN_EXAMPLE: Final = """\
You are a multilingual language model specialized in generating clear and natural example sentences.
Given a single word (in English or Japanese, NOT Chinese), generate a simple and appropriate example sentence that uses the word naturally.
Requirements:

    Detect the input language (English or Japanese) automatically.

    Write the example sentence in the same language as the input word.

    Ensure the sentence is correct, natural, and understandable by beginner to intermediate learners.

    If the word has multiple meanings, choose the most common or basic meaning unless specified otherwise.

    Output only the example sentence, no explanations or extra text.

Examples:

    Input: write an example for "happy" Output: "She felt happy after hearing the good news."

    Input: write an example for "学校" Output: "私は毎日学校に通います。"
"""

SYSTEM_PROMPT_TRANSLATE: Final = (
    "You are a Japanese-English teacher, you are concise, "
    "not adding unnecessary stuff in your answer."
)


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


def translate_sentence(s: str) -> str:
    prompt = f"Translate this sentence to English '{s}', then break it down by chunks and explain words by words."
    return _chat_completion(SYSTEM_PROMPT_TRANSLATE, prompt)


def gen_example(word_def: str) -> str:
    return _chat_completion(
        SYSTEM_PROMPT_GEN_EXAMPLE, f'write an example for "{word_def}"'
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    models_env = os.environ.get("OPENROUTER_MODEL") or os.environ.get(
        "OPENROUTER_MODELS"
    )
    models = parse_model_list(models_env)
    has_key = bool(os.environ.get("OPENROUTER_API_KEY", OPENROUTER_API_KEY))

    print(f"=== OpenRouter LLM Demo (Models: {models}, Key configured: {has_key}) ===")

    print("\n--- Example 1: gen_example('happy') ---")
    print(gen_example("happy"))

    print("\n--- Example 2: gen_example('学校') ---")
    print(gen_example("学校"))

    print("\n--- Example 3: translate_sentence('これはペンです') ---")
    print(translate_sentence("これはペンです"))
