import logging
import warnings
from typing import TypedDict
from urllib.parse import quote

import wn

# eng_to_ipa emits SyntaxWarning on Python 3.14 due to unescaped regex
# sequences in its source code — suppress since we cannot fix upstream.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", SyntaxWarning)
    import eng_to_ipa as _eng_to_ipa  # type: ignore[import-untyped]

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Map WordNet single-char POS codes to human-readable labels
_POS_LABELS: dict[str, str] = {
    "n": "noun",
    "v": "verb",
    "a": "adj",
    "r": "adv",
    "s": "adj",
}


class LookupResult(TypedDict):
    url: str
    ipa: str
    means: list[str]


def _get_ipa(word: str) -> str:
    """Get IPA pronunciation for a word using eng-to-ipa.

    Returns empty string if the word is not found in the IPA dictionary
    (eng_to_ipa marks unknown words with a trailing asterisk).
    """
    try:
        result: str = _eng_to_ipa.convert(word)
        if result.endswith("*"):
            return ""
        return result
    except Exception:
        logger.exception("IPA lookup failed for %s", word)
        return ""


def lookup_word(word: str) -> LookupResult:
    """Look up a word in the Open English WordNet with IPA pronunciation.

    Returns a dict compatible with the format from ``uds.cambridge()``:
        {"url": str, "ipa": str, "means": list[str]}

    If the word is not found, ``means`` will be an empty list.
    IPA is provided by eng-to-ipa (offline, CMU-based).
    """
    url = f"https://en.wiktionary.org/wiki/{quote(word)}"
    ipa = _get_ipa(word)
    means: list[str] = []

    try:
        word_entries = wn.words(word)
    except Exception:
        logger.exception("WordNet lookup failed for %s", word)
        return {"url": url, "ipa": ipa, "means": means}

    for word_entry in word_entries:
        pos_code = word_entry.pos or ""
        pos_label = _POS_LABELS.get(pos_code, pos_code)

        for sense in word_entry.senses():
            synset = sense.synset()
            definition = synset.definition()
            if definition:
                means.append(f"({pos_label}) {definition}")

    return {"url": url, "ipa": ipa, "means": means}


def lookup_word_fr(word: str) -> LookupResult:
    """Look up a word in the French WordNet (WOLF), translating to English for definitions.

    Returns a dict:
        {"url": str, "ipa": str, "means": list[str]}

    If the word is not found, ``means`` will be an empty list.
    No IPA is provided (empty string).
    """
    url = f"https://fr.wiktionary.org/wiki/{quote(word)}"
    ipa = ""
    means: list[str] = []

    try:
        word_entries = wn.words(word, lang="fr")
    except Exception:
        logger.exception("French WordNet lookup failed for %s", word)
        return {"url": url, "ipa": ipa, "means": means}

    for word_entry in word_entries:
        pos_code = word_entry.pos or ""
        pos_label = _POS_LABELS.get(pos_code, pos_code)

        for sense in word_entry.senses():
            synset = sense.synset()
            try:
                en_synsets = synset.translate(lang="en")
            except Exception:
                continue
            for en_synset in en_synsets:
                definition = en_synset.definition()
                if definition:
                    means.append(f"({pos_label}) {definition}")

    # Deduplicate while preserving order
    deduped_means = list(dict.fromkeys(means))

    return {"url": url, "ipa": ipa, "means": deduped_means}


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    is_fr = False
    if args and args[0] == "--fr":
        is_fr = True
        args = args[1:]

    words = args if args else (["bonjour"] if is_fr else ["hello"])
    for word in words:
        if is_fr:
            result = lookup_word_fr(word)
        else:
            result = lookup_word(word)
        ipa_str = f"/{result['ipa']}/" if result["ipa"] else "(no IPA)"
        print(f"\n{word}  {ipa_str}")
        print(f"  {result['url']}")
        if result["means"]:
            for m in result["means"]:
                print(f"  - {m}")
        else:
            print("  (no definitions found)")
