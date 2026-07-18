import { api } from 'sdk';
import { lookupWord, lookupWordFr, searchJisho } from 'lib/dictionary';
import { getKanji } from 'lib/kanji';
import { getLatestPodcastEpisodes } from 'lib/podcast';
import { genJoke, translateWord, translateSentence, genExample } from 'lib/llm';
import { getCoinName, getCoinPrice, getChartUrl } from 'lib/crypto';
import { getTemp, getAqiHanoi, getAqiSingapore, getAqiHcm } from 'lib/weather';
import { getAocLeaderboard } from 'lib/aoc';
import { addJob, delJob, listJobs } from 'lib/cron';

function fitMeaningsToMessage(url, meanings) {
  const result = [];
  const EACH_MEANING_LIMIT = 160;
  for (let idx = 0; idx < meanings.length; idx++) {
    if (idx === 5) {
      result.push('...');
      break;
    }
    let meaning = meanings[idx];
    if (meaning.length > EACH_MEANING_LIMIT) {
      meaning = `${meaning.slice(0, EACH_MEANING_LIMIT)}...`;
    }
    result.push(`${idx + 1}. ${meaning}`);
  }
  result.push(url);
  return result.join('\n');
}

async function dispatchCam(text, chatId, fromId) {
  const keyword = text.split(/\s+/).slice(1).join(' ').trim();
  if (!keyword || keyword.length > 50) {
    await api.sendMessage({ chat_id: chatId, text: 'Invalid word format or length (max 50 chars).' });
    return;
  }
  const res = await lookupWord(keyword);
  const msg = fitMeaningsToMessage(res.url, res.means);
  await api.sendMessage({
    chat_id: chatId,
    text: `Cambridge result for \`${keyword}\`\nIPA: ${res.ipa ? '/' + res.ipa + '/' : '(no IPA)'}\n${msg}`
  });
}

async function dispatchFr(text, chatId, fromId) {
  const keyword = text.split(/\s+/).slice(1).join(' ').trim();
  if (!keyword || keyword.length > 50) {
    await api.sendMessage({ chat_id: chatId, text: 'Invalid word format or length (max 50 chars).' });
    return;
  }
  const res = await lookupWordFr(keyword);
  const msg = fitMeaningsToMessage(res.url, res.means);
  await api.sendMessage({
    chat_id: chatId,
    text: `French dictionary result for \`${keyword}\`\n${msg}`
  });
}

async function dispatchHi(text, chatId, fromId) {
  const cities = ['Ho Chi Minh', 'Hanoi', 'Singapore'];
  try {
    const temps = await getTemp(cities);
    for (const t of temps) {
      await api.sendMessage({
        chat_id: chatId,
        text: `Weather in ${t.name} is ${t.weather}, temp now: ${t.temp_now}, feels like: ${t.feels_like}, humidity: ${t.humidity}%`
      });
    }
  } catch (e) {
    await api.sendMessage({
      chat_id: chatId,
      text: `Weather info is unavailable: ${e.message}. Note: To show weather data, you need to set WEATHER_TOKEN env.`
    });
  }

  const [hcmLoc, hcmVal, hcmTime] = await getAqiHcm();
  if (hcmLoc && hcmVal) {
    await api.sendMessage({ chat_id: chatId, text: `PM2.5 ${hcmVal} at ${hcmLoc} at ${hcmTime}` });
  } else {
    await api.sendMessage({ chat_id: chatId, text: 'No AQI available for Ho Chi Minh City' });
  }

  const [hnLoc, hnVal, hnTime] = await getAqiHanoi();
  await api.sendMessage({ chat_id: chatId, text: `PM2.5 ${hnVal} at ${hnLoc} at ${hnTime}` });

  const [sgLoc, sgVal, sgTime] = await getAqiSingapore();
  await api.sendMessage({ chat_id: chatId, text: `PM2.5 ${sgVal} at ${sgLoc} at ${sgTime}` });
}

async function dispatchJo(text, chatId, fromId) {
  const parts = text.split(/\s+/);
  let grade = 3;
  let nth = -1;
  if (parts.length >= 2) {
    grade = parseInt(parts[1], 10) || 3;
  }
  if (parts.length >= 3) {
    nth = parseInt(parts[2], 10) || -1;
  }
  const k = getKanji(grade, nth);
  await api.sendMessage({
    chat_id: chatId,
    text: `${k.char}: ${k.meaning}\n${k.reading}\n${k.url}`
  });
}

async function dispatchJk(text, chatId, fromId) {
  const joke = await genJoke();
  await api.sendMessage({ chat_id: chatId, text: joke.slice(0, 300) });
}

async function dispatchNikkei(text, chatId, fromId) {
  const episodes = await getLatestPodcastEpisodes();
  if (episodes.length === 0) {
    await api.sendMessage({ chat_id: chatId, text: 'No podcast episodes found.' });
    return;
  }
  const latest = episodes[0];
  const translated = await translateSentence(latest.name);
  await api.sendMessage({
    chat_id: chatId,
    text: `${translated}\n${latest.url}`
  });
}

async function dispatchLt(text, chatId, fromId) {
  const keyword = text.split(/\s+/).slice(1).join(' ').trim();
  if (!keyword || keyword.length > 30) {
    await api.sendMessage({ chat_id: chatId, text: 'Invalid word format or length (max 30 chars).' });
    return;
  }
  const res = await translateWord(keyword);
  await api.sendMessage({ chat_id: chatId, text: res.slice(0, 300) });
}

async function dispatchJi(text, chatId, fromId) {
  const keyword = text.split(/\s+/).slice(1).join(' ').trim();
  if (!keyword || keyword.length > 50) {
    await api.sendMessage({ chat_id: chatId, text: 'Invalid word format or length (max 50 chars).' });
    return;
  }
  const res = await searchJisho(keyword);
  const msg = fitMeaningsToMessage(res.url, res.means);
  await api.sendMessage({
    chat_id: chatId,
    text: `Jisho result for \`${keyword}\`\nReading: ${res.reading}\n${msg}`
  });
}

async function dispatchAqi(text, chatId, fromId) {
  const [hnLoc, hnVal, hnTime] = await getAqiHanoi();
  await api.sendMessage({ chat_id: chatId, text: `PM2.5 ${hnVal} at ${hnLoc} at ${hnTime}` });

  const [hcmLoc, hcmVal, hcmTime] = await getAqiHcm();
  if (hcmLoc && hcmVal) {
    await api.sendMessage({ chat_id: chatId, text: `PM2.5 ${hcmVal} at ${hcmLoc} at ${hcmTime}` });
  } else {
    await api.sendMessage({ chat_id: chatId, text: 'No AQI available for Ho Chi Minh City' });
  }

  const [sgLoc, sgVal, sgTime] = await getAqiSingapore();
  await api.sendMessage({ chat_id: chatId, text: `PM2.5 ${sgVal} at ${sgLoc} at ${sgTime}` });
}

async function dispatchTem(text, chatId, fromId) {
  const cities = ['Ho Chi Minh', 'Hanoi', 'Singapore'];
  try {
    const temps = await getTemp(cities);
    for (const t of temps) {
      await api.sendMessage({
        chat_id: chatId,
        text: `Weather in ${t.name} is ${t.weather}, temp now: ${t.temp_now}, feels like: ${t.feels_like}, humidity: ${t.humidity}%`
      });
    }
  } catch (e) {
    await api.sendMessage({
      chat_id: chatId,
      text: `Weather info is unavailable: ${e.message}. Note: To show weather data, you need to set WEATHER_TOKEN env.`
    });
  }
}

async function dispatchBtc(text, chatId, fromId) {
  const parts = text.split(/\s+/);
  const code = parts[1] || 'btc';
  try {
    const coinName = getCoinName(code);
    const priceData = await getCoinPrice(coinName);
    const capBillions = Math.round(priceData.market_cap_usd / 100000000) / 10;
    const changePercent = Math.round(priceData.change_24h_percent * 10) / 10;
    await api.sendMessage({
      chat_id: chatId,
      text: `${coinName.toUpperCase()} $${priceData.price_usd}\nCap $${capBillions}B\n24h ${changePercent}%`
    });
  } catch (e) {
    await api.sendMessage({
      chat_id: chatId,
      text: 'Try coin in list:[btc, eth, usdt, bnb, ada, doge, xrp, ltc, link, xlm]'
    });
  }
}

async function dispatchC(text, chatId, fromId) {
  const parts = text.split(/\s+/);
  const code = parts[1] || 'btc';
  try {
    const coinName = getCoinName(code);
    const chartUrl = await getChartUrl(coinName);
    await api.sendPhoto({
      chat_id: chatId,
      photo: chartUrl,
    });
  } catch (e) {
    await api.sendMessage({
      chat_id: chatId,
      text: `Failed to create chart: ${e.message}. Try coin in list:[btc, eth, usdt, bnb, ada, doge, xrp, ltc, link, xlm]`
    });
  }
}

async function dispatchAoc(text, chatId, fromId) {
  const parts = text.split(/\s+/);
  const topn = parseInt(parts[1], 10) || 10;
  try {
    const msg = await getAocLeaderboard(topn);
    await api.sendMessage({ chat_id: chatId, text: msg });
  } catch (e) {
    await api.sendMessage({ chat_id: chatId, text: `AoC command failed: ${e.message}` });
  }
}

async function dispatchCron(text, chatId, fromId) {
  try {
    const jobUuid = await addJob(text, chatId, fromId);
    await api.sendMessage({
      chat_id: chatId,
      text: `Cron job added successfully! To delete this job: /delcron ${jobUuid}`
    });
  } catch (e) {
    await api.sendMessage({
      chat_id: chatId,
      text: `Add cron job failed with error: ${e.message}`
    });
  }
}

async function dispatchDelcron(text, chatId, fromId) {
  try {
    const success = await delJob(text, chatId, fromId);
    if (success) {
      await api.sendMessage({ chat_id: chatId, text: 'Cron job deleted successfully!' });
    } else {
      await api.sendMessage({ chat_id: chatId, text: 'Cron job not found or you are not the owner.' });
    }
  } catch (e) {
    await api.sendMessage({
      chat_id: chatId,
      text: `Delete cron job failed with error: ${e.message}`
    });
  }
}

async function dispatchListcron(text, chatId, fromId) {
  try {
    const jobsList = await listJobs(text, chatId, fromId);
    if (jobsList.length === 0) {
      await api.sendMessage({ chat_id: chatId, text: 'No cron jobs found.' });
    } else {
      const jobsStr = jobsList.map(job => `${job.uuid} - ${String(job.hour).padStart(2, '0')}:${String(job.minute).padStart(2, '0')} ${job.command}`).join('\n');
      await api.sendMessage({ chat_id: chatId, text: jobsStr });
    }
  } catch (e) {
    await api.sendMessage({
      chat_id: chatId,
      text: `List cron jobs failed with error: ${e.message}`
    });
  }
}

async function dispatchX(text, chatId, fromId) {
  const parts = text.split(/\s+/);
  if (parts.length < 3) {
    await api.sendMessage({ chat_id: chatId, text: 'Format: /x <cmd> <word>, e.g. /x cam hello' });
    return;
  }
  const cmd = parts[1].replace(/^\//, '').toLowerCase();
  const disallowed = ['x', 'cron', 'delcron', 'listcron'];
  if (disallowed.includes(cmd)) {
    await api.sendMessage({ chat_id: chatId, text: 'Operation not permitted.' });
    return;
  }
  const word = parts.slice(2).join(' ');
  if (word.length > 100) {
    await api.sendMessage({ chat_id: chatId, text: 'Word is too long (max 100 chars).' });
    return;
  }

  // Run the command first
  const simulatedText = `/${cmd} ${word}`;
  await dispatch(simulatedText, chatId, fromId);

  // Generate example sentence via Gemini
  try {
    const example = await genExample(word);
    await api.sendMessage({ chat_id: chatId, text: example.slice(0, 300) });
  } catch (e) {
    console.error('Failed to generate example sentence:', e);
  }
}

export async function dispatch(text, chatId, fromId) {
  if (!text || !text.trim()) {
    console.warn('Received empty message, skipping');
    return;
  }

  const cleanText = text.trim();
  const parts = cleanText.split(/\s+/);
  const cmd = parts[0].toLowerCase().replace(/^\//, '');

  console.log(`Dispatching command: ${cmd} in chat: ${chatId}`);

  try {
    switch (cmd) {
      case 'cam':
        await dispatchCam(cleanText, chatId, fromId);
        break;
      case 'fr':
        await dispatchFr(cleanText, chatId, fromId);
        break;
      case 'hi':
        await dispatchHi(cleanText, chatId, fromId);
        break;
      case 'jo':
        await dispatchJo(cleanText, chatId, fromId);
        break;
      case 'jk':
        await dispatchJk(cleanText, chatId, fromId);
        break;
      case 'nikkei':
        await dispatchNikkei(cleanText, chatId, fromId);
        break;
      case 'lt':
        await dispatchLt(cleanText, chatId, fromId);
        break;
      case 'ji':
        await dispatchJi(cleanText, chatId, fromId);
        break;
      case 'aqi':
        await dispatchAqi(cleanText, chatId, fromId);
        break;
      case 'tem':
        await dispatchTem(cleanText, chatId, fromId);
        break;
      case 'btc':
        await dispatchBtc(cleanText, chatId, fromId);
        break;
      case 'c':
        await dispatchC(cleanText, chatId, fromId);
        break;
      case 'aoc':
        await dispatchAoc(cleanText, chatId, fromId);
        break;
      case 'cron':
        await dispatchCron(cleanText, chatId, fromId);
        break;
      case 'delcron':
        await dispatchDelcron(cleanText, chatId, fromId);
        break;
      case 'listcron':
        await dispatchListcron(cleanText, chatId, fromId);
        break;
      case 'x':
        await dispatchX(cleanText, chatId, fromId);
        break;
      default:
        console.warn(`Unknown command: ${cmd}, skipping`);
        break;
    }
  } catch (e) {
    console.error(`Error in dispatch_${cmd}:`, e);
    try {
      await api.sendMessage({
        chat_id: chatId,
        text: `Failed to execute command. Error: ${e.message}`
      });
    } catch (sendErr) {
      console.error('Failed to send error message:', sendErr);
    }
  }
}
