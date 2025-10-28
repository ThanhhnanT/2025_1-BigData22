"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import axios from "axios";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface CandleData {
  x: Date;
  y: [number, number, number, number]; // open, high, low, close
}

type BinanceKline = [
  number, // Open time
  string, // Open price
  string, // High price
  string, // Low price
  string, // Close price
  string, // Volume
  number, // Close time
  string, // Quote asset volume
  number, // Number of trades
  string, // Taker buy base asset volume
  string, // Taker buy quote asset volume
  string  // Ignore
];

export default function CandlestickChart() {
  const [series, setSeries] = useState<{ data: CandleData[] }[]>([
    { data: [] },
  ]);

  useEffect(() => {
    let ws: WebSocket | null = null;

    async function fetchInitialData() {
      try {
        const res = await axios.get(
          "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=100"
        );

        const initialData: CandleData[] = res.data.map((d: BinanceKline) => ({
          x: new Date(d[0]),
          y: [
            parseFloat(d[1]), // open
            parseFloat(d[2]), // high
            parseFloat(d[3]), // low
            parseFloat(d[4]), // close
          ],
        }));

        setSeries([{ data: initialData }]);

        connectWebSocket();
      } catch (err) {
        console.error("Error fetching initial data:", err);
      }
    }

    function connectWebSocket() {
      ws = new WebSocket("wss://stream.binance.com:9443/ws/btcusdt@kline_1m");

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.k) {
          const k = message.k;
          const candle: CandleData = {
            x: new Date(k.t),
            y: [
              parseFloat(k.o),
              parseFloat(k.h),
              parseFloat(k.l),
              parseFloat(k.c),
            ],
          };

          setSeries((prev) => {
            const oldData = prev[0]?.data || [];
            const lastIndex = oldData.findIndex(
              (d) => d.x.getTime() === candle.x.getTime()
            );

            let updatedData;
            if (lastIndex !== -1) {
              updatedData = [...oldData];
              updatedData[lastIndex] = candle;
            } else {
              updatedData = [...oldData, candle];
              if (updatedData.length > 100) updatedData.shift(); // giữ 100 nến gần nhất
            }

            return [{ data: updatedData }];
          });
        }
      };

      ws.onerror = (err) => console.error("WebSocket error:", err);
      ws.onclose = () => console.log("WebSocket closed");
    }

    fetchInitialData();

    return () => {
      if (ws) ws.close();
    };
  }, []);

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: "candlestick",
      height: 350,
      background: "transparent",
      animations: { enabled: false },
    },
    title: {
      text: "BTC/USDT - 1 Minute (Real-Time)",
      align: "left",
    },
    xaxis: {
      type: "datetime",
      labels: { datetimeUTC: false },
    },
    yaxis: {
      tooltip: { enabled: true },
    },
  };

  return (
    <div className="bg-white rounded-2xl shadow p-4">
      <Chart options={options} series={series} type="candlestick" height={350} />
    </div>
  );
}
