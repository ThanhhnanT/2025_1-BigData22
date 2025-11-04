"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import axios from "axios";
import { io, Socket } from "socket.io-client";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../ui/tabs";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface CandleData {
  x: number; 
  y: [number, number, number, number];
  volume?: number;
}

interface KafkaCandle {
  symbol: string;
  interval: string;
  openTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

interface ApiResponse {
  symbol: string;
  interval: string;
  count: number;
  candles: {
    openTime: number;
    y: [number, number, number, number];
    volume: number;
  }[];
}

export default function CandlestickChart() {
  const [mode, setMode] = useState<"history" | "realtime">("history");
  const [series, setSeries] = useState<{ data: CandleData[] }[]>([{ data: [] }]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let socket: Socket | undefined;
    let isMounted = true;

    async function fetchHistoricalData() {
      try {
        setIsLoading(true);
        const res = await axios.get<ApiResponse>("http://localhost:4000/api/candles", {
          params: { symbol: "BTCUSDT", interval: "30m", limit: 100 },
        });

        if (!isMounted) return;

        const formatted = (res.data?.candles || []).map((d) => ({
          x: new Date(d.openTime).getTime(),
          y: d.y,
          volume: d.volume,
        }));

        setSeries([{ data: formatted }]);
      } catch (err) {
        console.error("❌ Error fetching historical data:", err);
        if (isMounted) setSeries([{ data: [] }]);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    function connectWebSocket() {
      socket = io("http://localhost:5001", {
        transports: ["websocket"],
      });

      socket.on("connect", () => {
        console.log("✅ Connected to Kafka WebSocket");
      });

      socket.on("candle_update", (data: KafkaCandle) => {
        const newCandle: CandleData = {
          x: new Date(data.openTime).getTime(),
          y: [data.open, data.high, data.low, data.close],
          volume: data.volume,
        };

        setSeries((prev) => {
          const oldData = prev[0]?.data || [];
          const index = oldData.findIndex(
            (d) => d.x === newCandle.x
          );

          let updated;
          if (index !== -1) {
            updated = [...oldData];
            updated[index] = newCandle;
          } else {
            updated = [...oldData, newCandle];
            if (updated.length > 100) updated.shift(); 
          }

          return [{ data: updated }];
        });
      });

      socket.on("disconnect", () => console.log("⚠️ Disconnected from WebSocket"));
      socket.on("error", (err) => console.error("WebSocket error:", err));
    }

    if (mode === "history") {
      fetchHistoricalData();
      if (socket) socket.disconnect();
    } else {
      connectWebSocket();
    }

    return () => {
      isMounted = false;
      if (socket) socket.disconnect();
    };
  }, [mode]);

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: "candlestick",
      height: 350,
      background: "transparent",
      animations: { enabled: mode === "realtime" },
      toolbar: { show: true },
    },
    title: {
      text: `BTC/USDT - ${
        mode === "history" ? "Historical (30m)" : "Real-Time"
      }`,
      align: "left",
    },
    xaxis: {
      type: "datetime",
      labels: { datetimeUTC: false },
    },
    yaxis: {
      tooltip: { enabled: true },
    },
    tooltip: {
      shared: true,
      x: { show: true },
    },
  };

  return (
    <div className="space-y-4">
      <Tabs
        defaultValue="history"
        onValueChange={(value) => setMode(value as "history" | "realtime")}
      >
        <TabsList>
          <TabsTrigger value="history">Historical (30m)</TabsTrigger>
          <TabsTrigger value="realtime">Real-Time</TabsTrigger>
        </TabsList>

        <TabsContent value="history" className="bg-white rounded-2xl shadow p-4">
          {isLoading ? (
            <div className="flex items-center justify-center h-[350px]">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900" />
            </div>
          ) : series[0]?.data?.length > 0 ? (
            <Chart
              options={options}
              series={series}
              type="candlestick"
              height={350}
            />
          ) : (
            <div className="flex items-center justify-center h-[350px] text-gray-500">
              No data available
            </div>
          )}
        </TabsContent>

        <TabsContent value="realtime" className="bg-white rounded-2xl shadow p-4">
          {series[0]?.data?.length > 0 ? (
            <Chart
              options={options}
              series={series}
              type="candlestick"
              height={350}
            />
          ) : (
            <div className="flex items-center justify-center h-[350px] text-gray-500">
              Waiting for real-time data...
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
