"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import axios from "axios";
import { Spin, Typography } from "antd";
import type { ApexOptions } from "apexcharts";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

type ApexAxisChartSeries = {
  name?: string;
  type?: string;
  color?: string;
  data: Array<{ x: number; y: number | number[] | null }>;
}[];

interface CandleData {
  x: number;
  y: [number, number, number, number];
  volume?: number;
}

// Helper functions for calculating technical indicators
function calculateSMA(data: CandleData[], period: number): Array<{ x: number; y: number | null }> {
  const result: Array<{ x: number; y: number | null }> = [];
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push({ x: data[i].x, y: null });
    } else {
      let sum = 0;
      for (let j = 0; j < period; j++) {
        sum += data[i - j].y[3]; // Close price
      }
      result.push({ x: data[i].x, y: sum / period });
    }
  }
  return result;
}

function calculateEMA(data: CandleData[], period: number): Array<{ x: number; y: number | null }> {
  const result: Array<{ x: number; y: number | null }> = [];
  const multiplier = 2 / (period + 1);
  
  // Start with SMA for first value
  let ema = 0;
  for (let i = 0; i < period && i < data.length; i++) {
    ema += data[i].y[3];
  }
  ema = ema / Math.min(period, data.length);
  
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1) {
      result.push({ x: data[i].x, y: null });
    } else if (i === period - 1) {
      result.push({ x: data[i].x, y: ema });
    } else {
      ema = (data[i].y[3] - ema) * multiplier + ema;
      result.push({ x: data[i].x, y: ema });
    }
  }
  return result;
}

function calculateBollingerBands(data: CandleData[], period: number = 20, stdDev: number = 2): {
  upper: Array<{ x: number; y: number | null }>;
  middle: Array<{ x: number; y: number | null }>;
  lower: Array<{ x: number; y: number | null }>;
} {
  const middle = calculateSMA(data, period);
  const upper: Array<{ x: number; y: number | null }> = [];
  const lower: Array<{ x: number; y: number | null }> = [];
  
  for (let i = 0; i < data.length; i++) {
    if (i < period - 1 || middle[i].y === null) {
      upper.push({ x: data[i].x, y: null });
      lower.push({ x: data[i].x, y: null });
    } else {
      let sum = 0;
      const avg = middle[i].y!;
      for (let j = 0; j < period; j++) {
        sum += Math.pow(data[i - j].y[3] - avg, 2);
      }
      const std = Math.sqrt(sum / period);
      upper.push({ x: data[i].x, y: avg + stdDev * std });
      lower.push({ x: data[i].x, y: avg - stdDev * std });
    }
  }
  
  return { upper, middle, lower };
}

// COMMENTED OUT FOR MONGODB ONLY TESTING - Only used in WebSocket code
// interface BackendCandle {
//   symbol: string;
//   interval: string;
//   openTime: number;
//   closeTime: number;
//   open: number;
//   high: number;
//   low: number;
//   close: number;
//   volume: number;
//   quoteVolume?: number;
//   trades?: number;
//   x: boolean;
// }

// COMMENTED OUT FOR MONGODB ONLY TESTING - WebSocket message interface not needed
// interface BackendMessage {
//   type: "initial" | "latest" | "update" | "realtime";
//   candles?: BackendCandle[];
//   candle?: BackendCandle;
// }

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

interface IndicatorConfig {
  enabled: boolean;
  color: string;
  label: string;
  period?: number;
}

interface TechnicalIndicatorsConfig {
  ma7: IndicatorConfig;
  ma25: IndicatorConfig;
  ma99: IndicatorConfig;
  ema12: IndicatorConfig;
  ema26: IndicatorConfig;
  ema50: IndicatorConfig;
  bollinger: IndicatorConfig;
}

interface ChartEmbeddedProps {
  symbol: string;
  mode: "realtime" | "7day" | "30day" | "6month" | "1year";
  indicators?: TechnicalIndicatorsConfig;
}

export default function ChartEmbedded({ symbol, mode, indicators }: ChartEmbeddedProps) {
  const [candleData, setCandleData] = useState<CandleData[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMorePast, setIsLoadingMorePast] = useState(false);
  const [hasMorePast, setHasMorePast] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const chartRef = useRef<any>(null);
  const zoomRangeRef = useRef<{ min: number; max: number } | null>(null);
  const currentSymbolRef = useRef<string>(symbol);
  const isChangingSymbolRef = useRef<boolean>(false);
  const loadedRangeRef = useRef<{ min: number; max: number } | null>(null);
  const loadMorePastRef = useRef<(() => void | Promise<void>) | null>(null);
  const lastLoadMoreTimeRef = useRef<number>(0);
  // Share same API/WS base strategy as TradingDashboard - MongoDB only mode
  const API_BASE =
    process.env.NEXT_PUBLIC_API_BASE ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";  // Changed for local MongoDB testing
  // const WS_BASE = API_BASE.replace(/^http/, "ws"); // COMMENTED OUT - WebSocket not used in MongoDB-only mode

  useEffect(() => {
    let isMounted = true;
    const connectTimeout: NodeJS.Timeout | null = null;
    let connectDelay: NodeJS.Timeout | null = null;
    
    // Mark that we're changing symbol to prevent reconnections
    isChangingSymbolRef.current = true;

    // Reset lazy-load state when symbol or mode changes
    setCandleData([]);
    setHasMorePast(true);
    setIsLoadingMorePast(false);
    loadedRangeRef.current = null;
    
    // Close existing WebSocket FIRST before updating symbol
    if (wsRef.current) {
      wsRef.current.onmessage = null;
      wsRef.current.onerror = null;
      wsRef.current.onclose = null;
      wsRef.current.onopen = null;
      try {
        wsRef.current.close();
      } catch {
        // Ignore errors
      }
      wsRef.current = null;
    }
    
    // Cancel any pending reconnections
    if (reconnectTimer.current) {
      clearTimeout(reconnectTimer.current);
      reconnectTimer.current = null;
    }
    
    // Update current symbol ref AFTER closing old connection
    currentSymbolRef.current = symbol;
    
    // Small delay to ensure old connection is fully closed
    connectDelay = setTimeout(() => {
      isChangingSymbolRef.current = false;
    }, 100);

    async function fetchHistoricalData() {
      try {
        setIsLoading(true);
        // Map mode to collection name - MongoDB only mode includes realtime
        const collectionMap: Record<string, string> = {
          "realtime": "5m_kline",  // Use 5m data for realtime in MongoDB-only mode
          "7day": "5m_kline",
          "30day": "1h_kline",
          "6month": "4h_kline",
          "1year": "1d_kline",
        };
        const collection = collectionMap[mode];
        
        if (!collection) {
          console.error("Invalid mode for historical data:", mode);
          if (isMounted) setCandleData([]);
          return;
        }

        const res = await axios.get<ApiResponse>(`${API_BASE}/ohlc`, {
          params: { symbol: symbol, collection: collection, limit: 200 },
        });

        if (!isMounted) return;

        const formatted: CandleData[] = (res.data?.candles || []).map((d) => ({
          x: new Date(d.openTime).getTime(),
          y: d.y,
          volume: d.volume,
        }));

        setCandleData(formatted);

        // Initialize loaded range for lazy-loading
        if (formatted.length > 0) {
          const min = formatted[0].x;
          const max = formatted[formatted.length - 1].x;
          loadedRangeRef.current = { min, max };
          setHasMorePast(true);
        } else {
          loadedRangeRef.current = null;
          setHasMorePast(false);
        }
      } catch (err) {
        console.error("❌ Error fetching historical data:", err);
        if (isMounted) setCandleData([]);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    }

    // COMMENTED OUT FOR MONGODB ONLY TESTING - WebSocket requires Redis/Kafka
    /* function connectWebSocket() {
      // Don't connect if we're changing symbol
      if (isChangingSymbolRef.current) {
        return;
      }
      
      const targetSymbol = currentSymbolRef.current;
      
      // Don't create new connection if one already exists and is open
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        return;
      }
      
      if (wsRef.current) {
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.onopen = null;
        try {
          wsRef.current.close();
        } catch (e) {
          // Ignore errors
        }
        wsRef.current = null;
      }

      // Check again before creating WebSocket
      if (currentSymbolRef.current !== targetSymbol || isChangingSymbolRef.current) {
        return;
      }

      const ws = new WebSocket(`${WS_BASE}/ws/kline?symbol=${targetSymbol}`);
      wsRef.current = ws;

      ws.onopen = () => {
        // Connection successful
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data: BackendMessage = JSON.parse(event.data);
          const currentSymbol = currentSymbolRef.current;
          
          // Only process if symbol matches current symbol
          if (data.candles && data.candles.length > 0 && data.candles[0].symbol && data.candles[0].symbol !== currentSymbol) {
            return;
          }
          if (data.candle && data.candle.symbol && data.candle.symbol !== currentSymbol) {
            return;
          }

          const convertCandle = (candle: BackendCandle): CandleData => ({
            x: candle.openTime,
            y: [candle.open, candle.high, candle.low, candle.close],
            volume: candle.volume,
          });

          setSeries((prev) => {
            const oldData = prev[0]?.data || [];
            let updated = [...oldData];

            if (data.type === "initial" && data.candles) {
              updated = data.candles.map(convertCandle);
              zoomRangeRef.current = null;
            } else if (data.type === "latest" && data.candle) {
              const newCandle = convertCandle(data.candle);
              const index = updated.findIndex((d) => d.x === newCandle.x);
              if (index !== -1) {
                updated[index] = newCandle;
              } else {
                updated.push(newCandle);
              }
            } else if (data.type === "update" && data.candle) {
              const newCandle = convertCandle(data.candle);
              const index = updated.findIndex((d) => d.x === newCandle.x);
              if (index !== -1) {
                updated[index] = newCandle;
              } else {
                updated.push(newCandle);
              }
            } else if (data.type === "realtime" && data.candle) {
              const newCandle = convertCandle(data.candle);
              const index = updated.findIndex((d) => d.x === newCandle.x);
              if (index !== -1) {
                updated[index] = newCandle;
              } else {
                updated.push(newCandle);
                if (updated.length > 200) updated.shift();
              }
            }

            updated.sort((a, b) => a.x - b.x);

            if (zoomRangeRef.current && chartRef.current) {
              setTimeout(() => {
                if (chartRef.current && zoomRangeRef.current) {
                  chartRef.current.updateOptions({
                    xaxis: {
                      range: [zoomRangeRef.current.min, zoomRangeRef.current.max],
                    },
                  }, false, false);
                }
              }, 50);
            }

            return [{ data: updated }];
          });
        } catch (err) {
          console.error("Error parsing WebSocket message:", err);
        }
      };

      ws.onclose = () => {
        // Clear the ref if this was the current connection
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        
        if (!isMounted || isChangingSymbolRef.current) {
          return;
        }
        
        const currentSymbol = currentSymbolRef.current;
        const expectedSymbol = targetSymbol; // Capture at connection time
        
        // Only reconnect if symbol hasn't changed and we're not changing symbols
        if (currentSymbol === expectedSymbol && !isChangingSymbolRef.current) {
          reconnectTimer.current = setTimeout(() => {
            if (currentSymbolRef.current === expectedSymbol && isMounted && !isChangingSymbolRef.current) {
              connectWebSocket();
            }
          }, 2000);
        }
      };

      ws.onerror = (err) => {
        console.error("Chart WebSocket error:", err);
      };
    } */

    // COMMENTED OUT FOR MONGODB ONLY TESTING - Realtime mode requires WebSocket/Redis/Kafka
    // if (mode === "realtime") {
    //   // Small delay to ensure cleanup is complete before connecting
    //   connectTimeout = setTimeout(() => {
    //     if (isMounted && !isChangingSymbolRef.current) {
    //       connectWebSocket();
    //     }
    //   }, 150);
    // } else {
      // For all modes (including realtime), fetch from MongoDB in MongoDB-only mode
      fetchHistoricalData();

      // Safely close any existing WebSocket connection without touching event handlers.
      // Cast to `any` here to avoid over‑narrowing issues with the ref type in strict mode,
      // since this is just best‑effort cleanup.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const ws: any = wsRef.current;
      if (ws) {
        try {
          ws.close();
        } catch {
          // Ignore errors
        } finally {
          wsRef.current = null;
        }
      }
    // }

    return () => {
      isMounted = false;
      isChangingSymbolRef.current = true; // Prevent reconnections during cleanup
      
      if (connectTimeout) {
        clearTimeout(connectTimeout);
      }
      if (connectDelay) {
        clearTimeout(connectDelay);
      }
      
      if (wsRef.current) {
        wsRef.current.onmessage = null;
        wsRef.current.onerror = null;
        wsRef.current.onclose = null;
        wsRef.current.onopen = null;
        try {
          wsRef.current.close();
        } catch {
          // Ignore errors
        }
        wsRef.current = null;
      }
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };
  }, [mode, symbol, API_BASE]);

  // Lazy-load more historical candles when user scrolls/pans near the left edge
  useEffect(() => {
    loadMorePastRef.current = async () => {
      // MongoDB-only mode: all modes use historical data
      // if (mode === "realtime") return;  // COMMENTED OUT - realtime now uses MongoDB

      const loadedRange = loadedRangeRef.current;
      if (!loadedRange) return;
      if (!hasMorePast || isLoadingMorePast) return;

      const now = Date.now();
      if (now - lastLoadMoreTimeRef.current < 1000) {
        // debounce: don't load more than once per second
        return;
      }
      lastLoadMoreTimeRef.current = now;

      const collectionMap: Record<string, string> = {
        "realtime": "5m_kline",  // Use 5m data for realtime in MongoDB-only mode
        "7day": "5m_kline",
        "30day": "1h_kline",
        "6month": "4h_kline",
        "1year": "1d_kline",
      };
      const collection = collectionMap[mode];
      if (!collection) return;

      setIsLoadingMorePast(true);
      try {
        const end = loadedRange.min - 1;
        const res = await axios.get<ApiResponse>(`${API_BASE}/ohlc`, {
          params: {
            symbol,
            collection,
            limit: 200,
            end,
          },
        });

        const candles = res.data?.candles || [];
        if (candles.length === 0) {
          setHasMorePast(false);
          return;
        }

        const newData: CandleData[] = candles.map((d) => ({
          x: new Date(d.openTime).getTime(),
          y: d.y,
          volume: d.volume,
        }));

        // Preserve current viewport before updating data
        const chart = chartRef.current;
        const prevMinVisible =
          chart?.w?.globals?.minX !== undefined ? chart.w.globals.minX : null;
        const prevMaxVisible =
          chart?.w?.globals?.maxX !== undefined ? chart.w.globals.maxX : null;

        setCandleData((prev) => {
          const existing = prev || [];
          const merged = [...newData, ...existing];

          // Deduplicate by x (openTime)
          const dedupMap = new Map<number, CandleData>();
          for (const c of merged) {
            dedupMap.set(c.x, c);
          }
          const result = Array.from(dedupMap.values()).sort(
            (a, b) => a.x - b.x
          );

          if (result.length > 0) {
            const min = result[0].x;
            const max = result[result.length - 1].x;
            loadedRangeRef.current = { min, max };
          }

          return result;
        });

        // Restore previous viewport after data is extended
        if (
          chart &&
          prevMinVisible !== null &&
          prevMaxVisible !== null &&
          !isNaN(prevMinVisible) &&
          !isNaN(prevMaxVisible)
        ) {
          setTimeout(() => {
            try {
              chart.updateOptions(
                {
                  xaxis: {
                    min: prevMinVisible,
                    max: prevMaxVisible,
                  },
                },
                false,
                false
              );
            } catch {
              // ignore chart update errors
            }
          }, 0);
        }
      } catch (err) {
        console.error("❌ Error loading more historical data:", err);
      } finally {
        setIsLoadingMorePast(false);
      }
    };
  }, [API_BASE, mode, symbol, hasMorePast, isLoadingMorePast]);

  // Calculate series with indicators
  const series = useMemo(() => {
    // Always return at least a candlestick series (even if empty) to avoid ApexCharts errors
    const emptyCandleSeries: ApexAxisChartSeries = [{
      name: "Candles",
      type: "candlestick",
      data: [],
    }];

    if (!candleData || candleData.length === 0) {
      return emptyCandleSeries;
    }

    const result: ApexAxisChartSeries = [
      {
        name: "Candles",
        type: "candlestick",
        data: candleData,
      },
    ];

    if (!indicators) {
      return result;
    }

    // Add Moving Averages
    if (indicators.ma7?.enabled) {
      result.push({
        name: indicators.ma7.label,
        type: "line",
        data: calculateSMA(candleData, indicators.ma7.period || 7),
        color: indicators.ma7.color,
      });
    }
    if (indicators.ma25?.enabled) {
      result.push({
        name: indicators.ma25.label,
        type: "line",
        data: calculateSMA(candleData, indicators.ma25.period || 25),
        color: indicators.ma25.color,
      });
    }
    if (indicators.ma99?.enabled) {
      result.push({
        name: indicators.ma99.label,
        type: "line",
        data: calculateSMA(candleData, indicators.ma99.period || 99),
        color: indicators.ma99.color,
      });
    }

    // Add Exponential Moving Averages
    if (indicators.ema12?.enabled) {
      result.push({
        name: indicators.ema12.label,
        type: "line",
        data: calculateEMA(candleData, indicators.ema12.period || 12),
        color: indicators.ema12.color,
      });
    }
    if (indicators.ema26?.enabled) {
      result.push({
        name: indicators.ema26.label,
        type: "line",
        data: calculateEMA(candleData, indicators.ema26.period || 26),
        color: indicators.ema26.color,
      });
    }
    if (indicators.ema50?.enabled) {
      result.push({
        name: indicators.ema50.label,
        type: "line",
        data: calculateEMA(candleData, indicators.ema50.period || 50),
        color: indicators.ema50.color,
      });
    }

    // Add Bollinger Bands
    if (indicators.bollinger?.enabled) {
      const bb = calculateBollingerBands(candleData, indicators.bollinger.period || 20);
      result.push({
        name: "BB Upper",
        type: "line",
        data: bb.upper,
        color: indicators.bollinger.color,
      });
      result.push({
        name: "BB Middle",
        type: "line",
        data: bb.middle,
        color: indicators.bollinger.color,
      });
      result.push({
        name: "BB Lower",
        type: "line",
        data: bb.lower,
        color: indicators.bollinger.color,
      });
    }

    return result;
  }, [candleData, indicators]);

  // Calculate dynamic stroke widths based on series types
  const strokeWidths = useMemo(() => {
    // Generate stroke width array: 1 for candlestick, 2 for line indicators
    if (!series || series.length === 0) return [1];
    return series.map((s) => {
      if (s.type === 'candlestick') return 1;
      return 2; // Line indicators
    });
  }, [series]);

  const options: ApexOptions = useMemo(() => ({
    chart: {
      type: "candlestick",
      height: "100%",
      background: "transparent",
      animations: { 
        enabled: false,  // Disabled for MongoDB-only mode (no real-time updates)
        speed: 800,
        animateGradually: {
          enabled: true,
          delay: 150
        }
      },
      toolbar: { 
        show: true,
        offsetX: 0,
        offsetY: 0,
        tools: {
          download: false,
          selection: false,
          zoom: true,
          zoomin: true,
          zoomout: true,
          pan: true,
          reset: true,
        },
      },
      zoom: {
        enabled: true,
        type: 'x',
        autoScaleYaxis: true,
      },
      scrollbar: {
        enabled: true,
        offsetY: 0,
      },
      events: {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        mounted: (chartContext: any) => {
          chartRef.current = chartContext;
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        updated: (chartContext: any) => {
          chartRef.current = chartContext;
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        zoomed: (chartContext: any, { xaxis }: any) => {
          if (xaxis && xaxis.min && xaxis.max) {
            zoomRangeRef.current = {
              min: xaxis.min,
              max: xaxis.max,
            };
          }
        },
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        scrolled: (chartContext: any, { xaxis }: any) => {
          // Trigger lazy-load when user scrolls near the left edge of loaded data
          if (!xaxis || typeof xaxis.min !== "number" || typeof xaxis.max !== "number") {
            return;
          }
          // MongoDB-only mode: all modes use historical data
          // if (mode === "realtime") return;  // COMMENTED OUT - realtime now uses MongoDB

          const loadedRange = loadedRangeRef.current;
          if (!loadedRange) return;
          if (!hasMorePast || isLoadingMorePast) return;

          const totalRange = loadedRange.max - loadedRange.min;
          if (totalRange <= 0) return;

          const threshold = totalRange * 0.05; // 5% of the loaded range

          if (xaxis.min <= loadedRange.min + threshold) {
            if (loadMorePastRef.current) {
              loadMorePastRef.current();
            }
          }
        },
      },
      fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
    },
    stroke: {
      width: strokeWidths,
      curve: 'smooth',
    },
    plotOptions: {
      candlestick: {
        colors: {
          upward: '#10b981',
          downward: '#ef4444'
        },
        wick: {
          useFillColor: true
        },
        columnWidth: '80%',
      },
    },
    grid: {
      borderColor: 'rgba(55, 65, 81, 0.3)',
      strokeDashArray: 0,
      xaxis: {
        lines: {
          show: true,
        }
      },
      yaxis: {
        lines: {
          show: true,
        }
      },
    },
    xaxis: {
      type: "datetime",
      labels: { 
        datetimeUTC: false,
        style: {
          colors: '#9ca3af',
          fontSize: '12px',
          fontFamily: 'Inter, system-ui, sans-serif',
        },
        datetimeFormatter: {
          year: 'yyyy',
          month: 'MMM dd',
          day: 'dd MMM',
          hour: 'HH:mm',
        },
      },
      axisBorder: {
        color: 'rgba(55, 65, 81, 0.3)',
      },
      axisTicks: {
        color: 'rgba(55, 65, 81, 0.3)',
      },
    },
    yaxis: series.length > 0 ? series.map((s, index) => {
      // Y-axis for candlestick and all indicators (they share the same price axis)
      return {
        seriesName: s.name,
        show: index === 0, // Only show the first y-axis (Candles)
        position: "right" as const,
        labels: {
          style: {
            colors: '#9ca3af',
            fontSize: '12px',
            fontFamily: 'Inter, system-ui, sans-serif',
          },
          formatter: (value: number) => {
            if (value === null || value === undefined) return '';
            return value.toLocaleString('en-US', {
              minimumFractionDigits: 2,
              maximumFractionDigits: 2,
            });
          },
        },
        tooltip: { enabled: index === 0 },
        forceNiceScale: true,
      };
    }) : [{
      show: true,
      position: "right" as const,
      labels: {
        style: {
          colors: '#9ca3af',
          fontSize: '12px',
          fontFamily: 'Inter, system-ui, sans-serif',
        },
      },
      forceNiceScale: true,
    }],
    tooltip: {
      theme: 'dark',
      shared: true,
      x: { 
        show: true,
        format: 'dd MMM yyyy HH:mm',
      },
      style: {
        fontSize: '12px',
        fontFamily: 'Inter, system-ui, sans-serif',
      },
    },
    dataLabels: { enabled: false },
    legend: {
      show: true,
      showForSingleSeries: false,
      position: 'top',
      horizontalAlign: 'left',
      floating: true,
      offsetY: 0,
      labels: {
        colors: '#9ca3af',
      },
      markers: {
        size: 6,
        offsetX: 0,
        offsetY: 0,
      },
      itemMargin: {
        horizontal: 8,
        vertical: 4,
      },
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }), [mode, hasMorePast, isLoadingMorePast, strokeWidths, series]);

  if (isLoading && mode !== "realtime") {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <Spin size="large" />
      </div>
    );
  }

  if (candleData.length === 0) {
    return (
      <div
        style={{
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "#9ca3af",
          textAlign: "center",
        }}
      >
        {mode === "realtime" ? (
          <div>
            <div
              style={{
                marginBottom: 12,
                fontSize: 24,
                color: "#10b981",
              }}
            >
              ●
            </div>
            <Typography.Text style={{ color: "#e5e7eb" }}>
              Waiting for real-time data...
            </Typography.Text>
          </div>
        ) : (
          <Typography.Text style={{ color: "#e5e7eb" }}>
            No data available
          </Typography.Text>
        )}
      </div>
    );
  }

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <Chart
        key={`${mode}-${symbol}`}
        options={options}
        series={series}
        type="candlestick"
        height="100%"
      />
    </div>
  );
}


