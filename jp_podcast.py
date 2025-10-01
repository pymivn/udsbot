import requests
import json


def get_latest_podcast_title() -> str:
    URL = "https://podcasts.apple.com/jp/podcast/%E3%81%AA%E3%81%8C%E3%82%89%E6%97%A5%E7%B5%8C/id1627014612"
    resp = requests.get(URL)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    text = resp.text
    audio_objects = []
    for line in text.splitlines():
        if "AudioObject" in line:
            audio_objects = (json.loads(line))["workExample"]
            break

    latest = audio_objects[0]
    return latest["name"]


if __name__ == "__main__":
    print(get_latest_podcast_title())
