"use client";

import { useEffect, useState, useRef, useMemo } from "react";
import dynamic from "next/dynamic";
import axios from "axios";
import { Spin, Typography } from "antd";

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

interface ChartEmbeddedProps {
  symbol: string;
  mode: "history" | "realtime";
}

export default function ChartEmbedded({ symbol, mode }: ChartEmbeddedProps) {
  const [series, setSeries] = useState<{ data: CandleData[] }[]>([{ data: [] }]);
  const [isLoading, setIsLoading] = useState(true);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<NodeJS.Timeout | null>(null);
  const chartRef = useRef<any>(null);
  const zoomRangeRef = useRef<{ min: number; max: number } | null>(null);
  const currentSymbolRef = useRef<string>(symbol);
  const isChangingSymbolRef = useRef<boolean>(false);
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const WS_BASE = API_BASE.replace(/^http/, "ws");

  useEffect(() => {
    let isMounted = true;
    let connectTimeout: NodeJS.Timeout | null = null;
    let connectDelay: NodeJS.Timeout | null = null;
    
    // Mark that we're changing symbol to prevent reconnections
    isChangingSymbolRef.current = true;
    
    // Close existing WebSocket FIRST before updating symbol
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
        const res = await axios.get<ApiResponse>(`${API_BASE}/ohlc`, {
          params: { symbol: symbol, interval: "5m", limit: 200 },
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
    }

    if (mode === "history") {
      fetchHistoricalData();
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
    } else {
      // Small delay to ensure cleanup is complete before connecting
      connectTimeout = setTimeout(() => {
        if (isMounted && !isChangingSymbolRef.current) {
          connectWebSocket();
        }
      }, 150);
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
      if (reconnectTimer.current) {
        clearTimeout(reconnectTimer.current);
        reconnectTimer.current = null;
      }
    };
  }, [mode, symbol, API_BASE, WS_BASE]);

  const options: ApexCharts.ApexOptions = useMemo(() => ({
    chart: {
      type: "candlestick",
      height: "100%",
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
      scrollbar: {
        enabled: true,
        offsetY: 0,
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
      },
      fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
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
    yaxis: {
      position: "right",
      labels: {
        style: {
          colors: '#9ca3af',
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
    },
    dataLabels: { enabled: false },
    legend: {
      show: false,
    },
  }), [mode]);

  if (isLoading && mode === "history") {
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

  if (series[0]?.data?.length === 0) {
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


