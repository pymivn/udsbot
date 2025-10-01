import requests
import json
from dataclasses import dataclass


@dataclass
class PodcastEpisode:
    name: str
    date: str
    url: str


def get_latest_podcast_episodes() -> list[PodcastEpisode]:
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

    return [
        PodcastEpisode(i["name"], date=i["datePublished"], url=i.get("url", "NOURL"))
        for i in audio_objects
    ]

    # print(audio_objects)
    # {'@type': 'AudioObject', 'datePublished': '2025-09-19', 'description': '【PR】ラジオNIKKEIとマネースクエアは共催で、「全国セミナープロジェクト～あなたの街de(で)ザ・マネーセミナー」と題して、無料の投資セミナーを開催しています。現在、10月11日土曜日', 'duration': 'PT9M21S', 'genre': ['今日のニュース'], 'name': '9月20日(土) 日銀 保有するETFとREITの市場売却を決定、日経平均株価反落 終値は257円安の4万5045円', 'offers': [{'@type': 'Offer', 'category': 'free', 'price': 0}], 'requiresSubscription': 'no', 'uploadDate': '2025-09-19', 'url': 'https://podcasts.apple.com/jp/podcast/9%E6%9C%8820%E6%97%A5-%E5%9C%9F-%E6%97%A5%E9%8A%80-%E4%BF%9D%E6%9C%89%E3%81%99%E3%82%8Betf%E3%81%A8reit%E3%81%AE%E5%B8%82%E5%A0%B4%E5%A3%B2%E5%8D%B4%E3%82%92%E6%B1%BA%E5%AE%9A-%E6%97%A5%E7%B5%8C%E5%B9%B3%E5%9D%87%E6%A0%AA%E4%BE%A1%E5%8F%8D%E8%90%BD-%E7%B5%82%E5%80%A4%E3%81%AF257%E5%86%86%E5%AE%89%E3%81%AE4%E4%B8%875045%E5%86%86/id1627014612?i=1000727576431', 'thumbnailUrl': 'https://is1-ssl.mzstatic.com/image/thumb/Podcasts221/v4/b0/7b/0f/b07b0fca-5bda-2927-0966-dc8f04cb5ae4/mza_18313644726869430335.jpg/1200x1200bf.webp'}


if __name__ == "__main__":
    print(get_latest_podcast_episodes())
