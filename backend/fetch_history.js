require("dotenv").config();
const axios = require("axios");
const { MongoClient } = require("mongodb");
const dayjs = require("dayjs");

const uri = process.env.MONGO_URI || "mongodb://localhost:27017";
const client = new MongoClient(uri);

const SYMBOLS = [
  "BTCUSDT",
  "ETHUSDT",
  "BNBUSDT",
  "SOLUSDT",
  "XRPUSDT",
  "ADAUSDT",
  "DOGEUSDT",
  "MATICUSDT",
  "DOTUSDT",
  "AVAXUSDT",
];

const INTERVALS = ["5m", "1h", "1d"];

const INTERVAL_MS = {
  "5m": 5 * 60 * 1000,
  "1h": 60 * 60 * 1000,
  "1d": 24 * 60 * 60 * 1000,
};

const FETCH_PERIOD = {
  "5m": 3,
  "1h": 6,
  "1d": 12,
};

const dbName = process.env.DB_NAME || "crypto_history";
const LIMIT = 1000;
const API_URL = "https://api.binance.com/api/v3/klines";

async function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

async function fetchCandles(symbol, interval, startTime, endTime) {
  const url = `${API_URL}?symbol=${symbol}&interval=${interval}&limit=${LIMIT}&startTime=${startTime}&endTime=${endTime}`;
  try {
    const res = await axios.get(url);
    return res.data.map((k) => ({
      symbol,
      interval,
      openTime: k[0],
      closeTime: k[6],
      openTimeISO: new Date(k[0]).toISOString(),
      closeTimeISO: new Date(k[6]).toISOString(),
      open: parseFloat(k[1]),
      high: parseFloat(k[2]),
      low: parseFloat(k[3]),
      close: parseFloat(k[4]),
      volume: parseFloat(k[5]),
      trades: k[8],
      savedAt: new Date(),
    }));
  } catch (err) {
    console.error(`❌ Error fetching ${symbol} ${interval}:`, err.message);
    return [];
  }
}

async function fetchSymbolInterval(db, symbol, interval) {
  const col = db.collection("candles");

  const now = dayjs();
  const monthsAgo = FETCH_PERIOD[interval];
  const startDate = now.subtract(monthsAgo, "month");

  let start = startDate.valueOf();
  let end = start + LIMIT * INTERVAL_MS[interval];

  console.log(
    `\n📊 Fetching ${symbol} (${interval}) from ${startDate.format(
      "YYYY-MM-DD"
    )} to ${now.format("YYYY-MM-DD")}`
  );

  let total = 0;
  let savedCount = 0;

  while (start < now.valueOf()) {
    const candles = await fetchCandles(symbol, interval, start, end);
    if (candles.length === 0) break;

    try {
      const result = await col.bulkWrite(
        candles.map((doc) => ({
          updateOne: {
            filter: {
              symbol: doc.symbol,
              interval: doc.interval,
              openTime: doc.openTime,
            },
            update: { $set: doc },
            upsert: true,
          },
        }))
      );

      savedCount += result.upsertedCount + result.modifiedCount;
      total += candles.length;

      console.log(
        `  ✓ Processed ${candles.length} candles (${savedCount} saved) — total: ${total}`
      );

      start = candles[candles.length - 1].closeTime + 1;
      end = start + LIMIT * INTERVAL_MS[interval];

      await sleep(500); // Rate limit
    } catch (err) {
      console.error(`  ❌ Error saving ${symbol} ${interval}:`, err.message);
      await sleep(2000);
    }
  }

  console.log(
    `  ✅ ${symbol} ${interval}: Total ${total} candles, ${savedCount} saved/updated`
  );
  return { symbol, interval, total, saved: savedCount };
}

async function main() {
  await client.connect();
  console.log("🔗 Connected to MongoDB");

  const db = client.db(dbName);
  const col = db.collection("candles");

  await col.createIndex(
    { symbol: 1, interval: 1, openTime: 1 },
    { unique: true }
  );
  console.log("✅ Index created");

  const stats = [];

  // Fetch từng coin với từng interval
  for (const symbol of SYMBOLS) {
    console.log(`\n${"=".repeat(50)}`);
    console.log(`🪙  Processing ${symbol}`);
    console.log("=".repeat(50));

    for (const interval of INTERVALS) {
      try {
        const result = await fetchSymbolInterval(db, symbol, interval);
        stats.push(result);
      } catch (err) {
        console.error(`❌ Failed to fetch ${symbol} ${interval}:`, err.message);
      }
    }
  }

  console.log("\n" + "=".repeat(60));
  console.log("📈 SUMMARY");
  console.log("=".repeat(60));

  const grouped = {};
  stats.forEach((s) => {
    if (!grouped[s.symbol]) grouped[s.symbol] = {};
    grouped[s.symbol][s.interval] = { total: s.total, saved: s.saved };
  });

  Object.keys(grouped).forEach((symbol) => {
    console.log(`\n${symbol}:`);
    Object.keys(grouped[symbol]).forEach((interval) => {
      const { total, saved } = grouped[symbol][interval];
      console.log(`  ${interval}: ${total} candles (${saved} saved/updated)`);
    });
  });

  const totalCandles = stats.reduce((sum, s) => sum + s.total, 0);
  const totalSaved = stats.reduce((sum, s) => sum + s.saved, 0);

  console.log("\n" + "=".repeat(60));
  console.log(
    `✅ DONE! Total: ${totalCandles} candles, ${totalSaved} saved/updated`
  );
  console.log("=".repeat(60));

  await client.close();
}

main().catch(console.error);
