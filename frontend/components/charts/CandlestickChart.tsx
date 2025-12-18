"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import axios from "axios";
import { Layout, Select, Button, Badge, Typography, Space } from "antd";
import Link from "next/link";

const Chart = dynamic(() => import("react-apexcharts"), { ssr: false });

interface CandleData {
  x: number;
  y: [number, number, number, number];
  volume?: number;
}

interface BackendCandle {
  symbol: string;
  interval: string;
  openTime: number;
  closeTime: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  quoteVolume?: number;
  trades?: number;
  x: boolean;
}

interface BackendMessage {
  type: "initial" | "latest" | "update" | "realtime";
  candles?: BackendCandle[];
  candle?: BackendCandle;
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

const { Header, Content } = Layout;
const { Text } = Typography;

export default function CandlestickChart() {
  const [mode, setMode] = useState<"realtime" | "7day" | "30day" | "6month" | "1year">("realtime");
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [symbols, setSymbols] = useState<string[]>([]);
  const [series, setSeries] = useState<{ data: CandleData[] }[]>([{ data: [] }]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMorePast, setIsLoadingMorePast] = useState(false);
  const [hasMorePast, setHasMorePast] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
  const chartRef = useRef<any>(null);
  const zoomRangeRef = useRef<{ min: number; max: number } | null>(null);
  const loadedRangeRef = useRef<{ min: number; max: number } | null>(null);
  const loadMorePastRef = useRef<(() => void | Promise<void>) | null>(null);
  const lastLoadMoreTimeRef = useRef<number>(0);
  const currentSymbolRef = useRef<string>(symbol);
  const isChangingSymbolRef = useRef<boolean>(false);
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const WS_BASE = API_BASE.replace(/^http/, "ws");

  useEffect(() => {
    async function fetchSymbols() {
      try {
        const res = await axios.get<{ symbols: string[] }>(`${API_BASE}/symbols`);
        const fetchedSymbols = res.data.symbols || [];
        setSymbols(fetchedSymbols);
      } catch (err) {
        console.error("Error fetching symbols:", err);
        setSymbols(["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT"]);
      }
    }
    fetchSymbols();
  }, [API_BASE]);

  useEffect(() => {
    let isMounted = true;
    let connectTimeout: NodeJS.Timeout | null = null;
    let connectDelay: NodeJS.Timeout | null = null;
    
    // Mark that we're changing symbol to prevent reconnections
    isChangingSymbolRef.current = true;
    
    // Close existing WebSocket FIRST before updating symbol
    const existingWs = wsRef.current;
    if (existingWs) {
      existingWs.onmessage = null; // Remove message handler immediately
      existingWs.onerror = null;
      existingWs.onclose = null;
      existingWs.onopen = null;
      try {
        existingWs.close();
      } catch (e) {
        // Ignore errors when closing
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
        // Map mode to collection name
        const collectionMap: Record<string, string> = {
          "7day": "5m_kline",
          "30day": "1h_kline",
          "6month": "4h_kline",
          "1year": "1d_kline",
        };
        const collection = collectionMap[mode];
        
        if (!collection) {
          console.error("Invalid mode for historical data:", mode);
          if (isMounted) setSeries([{ data: [] }]);
          return;
        }

        const res = await axios.get<ApiResponse>(`${API_BASE}/ohlc`, {
          params: { symbol: symbol, collection: collection, limit: 200 },
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
      // Don't connect if we're changing symbol
      if (isChangingSymbolRef.current) {
        return;
      }
      
      const targetSymbol = currentSymbolRef.current;
      
      // Don't create new connection if one already exists
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        return;
      }
      
      const existingWs = wsRef.current;
      if (existingWs) {
        existingWs.onmessage = null;
        existingWs.onerror = null;
        existingWs.onclose = null;
        existingWs.onopen = null;
        try {
          existingWs.close();
        } catch (e) {
          // Ignore errors
        }
        wsRef.current = null;
      }

      // Check again right before creating WebSocket to ensure symbol hasn't changed
      const currentSymbol = currentSymbolRef.current;
      if (currentSymbol !== targetSymbol || isChangingSymbolRef.current) {
        return;
      }

      const wsUrl = `${WS_BASE}/ws/kline?symbol=${targetSymbol}`;
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        // Connection successful
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data: BackendMessage = JSON.parse(event.data);
          const currentSymbol = currentSymbolRef.current;
          
          // Only process if symbol matches current symbol (use ref to get latest value)
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
              // Initialize loaded range for lazy-loading
              if (updated.length > 0) {
                const min = updated[0].x;
                const max = updated[updated.length - 1].x;
                loadedRangeRef.current = { min, max };
                setHasMorePast(true);
              }
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
                // Always update existing candle in place to avoid flickering
                // This ensures the forming candle stays visible and just updates
                updated[index] = newCandle;
              } else {
                // Only add new candle if it's the latest (to avoid adding incomplete candles in the middle)
                const isLatest = updated.length === 0 || newCandle.x >= updated[updated.length - 1].x;
                if (isLatest) {
                  // Remove any existing incomplete candles at the end before adding new one
                  // This prevents duplicate incomplete candles
                  while (updated.length > 0 && updated[updated.length - 1].x >= newCandle.x) {
                    updated.pop();
                  }
                  updated.push(newCandle);
                  if (updated.length > 200) updated.shift();
                } else {
                  // If it's not the latest, it might be a delayed message, ignore it
                }
              }
            }

            updated.sort((a, b) => a.x - b.x);

            // Update loaded range
            if (updated.length > 0) {
              const min = updated[0].x;
              const max = updated[updated.length - 1].x;
              if (!loadedRangeRef.current || min < loadedRangeRef.current.min) {
                loadedRangeRef.current = { min, max };
              }
            }

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

      ws.onclose = (event) => {
        // Clear the ref if this was the current connection
        if (wsRef.current === ws) {
          wsRef.current = null;
        }
        
        if (!isMounted || isChangingSymbolRef.current) {
          return;
        }
        
        const currentSymbol = currentSymbolRef.current;
        
        // Only reconnect if symbol hasn't changed and we're not changing symbols
        if (currentSymbol === targetSymbol && !isChangingSymbolRef.current) {
          reconnectTimer.current = setTimeout(() => {
            // Triple-check before reconnecting
            if (currentSymbolRef.current === targetSymbol && isMounted && !isChangingSymbolRef.current) {
              connectWebSocket();
            }
          }, 2000);
        }
      };

      ws.onerror = (err) => {
        console.error("WebSocket error:", err);
      };
    }

    if (mode === "realtime") {
      // Small delay to ensure cleanup is complete before connecting
      connectTimeout = setTimeout(() => {
        if (isMounted && !isChangingSymbolRef.current) {
          connectWebSocket();
        }
      }, 150);
    } else {
      // For historical modes (7day, 30day, 6month, 1year), fetch from MongoDB
      fetchHistoricalData();
      // Close WebSocket if it exists
      const currentWs = wsRef.current;
      if (currentWs) {
        currentWs.onmessage = null;
        currentWs.onerror = null;
        currentWs.onclose = null;
        currentWs.onopen = null;
        try {
          currentWs.close();
        } catch (e) {
          // Ignore errors
        }
        wsRef.current = null;
      }
    }

    return () => {
      isMounted = false;
      isChangingSymbolRef.current = true; // Prevent reconnections during cleanup
      
      if (connectTimeout) {
        clearTimeout(connectTimeout);
      }
      if (connectDelay) {
        clearTimeout(connectDelay);
      }
      
      const currentWs = wsRef.current;
      if (currentWs) {
        currentWs.onmessage = null;
        currentWs.onerror = null;
        currentWs.onclose = null;
        currentWs.onopen = null;
        try {
          currentWs.close();
        } catch (e) {
          // Ignore errors
        }
        wsRef.current = null;
      }
      
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };
  }, [mode, symbol, API_BASE, WS_BASE]);

  // Lazy-load more historical candles from Redis when user scrolls/pans backward in realtime mode
  useEffect(() => {
    loadMorePastRef.current = async () => {
      if (mode !== "realtime") return;

      const loadedRange = loadedRangeRef.current;
      if (!loadedRange) return;
      if (!hasMorePast || isLoadingMorePast) return;

      const now = Date.now();
      if (now - lastLoadMoreTimeRef.current < 1000) {
        // debounce: don't load more than once per second
        return;
      }
      lastLoadMoreTimeRef.current = now;

      setIsLoadingMorePast(true);
      try {
        const res = await axios.get<ApiResponse>(`${API_BASE}/ohlc/realtime`, {
          params: {
            symbol,
            limit: 200,
            start: loadedRange.min, // Load candles before this time (openTime < start)
          },
        });

        const candles = res.data?.candles || [];
        if (candles.length === 0) {
          setHasMorePast(false);
          return;
        }

        const newData: CandleData[] = candles.map((d) => ({
          x: d.openTime,
          y: d.y,
          volume: d.volume,
        }));

        // Preserve current viewport before updating data
        const chart = chartRef.current;
        const prevMinVisible =
          chart?.w?.globals?.minX !== undefined ? chart.w.globals.minX : null;
        const prevMaxVisible =
          chart?.w?.globals?.maxX !== undefined ? chart.w.globals.maxX : null;

        setSeries((prev) => {
          const existing = prev[0]?.data || [];
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

          return [{ data: result }];
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
            } catch (e) {
              // ignore chart update errors
            }
          }, 0);
        }
      } catch (err) {
        console.error("❌ Error loading more realtime data:", err);
      } finally {
        setIsLoadingMorePast(false);
      }
    };
  }, [API_BASE, mode, symbol, hasMorePast, isLoadingMorePast]);

  const options: ApexCharts.ApexOptions = useMemo(() => ({
    chart: {
      type: "candlestick",
      height: 650,
      background: "transparent",
      animations: { 
        enabled: mode === "realtime",
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
      events: {
        mounted: (chartContext: any) => {
          chartRef.current = chartContext;
        },
        updated: (chartContext: any) => {
          chartRef.current = chartContext;
        },
        zoomed: (chartContext: any, { xaxis }: any) => {
          if (xaxis && xaxis.min && xaxis.max) {
            zoomRangeRef.current = {
              min: xaxis.min,
              max: xaxis.max,
            };
          }
        },
        scrolled: (chartContext: any, { xaxis }: any) => {
          // Trigger lazy-load when user scrolls near the left edge of loaded data (realtime mode only)
          if (mode !== "realtime") return;
          
          if (xaxis && xaxis.min !== undefined && loadedRangeRef.current) {
            const loadedMin = loadedRangeRef.current.min;
            const visibleMin = xaxis.min;
            
            // If user scrolled to within 10% of the left edge, load more
            const threshold = (xaxis.max - xaxis.min) * 0.1;
            if (visibleMin <= loadedMin + threshold) {
              if (!hasMorePast || isLoadingMorePast) return;
              
              // Small delay to avoid too frequent calls
              setTimeout(() => {
                if (loadMorePastRef.current) {
                  loadMorePastRef.current();
                }
              }, 300);
            }
          }
        },
      },
      fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
    },
    plotOptions: {
      candlestick: {
        colors: {
          upward: '#0ecb81',
          downward: '#f6465d'
        },
        wick: {
          useFillColor: true
        },
        columnWidth: '80%',
      },
    },
    title: {
      text: "",
      align: "left",
    },
    grid: {
      borderColor: 'rgba(255, 255, 255, 0.08)',
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
          colors: '#848E9C',
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
        color: 'rgba(255, 255, 255, 0.08)',
      },
      axisTicks: {
        color: 'rgba(255, 255, 255, 0.08)',
      },
    },
    yaxis: {
      opposite: true,
      labels: {
        style: {
          colors: '#848E9C',
          fontSize: '12px',
          fontFamily: 'Inter, system-ui, sans-serif',
        },
        formatter: (value: number) => {
          return value.toLocaleString('en-US', {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          });
        },
      },
      tooltip: { enabled: true },
      forceNiceScale: true,
    },
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
      custom: function({seriesIndex, dataPointIndex, w}: any) {
        const data = w.globals.initialSeries[seriesIndex].data[dataPointIndex];
        const ohlc = data.y;
        const changePercent = ((ohlc[3] - ohlc[0]) / ohlc[0] * 100);
        const change = changePercent.toFixed(2);
        const changeColor = changePercent >= 0 ? '#0ecb81' : '#f6465d';
        
        return `
          <div style="padding: 12px; background: #181a20; border: 1px solid #2b3139; border-radius: 6px;">
            <div style="color: #eaecef; font-weight: 600; margin-bottom: 8px; font-size: 13px;">
              ${w.globals.categoryLabels[dataPointIndex]}
            </div>
            <div style="display: flex; flex-direction: column; gap: 6px;">
              <div style="display: flex; justify-content: space-between; gap: 20px;">
                <span style="color: #848e9c;">Open:</span>
                <span style="color: #eaecef; font-weight: 500;">${ohlc[0].toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 20px;">
                <span style="color: #848e9c;">High:</span>
                <span style="color: #eaecef; font-weight: 500;">${ohlc[1].toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 20px;">
                <span style="color: #848e9c;">Low:</span>
                <span style="color: #eaecef; font-weight: 500;">${ohlc[2].toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 20px;">
                <span style="color: #848e9c;">Close:</span>
                <span style="color: #eaecef; font-weight: 500;">${ohlc[3].toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
              </div>
              <div style="display: flex; justify-content: space-between; gap: 20px; margin-top: 4px; padding-top: 6px; border-top: 1px solid #2b3139;">
                <span style="color: #848e9c;">Change:</span>
                <span style="color: ${changeColor}; font-weight: 600;">${changePercent >= 0 ? '+' : ''}${change}%</span>
              </div>
            </div>
          </div>
        `;
      },
    },
    dataLabels: { enabled: false },
    legend: {
      show: false,
    },
  }), [mode, symbol]);

  const symbolOptions = symbols.map(s => ({
    value: s,
    label: s.replace('USDT', '/USDT')
  }));

  return (
    <Layout style={{ minHeight: "100vh", backgroundColor: "#000" }}>
      <Header
        style={{
          backgroundColor: "#181a20",
          borderBottom: "1px solid #2b3139",
          padding: "12px 32px",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            marginBottom: 12,
            paddingBottom: 12,
            borderBottom: "1px solid #2b3139",
          }}
        >
          <Link
            href="/"
            style={{
              color: "#0ecb81",
              fontWeight: 600,
              fontSize: 13,
              textDecoration: "none",
            }}
          >
            Candlestick Chart
          </Link>
          <Link
            href="/orderbook"
            style={{
              color: "#848E9C",
              fontSize: 13,
              textDecoration: "none",
            }}
          >
            Order Book & Trades
          </Link>
        </div>
        <div
          style={{
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
          }}
        >
          <Space size={40} align="baseline">
            <div>
              <Text
                style={{
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: 0.8,
                  color: "#848E9C",
                  fontWeight: 500,
                  display: "block",
                  marginBottom: 4,
                }}
              >
                Live Status
              </Text>
              <Badge
                status="success"
                text={
                  <span style={{ color: "#0ecb81", fontSize: 13, fontWeight: 600 }}>
                    Connected
                  </span>
                }
              />
            </div>
            <div>
              <Text
                style={{
                  fontSize: 11,
                  textTransform: "uppercase",
                  letterSpacing: 0.8,
                  color: "#848E9C",
                  fontWeight: 500,
                  display: "block",
                  marginBottom: 4,
                }}
              >
                Symbol
              </Text>
              <Select
                value={symbol}
                onChange={(value) => {
                  setSymbol(value);
                  setSeries([{ data: [] }]);
                  zoomRangeRef.current = null;
                }}
                options={
                  symbolOptions.length > 0
                    ? symbolOptions
                    : [{ value: "BTCUSDT", label: "BTC/USDT" }]
                }
                style={{ width: 160 }}
                size="middle"
                className="custom-select"
              />
            </div>
          </Space>

          <Space size={8}>
            <Button
              type={mode === "realtime" ? "primary" : "default"}
              onClick={() => setMode("realtime")}
              size="middle"
              style={{
                minWidth: 90,
                backgroundColor: "#1e2329",
                borderColor: mode === "realtime" ? "#0ecb81" : "#2b3139",
              }}
            >
              Realtime
            </Button>
            <Button
              type={mode === "7day" ? "primary" : "default"}
              onClick={() => setMode("7day")}
              size="middle"
              style={{
                minWidth: 70,
                backgroundColor: "#1e2329",
                borderColor: mode === "7day" ? "#0ecb81" : "#2b3139",
              }}
            >
              7 Day
            </Button>
            <Button
              type={mode === "30day" ? "primary" : "default"}
              onClick={() => setMode("30day")}
              size="middle"
              style={{
                minWidth: 70,
                backgroundColor: "#1e2329",
                borderColor: mode === "30day" ? "#0ecb81" : "#2b3139",
              }}
            >
              30 Day
            </Button>
            <Button
              type={mode === "6month" ? "primary" : "default"}
              onClick={() => setMode("6month")}
              size="middle"
              style={{
                minWidth: 80,
                backgroundColor: "#1e2329",
                borderColor: mode === "6month" ? "#0ecb81" : "#2b3139",
              }}
            >
              6 Month
            </Button>
            <Button
              type={mode === "1year" ? "primary" : "default"}
              onClick={() => setMode("1year")}
              size="middle"
              style={{
                minWidth: 70,
                backgroundColor: "#1e2329",
                borderColor: mode === "1year" ? "#0ecb81" : "#2b3139",
              }}
            >
              1 Year
            </Button>
          </Space>
        </div>
      </Header>

      <Content style={{ padding: 16, backgroundColor: "#000" }}>
        <div
          style={{
            backgroundColor: "#181a20",
            borderRadius: 8,
            border: "1px solid #2b3139",
            padding: 16,
          }}
        >
          {mode !== "realtime" && isLoading ? (
            <div
              style={{
                height: 650,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Badge status="processing" color="#0ecb81" />
            </div>
          ) : series[0]?.data?.length > 0 ? (
            <Chart
              key={`${mode}-${symbol}`}
              options={options}
              series={series}
              type="candlestick"
              height={650}
            />
          ) : (
            <div
              style={{
                height: 650,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#848E9C",
                textAlign: "center",
              }}
            >
              {mode === "realtime" ? (
                <div>
                  <div
                    style={{
                      marginBottom: 12,
                      fontSize: 24,
                      color: "#0ecb81",
                    }}
                  >
                    ●
                  </div>
                  <Text style={{ color: "#e5e7eb" }}>Waiting for real-time data...</Text>
                </div>
              ) : (
                <Text style={{ color: "#e5e7eb" }}>No data available</Text>
              )}
            </div>
          )}
        </div>
      </Content>
    </Layout>
  );
}
