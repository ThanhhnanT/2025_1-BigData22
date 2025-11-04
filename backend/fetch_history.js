require("dotenv").config();
const axios = require("axios");
const { MongoClient } = require("mongodb");
const dayjs = require("dayjs");

const uri = process.env.MONGO_URI || "mongodb://localhost:27017";
const client = new MongoClient(uri);

const symbol = process.env.SYMBOL || "BTCUSDT";
const interval = process.env.INTERVAL || "30m";
const dbName = process.env.DB_NAME || "crypto_history";

const LIMIT = 1000;
const API_URL = "https://api.binance.com/api/v3/klines";

async function sleep(ms) {
  return new Promise((res) => setTimeout(res, ms));
}

async function fetchCandles(startTime, endTime) {
  const url = `${API_URL}?symbol=${symbol}&interval=${interval}&limit=${LIMIT}&startTime=${startTime}&endTime=${endTime}`;
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
}

async function main() {
  await client.connect();
  const db = client.db(dbName);
  const col = db.collection("candles");

  await col.createIndex(
    { symbol: 1, interval: 1, openTime: 1 },
    { unique: true }
  );

  const now = dayjs();
  const oneYearAgo = now.subtract(1, "year");
  let start = oneYearAgo.valueOf();
  let end = start + LIMIT * 30 * 60 * 1000;

  console.log(
    `Fetching ${symbol} (${interval}) from ${oneYearAgo.format()} to ${now.format()}`
  );

  let total = 0;

  while (start < now.valueOf()) {
    try {
      const candles = await fetchCandles(start, end);
      if (candles.length === 0) break;

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

      total += candles.length;
      console.log(`Saved ${candles.length} candles — total ${total}`);

      start = candles[candles.length - 1].closeTime + 1;
      end = start + LIMIT * 30 * 60 * 1000;

      await sleep(500);
    } catch (err) {
      console.error("Error:", err.response ? err.response.data : err.message);
      await sleep(2000);
    }
  }

  console.log(`✅ Done! Total candles saved: ${total}`);
  await client.close();
}

main().catch(console.error);
