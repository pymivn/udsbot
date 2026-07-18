import { fetch } from 'sdk';

const COIN_MAP = {
  btc: 'bitcoin',
  eth: 'ethereum',
  usdt: 'tether',
  bnb: 'binancecoin',
  ada: 'cardano',
  doge: 'dogecoin',
  sol: 'solana',
  xrm: 'monero',
  xrp: 'xrp',
  ltc: 'litecoin',
  link: 'chainlink',
  xlm: 'stellar',
};

export function getCoinName(code) {
  const c = COIN_MAP[code.toLowerCase()];
  if (!c) throw new Error(`Unsupported coin: ${code}`);
  return c;
}

export async function getCoinPrice(coin) {
  const url = `https://api.coingecko.com/api/v3/simple/price?ids=${coin}&vs_currencies=usd&include_market_cap=true&include_24hr_change=true`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Coingecko API returned status ${res.status}`);
  }
  const data = await res.json();
  const coinData = data[coin];
  if (!coinData) {
    throw new Error(`Data for coin ${coin} not found in response`);
  }
  return {
    price_usd: coinData.usd,
    market_cap_usd: coinData.usd_market_cap,
    change_24h_percent: coinData.usd_24h_change,
  };
}

export async function getChartUrl(coin) {
  const url = `https://api.coingecko.com/api/v3/coins/${coin}/market_chart?vs_currency=usd&days=60`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Coingecko Market Chart API returned status ${res.status}`);
  }
  const data = await res.json();
  if (!data.prices || data.prices.length === 0) {
    throw new Error('No price data returned');
  }

  // Group by date to get daily close prices
  const daily = {};
  for (const [timestamp, price] of data.prices) {
    const dateStr = new Date(timestamp).toISOString().slice(0, 10);
    if (!daily[dateStr] || timestamp > daily[dateStr].time) {
      daily[dateStr] = { price, time: timestamp };
    }
  }

  const sortedDates = Object.keys(daily).sort();
  const labels = sortedDates.map(date => {
    // format date as "MM-DD" to keep the axis clean
    const parts = date.split('-');
    return `${parts[1]}-${parts[2]}`;
  });
  const prices = sortedDates.map(date => daily[date].price);

  const chartConfig = {
    type: 'line',
    data: {
      labels: labels,
      datasets: [{
        label: `${coin.toUpperCase()} (60 Days)`,
        data: prices,
        borderColor: '#00e676', // vibrant green
        borderWidth: 2,
        pointRadius: 0,
        fill: true,
        backgroundColor: 'rgba(0, 230, 118, 0.05)',
      }]
    },
    options: {
      title: {
        display: true,
        text: `${coin.toUpperCase()} Price Trend (USD)`,
        fontColor: '#ffffff',
        fontSize: 16
      },
      legend: {
        display: false
      },
      scales: {
        xAxes: [{
          gridLines: { color: 'rgba(255, 255, 255, 0.08)' },
          ticks: { fontColor: '#aaaaaa', maxTicksLimit: 8 }
        }],
        yAxes: [{
          gridLines: { color: 'rgba(255, 255, 255, 0.08)' },
          ticks: { fontColor: '#aaaaaa' }
        }]
      }
    }
  };

  return `https://quickchart.io/chart?c=${encodeURIComponent(JSON.stringify(chartConfig))}&bg=%231e1e1e`;
}
