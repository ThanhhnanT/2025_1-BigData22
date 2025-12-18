"use client";

import { useEffect, useState, useRef } from "react";
import axios from "axios";
import { Select, Row, Col, Table, Button, Space, Typography, Badge } from "antd";
import type { ColumnsType } from "antd/es/table";
import ChartEmbedded from "./ChartEmbedded";
import "./TradingDashboard.css";

const { Title, Text } = Typography;

interface OrderBookEntry {
  price: number;
  quantity: number;
  total: number;
}

interface Trade {
  symbol: string;
  price: number;
  quantity: number;
  time: number;
  isBuyerMaker: boolean;
  tradeId?: number;
}

interface OrderBookMessage {
  type: "initial" | "update";
  symbol: string;
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  timestamp?: number;
}

interface TradesMessage {
  type: "initial" | "realtime";
  symbol: string;
  trades?: Trade[];
  trade?: Trade;
}

export default function TradingDashboard() {
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [symbols, setSymbols] = useState<string[]>([]);
  const [bids, setBids] = useState<OrderBookEntry[]>([]);
  const [asks, setAsks] = useState<OrderBookEntry[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);
  const [granularity, setGranularity] = useState<string>("0.1");
  const [mode, setMode] = useState<"realtime" | "7day" | "30day" | "6month" | "1year">("realtime");
  
  const wsOrderBookRef = useRef<WebSocket | null>(null);
  const wsTradesRef = useRef<WebSocket | null>(null);
  const reconnectTimerOB = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimerTrades = useRef<NodeJS.Timeout | null>(null);
  const currentSymbolRef = useRef<string>(symbol);
  const isChangingSymbolRef = useRef<boolean>(false);
  
  const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
  const WS_BASE = API_BASE.replace(/^http/, "ws");

  useEffect(() => {
    async function fetchSymbols() {
      try {
        const res = await axios.get<{ symbols: string[] }>(`${API_BASE}/symbols`);
        setSymbols(res.data.symbols || []);
      } catch (err) {
        console.error("Error fetching symbols:", err);
        setSymbols(["BTCUSDT", "ETHUSDT", "BNBUSDT"]);
      }
    }
    fetchSymbols();
  }, [API_BASE]);

  useEffect(() => {
    let isMounted = true;
    let connectTimeoutOB: NodeJS.Timeout | null = null;
    let connectTimeoutTrades: NodeJS.Timeout | null = null;
    let connectDelay: NodeJS.Timeout | null = null;
    
    // Mark that we're changing symbol to prevent reconnections
    isChangingSymbolRef.current = true;
    
    // Close existing WebSockets FIRST before updating symbol
    // This prevents old WebSocket from sending messages after symbol change
    if (wsOrderBookRef.current) {
      wsOrderBookRef.current.onmessage = null;
      wsOrderBookRef.current.onerror = null;
      wsOrderBookRef.current.onclose = null;
      wsOrderBookRef.current.onopen = null;
      try {
        wsOrderBookRef.current.close();
      } catch (e) {
        // Ignore errors
      }
      wsOrderBookRef.current = null;
    }
    if (wsTradesRef.current) {
      wsTradesRef.current.onmessage = null;
      wsTradesRef.current.onerror = null;
      wsTradesRef.current.onclose = null;
      wsTradesRef.current.onopen = null;
      try {
        wsTradesRef.current.close();
      } catch (e) {
        // Ignore errors
      }
      wsTradesRef.current = null;
    }
    if (reconnectTimerOB.current) {
      clearTimeout(reconnectTimerOB.current);
      reconnectTimerOB.current = null;
    }
    if (reconnectTimerTrades.current) {
      clearTimeout(reconnectTimerTrades.current);
      reconnectTimerTrades.current = null;
    }
    
    // Update current symbol ref AFTER closing old connections
    currentSymbolRef.current = symbol;
    
    // Small delay to ensure old connections are fully closed
    connectDelay = setTimeout(() => {
      isChangingSymbolRef.current = false;
    }, 100);
    
    // Reset state when symbol changes
    setBids([]);
    setAsks([]);
    setTrades([]);
    setCurrentPrice(0);
    setPriceChange(0);
    
    // Fetch initial snapshot
    async function fetchInitialData() {
      try {
        // Fetch Order Book
        const obRes = await axios.get(`${API_BASE}/orderbook`, {
          params: { symbol, limit: 20 },
        });
        if (obRes.data) {
          setBids(obRes.data.bids || []);
          setAsks(obRes.data.asks || []);
          if (obRes.data.bids.length > 0 && obRes.data.asks.length > 0) {
            const midPrice = (obRes.data.bids[0].price + obRes.data.asks[0].price) / 2;
            setCurrentPrice(midPrice);
          }
        }

        // Fetch Trades
        const tradesRes = await axios.get(`${API_BASE}/trades`, {
          params: { symbol, limit: 50 },
        });
        if (tradesRes.data && tradesRes.data.trades) {
          setTrades(tradesRes.data.trades.reverse());
          if (tradesRes.data.trades.length > 0) {
            const latestTrade = tradesRes.data.trades[tradesRes.data.trades.length - 1];
            setCurrentPrice(latestTrade.price);
          }
        }
      } catch (err) {
        console.error("Error fetching initial data:", err);
      }
    }

    fetchInitialData();

    // Connect Order Book WebSocket
    function connectOrderBookWS() {
      // Don't connect if we're changing symbol
      if (isChangingSymbolRef.current) {
        return;
      }
      
      const targetSymbol = currentSymbolRef.current;
      
      // Don't create new connection if one already exists and is open
      if (wsOrderBookRef.current && wsOrderBookRef.current.readyState === WebSocket.OPEN) {
        return;
      }
      
      if (wsOrderBookRef.current) {
        wsOrderBookRef.current.onmessage = null;
        wsOrderBookRef.current.onerror = null;
        wsOrderBookRef.current.onclose = null;
        wsOrderBookRef.current.onopen = null;
        try {
          wsOrderBookRef.current.close();
        } catch (e) {
          // Ignore errors
        }
        wsOrderBookRef.current = null;
      }
      
      // Clear any existing reconnect timer
      if (reconnectTimerOB.current) {
        clearTimeout(reconnectTimerOB.current);
        reconnectTimerOB.current = null;
      }

      // Check again before creating WebSocket
      if (currentSymbolRef.current !== targetSymbol || isChangingSymbolRef.current) {
        return;
      }

      const wsUrl = `${WS_BASE}/ws/orderbook?symbol=${targetSymbol}`;
      const ws = new WebSocket(wsUrl);
      wsOrderBookRef.current = ws;

      ws.onopen = () => {
        // Connection successful
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data: OrderBookMessage = JSON.parse(event.data);
          const currentSymbol = currentSymbolRef.current;
          
          // Only process if symbol matches current symbol (use ref to get latest value)
          if (data.symbol && data.symbol !== currentSymbol) {
            return;
          }
          
          if (data.type === "initial" || data.type === "update") {
            setBids(data.bids || []);
            setAsks(data.asks || []);
            
            if (data.bids.length > 0 && data.asks.length > 0) {
              const midPrice = (data.bids[0].price + data.asks[0].price) / 2;
              setCurrentPrice(midPrice);
            }
          }
        } catch (err) {
          console.error("Error parsing Order Book message:", err);
        }
      };

      ws.onclose = (event) => {
        // Clear the ref if this was the current connection
        if (wsOrderBookRef.current === ws) {
          wsOrderBookRef.current = null;
        }
        
        if (!isMounted || isChangingSymbolRef.current) {
          return;
        }
        
        const currentSymbol = currentSymbolRef.current;
        const expectedSymbol = targetSymbol; // Capture at connection time
        
        // Only reconnect if symbol hasn't changed and we're not changing symbols
        if (currentSymbol === expectedSymbol && !isChangingSymbolRef.current) {
          reconnectTimerOB.current = setTimeout(() => {
            if (currentSymbolRef.current === expectedSymbol && isMounted && !isChangingSymbolRef.current) {
              connectOrderBookWS();
            }
          }, 2000);
        }
      };

      ws.onerror = (err) => {
        console.error("Order Book WebSocket error:", err);
      };
    }

    // Connect Trades WebSocket
    function connectTradesWS() {
      // Don't connect if we're changing symbol
      if (isChangingSymbolRef.current) {
        return;
      }
      
      const targetSymbol = currentSymbolRef.current;
      
      // Don't create new connection if one already exists and is open
      if (wsTradesRef.current && wsTradesRef.current.readyState === WebSocket.OPEN) {
        return;
      }
      
      if (wsTradesRef.current) {
        wsTradesRef.current.onmessage = null;
        wsTradesRef.current.onerror = null;
        wsTradesRef.current.onclose = null;
        wsTradesRef.current.onopen = null;
        try {
          wsTradesRef.current.close();
        } catch (e) {
          // Ignore errors
        }
        wsTradesRef.current = null;
      }
      
      // Clear any existing reconnect timer
      if (reconnectTimerTrades.current) {
        clearTimeout(reconnectTimerTrades.current);
        reconnectTimerTrades.current = null;
      }

      // Check again before creating WebSocket
      if (currentSymbolRef.current !== targetSymbol || isChangingSymbolRef.current) {
        return;
      }

      const wsUrl = `${WS_BASE}/ws/trades?symbol=${targetSymbol}&limit=50`;
      const ws = new WebSocket(wsUrl);
      wsTradesRef.current = ws;

      ws.onopen = () => {
        // Connection successful
      };

      ws.onmessage = (event) => {
        if (!isMounted) return;
        try {
          const data: TradesMessage = JSON.parse(event.data);
          const currentSymbol = currentSymbolRef.current;
          
          // Only process if symbol matches current symbol (use ref to get latest value)
          if (data.symbol && data.symbol !== currentSymbol) {
            return;
          }
          
          if (data.type === "initial" && data.trades) {
            setTrades(data.trades.reverse());
            if (data.trades.length > 0) {
              const latestTrade = data.trades[data.trades.length - 1];
              setCurrentPrice(latestTrade.price);
            }
          } else if (data.type === "realtime" && data.trade) {
            // Also check trade symbol
            if (data.trade.symbol && data.trade.symbol !== currentSymbol) {
              return;
            }
            setTrades((prev) => {
              const updated = [data.trade!, ...prev];
              return updated.slice(0, 50);
            });
            if (data.trade) {
              const newPrice = data.trade.price;
              if (currentPrice > 0) {
                const change = ((newPrice - currentPrice) / currentPrice) * 100;
                setPriceChange(change);
              }
              setCurrentPrice(newPrice);
            }
          }
        } catch (err) {
          console.error("Error parsing Trades message:", err);
        }
      };

      ws.onclose = (event) => {
        // Clear the ref if this was the current connection
        if (wsTradesRef.current === ws) {
          wsTradesRef.current = null;
        }
        
        if (!isMounted || isChangingSymbolRef.current) {
          return;
        }
        
        const currentSymbol = currentSymbolRef.current;
        const expectedSymbol = targetSymbol; // Capture at connection time
        
        // Only reconnect if symbol hasn't changed and we're not changing symbols
        if (currentSymbol === expectedSymbol && !isChangingSymbolRef.current) {
          reconnectTimerTrades.current = setTimeout(() => {
            if (currentSymbolRef.current === expectedSymbol && isMounted && !isChangingSymbolRef.current) {
              connectTradesWS();
            }
          }, 2000);
        }
      };

      ws.onerror = (err) => {
        console.error("Trades WebSocket error:", err);
      };
    }

    // Small delay to ensure cleanup is complete before connecting
    connectTimeoutOB = setTimeout(() => {
      if (isMounted && !isChangingSymbolRef.current) {
        connectOrderBookWS();
      }
    }, 150);
    
    connectTimeoutTrades = setTimeout(() => {
      if (isMounted && !isChangingSymbolRef.current) {
        connectTradesWS();
      }
    }, 150);

    return () => {
      isMounted = false;
      isChangingSymbolRef.current = true; // Prevent reconnections during cleanup
      
      if (connectTimeoutOB) {
        clearTimeout(connectTimeoutOB);
      }
      if (connectTimeoutTrades) {
        clearTimeout(connectTimeoutTrades);
      }
      if (connectDelay) {
        clearTimeout(connectDelay);
      }
      
      if (wsOrderBookRef.current) {
        wsOrderBookRef.current.onmessage = null;
        wsOrderBookRef.current.onerror = null;
        wsOrderBookRef.current.onclose = null;
        wsOrderBookRef.current.onopen = null;
        try {
          wsOrderBookRef.current.close();
        } catch (e) {
          // Ignore errors
        }
        wsOrderBookRef.current = null;
      }
      if (wsTradesRef.current) {
        wsTradesRef.current.onmessage = null;
        wsTradesRef.current.onerror = null;
        wsTradesRef.current.onclose = null;
        wsTradesRef.current.onopen = null;
        try {
          wsTradesRef.current.close();
        } catch (e) {
          // Ignore errors
        }
        wsTradesRef.current = null;
      }
      if (reconnectTimerOB.current) {
        clearTimeout(reconnectTimerOB.current);
        reconnectTimerOB.current = null;
      }
      if (reconnectTimerTrades.current) {
        clearTimeout(reconnectTimerTrades.current);
        reconnectTimerTrades.current = null;
      }
    };
  }, [symbol, API_BASE, WS_BASE]);

  // Format price with granularity
  const formatPrice = (price: number): string => {
    const decimals = granularity === "0.01" ? 2 : 1;
    return price.toFixed(decimals);
  };

  // Format time
  const formatTime = (timestamp: number): string => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString("en-US", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  // Calculate max total for visual bars
  const maxBidTotal = bids.length > 0 ? Math.max(...bids.map((b) => b.total)) : 0;
  const maxAskTotal = asks.length > 0 ? Math.max(...asks.map((a) => a.total)) : 0;
  const maxTotal = Math.max(maxBidTotal, maxAskTotal);

  const symbolOptions = symbols.map((s) => ({
    value: s,
    label: s.replace("USDT", "/USDT"),
  }));

  // Order Book Table Columns
  const orderBookColumns: ColumnsType<OrderBookEntry & { key: string; type: 'ask' | 'bid' }> = [
    {
      title: 'Price(USDT)',
      dataIndex: 'price',
      key: 'price',
      align: 'left',
      render: (price: number, record) => (
        <span style={{ color: record.type === 'ask' ? '#ef4444' : '#10b981' }}>
          {formatPrice(price)}
        </span>
      ),
    },
    {
      title: 'Amount(BTC)',
      dataIndex: 'quantity',
      key: 'quantity',
      align: 'right',
      render: (quantity: number) => (
        <span style={{ color: '#fff' }}>{quantity.toFixed(4)}</span>
      ),
    },
    {
      title: 'Total',
      dataIndex: 'total',
      key: 'total',
      align: 'right',
      render: (total: number) => (
        <span style={{ color: '#fff' }}>{(total / 1000).toFixed(1)}K</span>
      ),
    },
  ];

  // Market Trades Table Columns
  const tradesColumns: ColumnsType<Trade> = [
    {
      title: 'Price(USDT)',
      dataIndex: 'price',
      key: 'price',
      align: 'left',
      render: (price: number, record) => (
        <span style={{ color: record.isBuyerMaker ? '#ef4444' : '#10b981' }}>
          {formatPrice(price)}
        </span>
      ),
    },
    {
      title: 'Amount(BTC)',
      dataIndex: 'quantity',
      key: 'quantity',
      align: 'right',
      render: (quantity: number) => (
        <span style={{ color: '#fff' }}>{quantity.toFixed(4)}</span>
      ),
    },
    {
      title: 'Time',
      dataIndex: 'time',
      key: 'time',
      align: 'right',
      render: (time: number) => (
        <span style={{ color: '#fff' }}>{formatTime(time)}</span>
      ),
    },
  ];

  // Prepare Order Book data for Table
  const asksData = asks.slice(0, 6).reverse().map((ask, idx) => ({
    ...ask,
    key: `ask-${idx}`,
    type: 'ask' as const,
  }));

  const bidsData = bids.slice(0, 6).map((bid, idx) => ({
    ...bid,
    key: `bid-${idx}`,
    type: 'bid' as const,
  }));

  // Prepare Trades data for Table (limit to 5-6 rows)
  const tradesData = trades.slice(0, 6).map((trade, idx) => ({
    ...trade,
    key: `trade-${trade.tradeId || idx}`,
  }));

  return (
    <div style={{ minHeight: '100vh', backgroundColor: '#111827', color: '#fff' }}>
      {/* Header */}
      <header style={{
        backgroundColor: '#1f2937',
        borderBottom: '1px solid #374151',
        padding: '16px 24px',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div style={{
            height: '12px',
            width: '12px',
            borderRadius: '50%',
            backgroundColor: '#3b82f6',
            animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
          }}></div>
          <Title level={4} style={{ margin: 0, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ color: '#3b82f6' }}>📊</span>
            Crypto Dashboard
          </Title>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '14px', color: '#fff' }}>
            <span style={{
              display: 'flex',
              height: '8px',
              width: '8px',
              borderRadius: '50%',
              backgroundColor: '#10b981',
            }}></span>
            <span>System Operational</span>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main style={{
        padding: '16px 24px 32px',
        maxWidth: '1536px',
        margin: '0 auto',
      }}>
        {/* Control Section */}
        <section style={{
          backgroundColor: '#1f2937',
          padding: '16px',
          borderRadius: '8px',
          border: '1px solid #374151',
          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
          marginBottom: '24px',
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', flexWrap: 'wrap' }}>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <label style={{ fontSize: '12px', fontWeight: 500, color: '#fff', marginBottom: '4px' }}>
                  Live Status
                </label>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '14px', fontWeight: 600, color: '#10b981' }}>
                  <span style={{ position: 'relative', display: 'flex', height: '8px', width: '8px' }}>
                    <span style={{
                      position: 'absolute',
                      animation: 'ping 1s cubic-bezier(0, 0, 0.2, 1) infinite',
                      height: '100%',
                      width: '100%',
                      borderRadius: '50%',
                      backgroundColor: '#10b981',
                      opacity: 0.75,
                    }}></span>
                    <span style={{
                      position: 'relative',
                      display: 'inline-flex',
                      borderRadius: '50%',
                      height: '8px',
                      width: '8px',
                      backgroundColor: '#10b981',
                    }}></span>
                  </span>
                  Connected
                </div>
              </div>
              <div style={{ height: '32px', width: '1px', backgroundColor: '#374151', display: 'none' }}></div>
              <div style={{ display: 'flex', flexDirection: 'column' }}>
                <label style={{ fontSize: '12px', fontWeight: 500, color: '#fff', marginBottom: '4px' }}>
                  Symbol
                </label>
                <Select
                  value={symbol}
                  onChange={(value) => {
                    setSymbol(value);
                    setBids([]);
                    setAsks([]);
                    setTrades([]);
                  }}
                  options={symbolOptions.length > 0 ? symbolOptions : [{ value: "BTCUSDT", label: "BTC/USDT" }]}
                  style={{ width: 160 }}
                  size="middle"
                  className="custom-select"
                />
              </div>
            </div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: '#1f2937',
              padding: '4px',
              borderRadius: '6px',
              gap: '4px',
            }}>
              <Button
                type={mode === "realtime" ? "primary" : "default"}
                onClick={() => setMode("realtime")}
                size="small"
                style={{
                  backgroundColor: mode === "realtime" ? '#374151' : 'transparent',
                  color: '#fff',
                  border: 'none',
                }}
              >
                Realtime
              </Button>
              <Button
                type={mode === "7day" ? "primary" : "default"}
                onClick={() => setMode("7day")}
                size="small"
                style={{
                  backgroundColor: mode === "7day" ? '#374151' : 'transparent',
                  color: '#fff',
                  border: 'none',
                }}
              >
                7 Day
              </Button>
              <Button
                type={mode === "30day" ? "primary" : "default"}
                onClick={() => setMode("30day")}
                size="small"
                style={{
                  backgroundColor: mode === "30day" ? '#374151' : 'transparent',
                  color: '#fff',
                  border: 'none',
                }}
              >
                30 Day
              </Button>
              <Button
                type={mode === "6month" ? "primary" : "default"}
                onClick={() => setMode("6month")}
                size="small"
                style={{
                  backgroundColor: mode === "6month" ? '#374151' : 'transparent',
                  color: '#fff',
                  border: 'none',
                }}
              >
                6 Month
              </Button>
              <Button
                type={mode === "1year" ? "primary" : "default"}
                onClick={() => setMode("1year")}
                size="small"
                style={{
                  backgroundColor: mode === "1year" ? '#374151' : 'transparent',
                  color: '#fff',
                  border: 'none',
                }}
              >
                1 Year
              </Button>
            </div>
          </div>
        </section>

        {/* Main Layout using Row/Col */}
        <Row gutter={[24, 24]} style={{ height: 'calc(100vh - 250px)', minHeight: '600px' }}>
          {/* Chart Section - Left (18 columns = 75%) */}
          <Col xs={24} lg={18} style={{ height: '100%', display: 'flex' }}>
            <section style={{
              backgroundColor: '#1f2937',
              borderRadius: '8px',
              border: '1px solid #374151',
              boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
              overflow: 'hidden',
              display: 'flex',
              flexDirection: 'column',
              width: '100%',
              height: '100%',
            }}>
              <div style={{
                padding: '12px 16px',
                borderBottom: '1px solid #374151',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                backgroundColor: 'rgba(31, 41, 55, 0.5)',
                flexShrink: 0,
              }}>
                <Title level={5} style={{ margin: 0, color: '#fff', display: 'flex', alignItems: 'center', gap: '8px' }}>
                  {symbol.replace("USDT", "/USDT")}{" "}
                  <Text style={{ color: '#fff', fontSize: '14px', fontWeight: 'normal' }}>
                    - {mode === "realtime"
                      ? "Real-Time (1m)"
                      : mode === "7day"
                      ? "7 Day (5m)"
                      : mode === "30day"
                      ? "30 Day (1h)"
                      : mode === "6month"
                      ? "6 Month (4h)"
                      : "1 Year (1d)"}
                  </Text>
                </Title>
              </div>
              <div style={{
                padding: '16px',
                backgroundColor: '#131722',
                position: 'relative',
                flex: 1,
                overflowX: 'auto',
                minHeight: 0,
              }}>
                <div style={{ width: '100%', height: '100%', minWidth: '800px' }}>
                  <ChartEmbedded symbol={symbol} mode={mode} />
                </div>
              </div>
            </section>
          </Col>

          {/* Order Book & Trades - Right (6 columns = 25%) */}
          <Col xs={24} lg={6} style={{ display: 'flex' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '100%', height: '100%' }}>
              {/* Order Book */}
              <section style={{
                backgroundColor: '#1f2937',
                borderRadius: '8px',
                border: '1px solid #374151',
                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                height: '400px',
                flex: 1,
                minHeight: 0,
              }}>
                <div style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #374151',
                  backgroundColor: 'rgba(31, 41, 55, 0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexShrink: 0,
                }}>
                  <Title level={5} style={{ margin: 0, color: '#fff', fontSize: '14px' }}>Order Book</Title>
                  <Space size={4} style={{ fontSize: '12px', backgroundColor: '#374151', padding: '2px', borderRadius: '4px' }}>
                    <Button
                      type={granularity === "0.1" ? "primary" : "text"}
                      onClick={() => setGranularity("0.1")}
                      size="small"
                      style={{
                        backgroundColor: granularity === "0.1" ? '#4b5563' : 'transparent',
                        color: '#fff',
                        border: 'none',
                        padding: '2px 8px',
                        fontSize: '12px',
                        height: 'auto',
                      }}
                    >
                      0.1
                    </Button>
                    <Button
                      type={granularity === "0.01" ? "primary" : "text"}
                      onClick={() => setGranularity("0.01")}
                      size="small"
                      style={{
                        backgroundColor: granularity === "0.01" ? '#4b5563' : 'transparent',
                        color: '#fff',
                        border: 'none',
                        padding: '2px 8px',
                        fontSize: '12px',
                        height: 'auto',
                      }}
                    >
                      0.01
                    </Button>
                  </Space>
                </div>

                {/* Order Book Table */}
                <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
                  {/* Asks Section */}
                  <div style={{ flex: 1, overflowY: 'auto' }}>
                    {asksData.length > 0 ? (
                      <Table
                        columns={orderBookColumns}
                        dataSource={asksData}
                        pagination={false}
                        size="small"
                        className="order-book-table"
                        rowClassName={(record) => {
                          const widthPercent = maxTotal > 0 ? (record.total / maxTotal) * 100 : 0;
                          return `relative order-book-row-ask`;
                        }}
                        onRow={(record) => {
                          const widthPercent = maxTotal > 0 ? (record.total / maxTotal) * 100 : 0;
                          return {
                            style: {
                              '--depth-width': `${widthPercent}%`,
                            } as React.CSSProperties,
                          };
                        }}
                        locale={{
                          emptyText: '',
                        }}
                      />
                    ) : (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100%',
                        color: '#fff',
                        fontSize: '14px',
                      }}>
                        No data
                      </div>
                    )}
                  </div>

                  {/* Current Price - Sticky */}
                  <div style={{
                    position: 'sticky',
                    top: 0,
                    bottom: 0,
                    zIndex: 20,
                    padding: '12px 0',
                    margin: '4px 0',
                    borderTop: '1px solid #374151',
                    borderBottom: '1px solid #374151',
                    backgroundColor: 'rgba(31, 41, 55, 0.9)',
                    backdropFilter: 'blur(4px)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    gap: '12px',
                    flexShrink: 0,
                  }}>
                    <span style={{ fontSize: '20px', fontWeight: 'bold', color: '#10b981' }}>
                      {currentPrice > 0 ? formatPrice(currentPrice) : "—"}
                    </span>
                    {priceChange !== 0 && (
                      <span style={{
                        fontSize: '14px',
                        color: priceChange >= 0 ? '#10b981' : '#ef4444',
                      }}>
                        {priceChange >= 0 ? "↑" : "↓"} {Math.abs(priceChange).toFixed(2)}%
                      </span>
                    )}
                    <span style={{ fontSize: '12px', color: '#fff' }}>
                      ≈ ${currentPrice > 0 ? formatPrice(currentPrice) : "—"}
                    </span>
                  </div>

                  {/* Bids Section */}
                  <div style={{ flex: 1, overflowY: 'auto' }}>
                    {bidsData.length > 0 ? (
                      <Table
                        columns={orderBookColumns}
                        dataSource={bidsData}
                        pagination={false}
                        size="small"
                        className="order-book-table"
                        rowClassName={(record) => {
                          const widthPercent = maxTotal > 0 ? (record.total / maxTotal) * 100 : 0;
                          return `relative order-book-row-bid`;
                        }}
                        onRow={(record) => {
                          const widthPercent = maxTotal > 0 ? (record.total / maxTotal) * 100 : 0;
                          return {
                            style: {
                              '--depth-width': `${widthPercent}%`,
                            } as React.CSSProperties,
                          };
                        }}
                        locale={{
                          emptyText: '',
                        }}
                      />
                    ) : (
                      <div style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        height: '100%',
                        color: '#fff',
                        fontSize: '14px',
                      }}>
                        No data
                      </div>
                    )}
                  </div>
                </div>
              </section>

              {/* Market Trades */}
              <section style={{
                backgroundColor: '#1f2937',
                borderRadius: '8px',
                border: '1px solid #374151',
                boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
                overflow: 'hidden',
                display: 'flex',
                flexDirection: 'column',
                flex: 1,
                minHeight: 0,
              }}>
                <div style={{
                  padding: '12px 16px',
                  borderBottom: '1px solid #374151',
                  backgroundColor: 'rgba(31, 41, 55, 0.5)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  flexShrink: 0,
                }}>
                  <Title level={5} style={{ margin: 0, color: '#fff', fontSize: '14px' }}>Market Trades</Title>
                </div>

                {/* Trades Table */}
                <div style={{ flex: 1, overflowY: 'auto' }}>
                  <Table
                    columns={tradesColumns}
                    dataSource={tradesData}
                    pagination={false}
                    size="small"
                    className="trades-table"
                    rowClassName="trades-table-row"
                  />
                </div>
              </section>
            </div>
          </Col>
        </Row>

        {/* Footer */}
        <footer style={{
          fontSize: '12px',
          color: '#fff',
          paddingTop: '8px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}>
          <p style={{ margin: 0, color: '#fff' }}>Real-time cryptocurrency data powered by Kafka & Redis</p>
          <p style={{ margin: 0, color: '#fff' }}>
            Last updated: <span style={{ color: '#fff' }}>{new Date().toLocaleTimeString()}</span>
          </p>
        </footer>
      </main>
    </div>
  );
}
