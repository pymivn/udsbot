import { fetch } from 'sdk';

export async function getLatestPodcastEpisodes() {
  const url = 'https://podcasts.apple.com/jp/podcast/%E3%81%AA%E3%81%8C%E3%82%89%E6%97%A5%E7%B5%8C/id1627014612';
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`HTTP error! status: ${res.status}`);
  }
  const text = await res.text();
  let audioObjects = [];
  const lines = text.split('\n');
  for (const line of lines) {
    if (line.includes('AudioObject') && line.length < 100000) {
      try {
        const parsed = JSON.parse(line);
        audioObjects = parsed.workExample || [];
        break;
      } catch (e) {
        // ignore JSON parsing errors for lines that just happen to contain AudioObject
      }
    }
  }
  return audioObjects.map(i => ({
    name: i.name,
    date: i.datePublished,
    url: i.url || 'NOURL',
  }));
}
