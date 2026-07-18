import { fetch } from 'sdk';

export async function lookupWord(word) {
  const url = `https://en.wiktionary.org/wiki/${encodeURIComponent(word)}`;
  let ipa = '';
  let means = [];
  try {
    const res = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/en/${encodeURIComponent(word)}`);
    if (res.ok) {
      const data = await res.json();
      const entry = data[0];
      if (entry) {
        if (entry.phonetic) {
          ipa = entry.phonetic.replace(/^\/|\/$/g, '');
        } else if (entry.phonetics && entry.phonetics.length > 0) {
          const withText = entry.phonetics.find(p => p.text);
          if (withText) {
            ipa = withText.text.replace(/^\/|\/$/g, '');
          }
        }

        if (entry.meanings) {
          for (const m of entry.meanings) {
            const pos = m.partOfSpeech || '';
            if (m.definitions) {
              for (const d of m.definitions) {
                if (d.definition) {
                  means.push(`(${pos}) ${d.definition}`);
                }
              }
            }
          }
        }
      }
    }
  } catch (e) {
    console.error(`English lookup failed for ${word}:`, e);
  }
  return { url, ipa, means };
}

export async function lookupWordFr(word) {
  const url = `https://fr.wiktionary.org/wiki/${encodeURIComponent(word)}`;
  let means = [];
  try {
    const res = await fetch(`https://api.dictionaryapi.dev/api/v2/entries/fr/${encodeURIComponent(word)}`);
    if (res.ok) {
      const data = await res.json();
      const entry = data[0];
      if (entry && entry.meanings) {
        for (const m of entry.meanings) {
          const pos = m.partOfSpeech || '';
          if (m.definitions) {
            for (const d of m.definitions) {
              if (d.definition) {
                means.push(`(${pos}) ${d.definition}`);
              }
            }
          }
        }
      }
    }
  } catch (e) {
    console.error(`French lookup failed for ${word}:`, e);
  }
  means = [...new Set(means)];
  return { url, ipa: '', means };
}

export async function searchJisho(word) {
  try {
    const res = await fetch(`https://jisho.org/api/v1/search/words?keyword=${encodeURIComponent(word)}`);
    if (res.ok) {
      const data = await res.json();
      if (data.data && data.data.length > 0) {
        const result = data.data[0];
        const url = `https://jisho.org/word/${result.slug}`;
        const reading = result.japanese.map(i => {
          const w = i.word || '';
          const r = i.reading || 'no reading';
          return w ? `${w}:${r}` : r;
        }).join(', ');
        const means = result.senses.map(s => s.english_definitions.join(', '));
        return { url, reading, means };
      }
    }
  } catch (e) {
    console.error(`Jisho lookup failed for ${word}:`, e);
  }
  return { url: '', reading: '', means: [] };
}
