import { fetch, db } from 'sdk';
import { eq } from 'sdk/db';
import { cache } from 'schema';

// Helper to hash string to hex (SHA-256)
async function sha256(message) {
  // If crypto subtle API is available (in browser/sandbox environment)
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    const msgBuffer = new TextEncoder().encode(message);
    const hashBuffer = await crypto.subtle.digest('SHA-256', msgBuffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }
  // Fallback simple hash function if SubtleCrypto is not available in sandbox
  let hash = 0;
  for (let i = 0; i < message.length; i++) {
    const char = message.charCodeAt(i);
    hash = (hash << 5) - hash + char;
    hash = hash & hash; // Convert to 32bit integer
  }
  return 'simple_' + Math.abs(hash).toString(16);
}

export async function getAocLeaderboard(topn = 10) {
  const sessionToken = process.env.AOC_SESSION;
  if (!sessionToken) {
    throw new Error('AOC_SESSION environment variable must be set.');
  }

  const hash = await sha256(sessionToken);
  const cacheKey = `aoc_${hash}`;
  const now = Math.floor(Date.now() / 1000);

  let data = null;
  let timestampStr = '';

  // 1. Check database cache
  try {
    const cachedRow = await db.select().from(cache).where(eq(cache.key, cacheKey)).get();
    if (cachedRow && (now - cachedRow.updatedAt < 15 * 60)) {
      data = JSON.parse(cachedRow.val);
      const date = new Date(cachedRow.updatedAt * 1000);
      timestampStr = date.toISOString().replace('T', ' ').substring(0, 16).replace(/-/g, '');
    }
  } catch (err) {
    console.warn('Failed to query AoC cache from database:', err.message);
  }

  // 2. Fetch fresh data if cache is empty or stale
  if (!data) {
    const date = new Date();
    timestampStr = date.toISOString().replace('T', ' ').substring(0, 16).replace(/-/g, '');
    console.log('AoC: Fetching fresh leaderboard data...');

    const res = await fetch('https://adventofcode.com/2024/leaderboard/private/view/416592.json', {
      headers: {
        Cookie: `session=${sessionToken}`
      }
    });

    if (!res.ok) {
      throw new Error(`Advent of Code API returned status ${res.status}`);
    }

    data = await res.json();

    // Store in cache
    try {
      await db.insert(cache)
        .values({ key: cacheKey, val: JSON.stringify(data), updatedAt: now })
        .onConflictDoUpdate({
          target: cache.key,
          set: { val: JSON.stringify(data), updatedAt: now }
        })
        .run();
    } catch (err) {
      console.warn('Failed to write AoC cache to database:', err.message);
    }
  }

  if (!data || !data.members) {
    return 'Failed to retrieve Advent of Code leaderboard data.';
  }

  // 3. Format leaderboard
  const members = Object.values(data.members);
  const scoreboard = members
    .filter(m => m.stars > 0)
    .sort((a, b) => b.local_score - a.local_score)
    .map(m => ({
      name: m.name || `Anonymous User #${m.id}`,
      score: m.local_score,
      stars: m.stars,
    }));

  const lines = scoreboard.slice(0, topn).map((m, idx) => {
    return `${idx + 1}. ${m.name} ${m.score} ${m.stars}`;
  });

  return `AoC PyMi At ${timestampStr}UTC - refresh each 15m\n` + lines.join('\n');
}
