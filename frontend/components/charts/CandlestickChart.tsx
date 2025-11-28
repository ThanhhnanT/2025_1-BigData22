"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import axios from "axios";
import { io, Socket } from "socket.io-client";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface CandleData {
  x: number; 
  y: [number, number, number, number]; 
  volume: number;
}

interface BinanceKline {
  e: string;     // Event type
  E: number;     // Event time
  s: string;     // Symbol
  k: {
    t: number;   // Kline start time
    T: number;   // Kline close time
    s: string;   // Symbol
    i: string;   // Interval
    f: number;   // First trade ID
    L: number;   // Last trade ID
    o: string;   // Open price
    c: string;   // Close price
    h: string;   // High price
    l: string;   // Low price
    v: string;   // Base asset volume
    n: number;   // Number of trades
    x: boolean;  // Is this kline closed?
    q: string;   // Quote asset volume
    V: string;   // Taker buy base asset volume
    Q: string;   // Taker buy quote asset volume
    B: string;   // Ignore
  };
}

interface ApiResponse {
  symbol: string;
  interval: string;
  count: number;
  candles: {
    openTime: number;
    x: string;
    y: [number, number, number, number];
    volume: number;
  }[];
}

export default function CandlestickChart() {
  const [series, setSeries] = useState<{ data: CandleData[] }[]>([{ data: [] }]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let socket: Socket | undefined;
    let isMounted = true;

    async function fetchHistoricalData() {
      try {
        setIsLoading(true);
        const res = await axios.get<ApiResponse>("http://localhost:4000/api/candles", {
          params: {
            symbol: "BTCUSDT",
            interval: "5m",
            limit: 100
          },
        });

        if (!isMounted) return;

        const formatted = res.data.candles.map((candle) => ({
          x: candle.openTime,
          y: candle.y,
          volume: candle.volume
        }));

        setSeries([{ data: formatted }]);
        console.log("📈 Loaded historical data:", formatted.length, "candles");
        
        connectWebSocket();
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

      socket.on("candle_update", (data: BinanceKline) => {
        const k = data.k;
        const newCandle: CandleData = {
          x: k.t, // Kline start time
          y: [
            parseFloat(k.o), // Open
            parseFloat(k.h), // High
            parseFloat(k.l), // Low
            parseFloat(k.c), // Close
          ],
          volume: parseFloat(k.v), // Base asset volume
        };

        setSeries((prev) => {
          const oldData = prev[0]?.data || [];
          
          if (k.x === true) {
            console.log("📈 Closed candle - Adding to chart");
            const index = oldData.findIndex((d) => d.x === newCandle.x);
            if (index === -1) {
              const updated = [...oldData, newCandle].sort((a, b) => a.x - b.x);
              if (updated.length > 100) updated.shift();
              console.log("📊 Chart data updated, total candles:", updated.length);
              return [{ data: updated }];
            }
          } 
          else {
            const lastIndex = oldData.length - 1;
            if (lastIndex >= 0 && oldData[lastIndex].x === newCandle.x) {
              console.log("🔄 Updating current candle");
              const updated = [...oldData];
              updated[lastIndex] = newCandle;
              return [{ data: updated }];
            } else if (oldData.length === 0 || newCandle.x > oldData[lastIndex].x) {
              console.log("➕ Adding new candle");
              return [{ data: [...oldData, newCandle] }];
            }
          }
          
          return prev;
        });
      });

      socket.on("disconnect", () => console.log("⚠️ Disconnected from WebSocket"));
      socket.on("error", (err) => console.error("WebSocket error:", err));
    }

    fetchHistoricalData();

    return () => {
      isMounted = false;
      if (socket) {
        socket.disconnect();
        socket = undefined;
      }
    };
  }, []);

  const options: ApexCharts.ApexOptions = {
    chart: {
      type: "candlestick",
      height: 350,
      background: "transparent",
      animations: { enabled: true },
      toolbar: {
        show: true,
        tools: {
          download: true,
          selection: true,
          zoom: true,
          zoomin: true,
          zoomout: true,
          pan: true,
          reset: true
        }
      }
    },
    title: {
      text: "BTC/USDT - 5 Minutes",
      align: "left",
      style: {
        fontSize: '16px',
        fontWeight: 'bold'
      }
    },
    xaxis: {
      type: "datetime",
      labels: {
        datetimeUTC: false,
        formatter: function(val: string) {
          return new Date(parseInt(val)).toLocaleString();
        }
      },
      tickAmount: 8
    },
    yaxis: {
      tooltip: { enabled: true },
      labels: {
        formatter: (val: number) => val.toFixed(2)
      },
      decimalsInFloat: 2
    },
    tooltip: {
      enabled: true,
      theme: "dark",
      shared: true,
      custom: ({ seriesIndex, dataPointIndex, w }) => {
        const o = w.globals.seriesCandleO[seriesIndex][dataPointIndex];
        const h = w.globals.seriesCandleH[seriesIndex][dataPointIndex];
        const l = w.globals.seriesCandleL[seriesIndex][dataPointIndex];
        const c = w.globals.seriesCandleC[seriesIndex][dataPointIndex];
        const vol = w.globals.series[seriesIndex][dataPointIndex].volume;
        
        return `
          <div class="p-2">
            <div class="text-xs text-gray-400">
              ${new Date(w.globals.seriesX[seriesIndex][dataPointIndex]).toLocaleString()}
            </div>
            <div class="grid grid-cols-2 gap-2 text-sm mt-1">
              <div>O: ${o.toFixed(2)}</div>
              <div>H: ${h.toFixed(2)}</div>
              <div>L: ${l.toFixed(2)}</div>
              <div>C: ${c.toFixed(2)}</div>
              ${vol ? `<div class="col-span-2">Vol: ${vol.toFixed(4)}</div>` : ''}
            </div>
          </div>
        `;
      }
    },
    plotOptions: {
      candlestick: {
        colors: {
          upward: '#26A69A',
          downward: '#EF5350'
        },
        wick: {
          useFillColor: true
        }
      }
    },
    grid: {
      borderColor: '#90A4AE',
      strokeDashArray: 2
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-white rounded-2xl shadow-lg p-4">
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
            <div className="text-center">
              <div className="animate-pulse mb-2">⏳</div>
              <p>Loading chart data...</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
