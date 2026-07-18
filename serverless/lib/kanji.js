import { joyoData } from 'lib/joyo_final';

const NUMBER_OF_YOJO_WORDS = 2136;

export function getKanji(grade = 2, nth = -1) {
  const gradeStr = String(grade);
  const kanjiList = joyoData[gradeStr] || joyoData['2'];
  const len = kanjiList.length;

  if (nth === -1) {
    nth = Math.floor(Math.random() * NUMBER_OF_YOJO_WORDS);
  } else if (nth >= 1) {
    nth = nth - 1;
  }

  // Modulo in JS can return negative numbers for negative inputs, so do a positive modulo
  nth = ((nth % len) + len) % len;

  const k = kanjiList[nth];
  const url = `${k.url}%20%23grade:${gradeStr}`;

  return {
    char: k.kanji,
    meaning: k.meaning,
    reading: k.reading,
    grade: gradeStr,
    url: url,
  };
}
