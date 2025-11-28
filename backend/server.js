require("dotenv").config();
const express = require("express");
const cors = require("cors");
const { MongoClient } = require("mongodb");

const app = express();
app.use(cors());

const uri = process.env.MONGO_URI || "mongodb://localhost:27017";
const client = new MongoClient(uri);
const dbName = process.env.DB_NAME || "crypto_history";

async function main() {
  await client.connect();
  const db = client.db(dbName);
  const candles = db.collection("candles");

  app.get("/api/candles", async (req, res) => {
    try {
      const symbol = req.query.symbol || "BTCUSDT";
      const interval = req.query.interval || "30m";
      const limit = parseInt(req.query.limit) || 500;
      const from = req.query.from ? parseInt(req.query.from) : null;
      const to = req.query.to ? parseInt(req.query.to) : null;

      const query = { symbol, interval };
      if (from && to) {
        query.openTime = { $gte: from, $lte: to };
      } else if (from) {
        query.openTime = { $gte: from };
      } else if (to) {
        query.openTime = { $lte: to };
      }

      const data = await candles
        .find(query)
        .sort({ openTime: -1 })
        .limit(limit)
        .toArray();

      const formatted = data.reverse().map((d) => ({
        openTime: d.openTime,
        x: new Date(d.openTime).toISOString(),
        y: [d.open, d.high, d.low, d.close],
        volume: d.volume,
      }));

      res.json({
        symbol,
        interval,
        count: formatted.length,
        candles: formatted,
      });
    } catch (err) {
      console.error("❌ Error fetching candles:", err);
      res.status(500).json({ error: "Internal server error" });
    }
  });

  app.get("/", (_, res) => {
    res.send("✅ Crypto History API is running");
  });

  const port = process.env.PORT || 4000;
  app.listen(port, () =>
    console.log(`🚀 Server running on http://localhost:${port}`)
  );
}

main().catch(console.error);
