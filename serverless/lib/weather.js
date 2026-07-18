import { fetch } from 'sdk';

export async function getTemp(cities) {
  const apiKey = process.env.WEATHER_TOKEN;
  if (!apiKey) {
    throw new Error('WEATHER_TOKEN environment variable not set.');
  }

  const results = [];
  for (const city of cities) {
    const url = `https://api.openweathermap.org/data/2.5/weather?q=${encodeURIComponent(city)}&appid=${apiKey}`;
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Weather API returned status ${res.status} for ${city}`);
    }
    const data = await res.json();
    results.push({
      name: data.name,
      temp_now: Math.round(data.main.temp - 273.15),
      feels_like: Math.round(data.main.feels_like - 273.15),
      humidity: data.main.humidity,
      weather: data.weather[0].description,
    });
  }
  return results;
}

export async function getAqiHanoi() {
  const url = 'https://api.waqi.info/mapq/bounds/?bounds=20.96111901161895,105.75405120849611,21.09571147652958,105.91609954833986';
  try {
    const res = await fetch(url);
    if (!res.ok) return ['Hanoi', null, null];
    const locs = await res.json();
    if (locs && locs.length > 0) {
      for (const i of locs) {
        const aqiNum = parseInt(i.aqi, 10);
        if (!isNaN(aqiNum) && aqiNum > 0) {
          return [i.city, i.aqi, i.utime];
        }
      }
      return [locs[0].city, null, locs[0].utime];
    }
  } catch (e) {
    console.error('getAqiHanoi error:', e);
  }
  return ['Hanoi', null, null];
}

export async function getAqiSingapore() {
  const url = 'https://api.waqi.info/mapq/bounds/?bounds=1.156,103.605,1.494,104.084';
  try {
    const res = await fetch(url, { timeout: 10000 });
    if (!res.ok) return ['Singapore', null, null];
    const locs = await res.json();
    if (locs && locs.length > 0) {
      for (const i of locs) {
        const aqiNum = parseInt(i.aqi, 10);
        if (!isNaN(aqiNum) && aqiNum > 0) {
          return [i.city, i.aqi, i.utime];
        }
      }
      return [locs[0].city, null, locs[0].utime];
    }
  } catch (e) {
    console.error('getAqiSingapore error:', e);
  }
  return ['Singapore', null, null];
}

export async function getAqiHcm() {
  const url = 'https://airnet.waqi.info/airnet/map/bounds';
  const currentTime = new Date().toISOString();
  try {
    const res = await fetch(url, {
      method: 'POST',
      body: fetch.body.form({
        bounds: '106.57606490366962,10.710644309189911,106.83509113187337,10.906718682210693',
        zoom: '11',
        xscale: '1303.4747344074406',
        width: '678',
        time: currentTime,
      })
    });
    if (!res.ok) return ['Ho Chi Minh City', null, null];
    const data = await res.json();
    const locs = data.data || [];
    if (locs.length > 0) {
      let highestAqi = null;
      let maxU = -1;
      for (const x of locs) {
        const u = typeof x.u === 'number' ? x.u : 0;
        if (u > maxU) {
          maxU = u;
          highestAqi = x;
        }
      }
      if (highestAqi) {
        const name = highestAqi.n;
        const aqiValue = highestAqi.a;
        const date = new Date(highestAqi.u * 1000);
        const tzOffset = 7 * 60 * 60 * 1000; // HCM timezone offset is UTC+7
        const localTime = new Date(date.getTime() + tzOffset);
        const utime = localTime.toISOString().replace('T', ' ').substring(0, 19);
        return [name, aqiValue, utime];
      }
    }
  } catch (e) {
    console.error('getAqiHcm error:', e);
  }
  return ['Ho Chi Minh City', null, null];
}
