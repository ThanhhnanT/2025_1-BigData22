"use client";

import { useEffect, useState, useRef } from "react";
import axios from "axios";
import { Layout, Select, Badge, Typography, Row, Col, Space, Card } from "antd";
import Link from "next/link";

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

const { Header, Content } = Layout;
const { Text } = Typography;

export default function OrderBookTrades() {
  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [symbols, setSymbols] = useState<string[]>([]);
  const [bids, setBids] = useState<OrderBookEntry[]>([]);
  const [asks, setAsks] = useState<OrderBookEntry[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);
  const [granularity, setGranularity] = useState<string>("0.1");
  
  const wsOrderBookRef = useRef<WebSocket | null>(null);
  const wsTradesRef = useRef<WebSocket | null>(null);
  const reconnectTimerOB = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimerTrades = useRef<NodeJS.Timeout | null>(null);
  const currentSymbolRef = useRef<string>(symbol);
  const isChangingSymbolRef = useRef<boolean>(false);
  
  // Priority: browser detection > env variables > localhost
  const API_BASE = 
    (typeof window !== "undefined" ? "http://crypto.local/api" : null) ||
    process.env.NEXT_PUBLIC_API_BASE ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";
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
          // Calculate current price (mid price)
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
          setTrades(tradesRes.data.trades.reverse()); // Show newest first
          // Update current price from latest trade
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
            
            // Update current price
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
            // Update current price
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
              // Keep only last 50 trades
              return updated.slice(0, 50);
            });
            // Update current price and calculate change
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

  return (
    <Layout style={{ minHeight: "100vh", backgroundColor: "#000", padding: 16 }}>
      <Header
        style={{
          backgroundColor: "#181a20",
          borderBottom: "1px solid #2b3139",
          padding: "12px 32px",
          marginBottom: 16,
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
              color: "#848E9C",
              fontSize: 13,
              textDecoration: "none",
            }}
          >
            Candlestick Chart
          </Link>
          <Link
            href="/orderbook"
            style={{
              color: "#0ecb81",
              fontWeight: 600,
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
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Space size={40}>
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
                  setBids([]);
                  setAsks([]);
                  setTrades([]);
                }}
                options={
                  symbolOptions.length > 0
                    ? symbolOptions
                    : [{ value: "BTCUSDT", label: "BTC/USDT" }]
                }
                style={{ width: 160 }}
                size="middle"
              />
            </div>
          </Space>
        </div>
      </Header>

      <Content>
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <Card
              style={{
                backgroundColor: "#181a20",
                borderColor: "#2b3139",
                color: "#fff",
              }}
              bodyStyle={{ padding: 16 }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  marginBottom: 16,
                }}
              >
                <Typography.Title
                  level={4}
                  style={{ margin: 0, color: "#fff", fontSize: 18 }}
                >
                  Order Book
                </Typography.Title>
                <Space>
                  <button
                    onClick={() => setGranularity("0.1")}
                    style={{
                      padding: "4px 12px",
                      borderRadius: 4,
                      fontSize: 13,
                      border: "1px solid",
                      borderColor:
                        granularity === "0.1" ? "#0ecb81" : "#2b3139",
                      backgroundColor:
                        granularity === "0.1" ? "#2b3139" : "#1e2329",
                      color:
                        granularity === "0.1" ? "#fff" : "#848E9C",
                      cursor: "pointer",
                    }}
                  >
                    0.1
                  </button>
                  <button
                    onClick={() => setGranularity("0.01")}
                    style={{
                      padding: "4px 12px",
                      borderRadius: 4,
                      fontSize: 13,
                      border: "1px solid",
                      borderColor:
                        granularity === "0.01" ? "#0ecb81" : "#2b3139",
                      backgroundColor:
                        granularity === "0.01" ? "#2b3139" : "#1e2329",
                      color:
                        granularity === "0.01" ? "#fff" : "#848E9C",
                      cursor: "pointer",
                    }}
                  >
                    0.01
                  </button>
                </Space>
              </div>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 8,
                  color: "#848E9C",
                  fontSize: 12,
                  fontWeight: 500,
                  paddingBottom: 8,
                  marginBottom: 8,
                  borderBottom: "1px solid #2b3139",
                }}
              >
                <div>Price(USDT)</div>
                <div>Amount(BTC)</div>
                <div>Total</div>
              </div>

              <div style={{ marginBottom: 16 }}>
                {asks.slice(0, 6).map((ask, idx) => {
                  const widthPercent =
                    maxTotal > 0 ? (ask.total / maxTotal) * 100 : 0;
                  return (
                    <div
                      key={`ask-${idx}`}
                      style={{
                        position: "relative",
                        display: "grid",
                        gridTemplateColumns: "repeat(3, 1fr)",
                        gap: 8,
                        fontSize: 14,
                        padding: "4px 0",
                        borderRadius: 4,
                        overflow: "hidden",
                      }}
                    >
                      <div style={{ position: "relative", zIndex: 1 }}>
                        <span
                          style={{
                            color: "#f6465d",
                            fontWeight: 500,
                          }}
                        >
                          {formatPrice(ask.price)}
                        </span>
                      </div>
                      <div style={{ position: "relative", zIndex: 1 }}>
                        {ask.quantity.toFixed(4)}
                      </div>
                      <div
                        style={{
                          position: "relative",
                          zIndex: 1,
                          color: "#848E9C",
                        }}
                      >
                        {(ask.total / 1000).toFixed(1)}K
                      </div>
                      <div
                        style={{
                          position: "absolute",
                          left: 0,
                          top: 0,
                          height: "100%",
                          width: `${widthPercent}%`,
                          backgroundColor: "#f6465d",
                          opacity: 0.1,
                        }}
                      />
                    </div>
                  );
                })}
              </div>

              <div
                style={{
                  padding: "16px 0",
                  borderTop: "1px solid #2b3139",
                  borderBottom: "1px solid #2b3139",
                  margin: "16px 0",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    gap: 8,
                  }}
                >
                  <span
                    style={{
                      fontSize: 24,
                      fontWeight: "bold",
                      color: "#0ecb81",
                    }}
                  >
                    {currentPrice > 0 ? formatPrice(currentPrice) : "—"}
                  </span>
                  {priceChange !== 0 && (
                    <span
                      style={{
                        fontSize: 14,
                        color: priceChange >= 0 ? "#0ecb81" : "#f6465d",
                      }}
                    >
                      {priceChange >= 0 ? "↑" : "↓"}{" "}
                      {Math.abs(priceChange).toFixed(2)}%
                    </span>
                  )}
                  <span
                    style={{
                      fontSize: 14,
                      color: "#848E9C",
                    }}
                  >
                    ≈ ${currentPrice > 0 ? formatPrice(currentPrice) : "—"}
                  </span>
                </div>
              </div>

              <div>
                {bids.slice(0, 6).map((bid, idx) => {
                  const widthPercent =
                    maxTotal > 0 ? (bid.total / maxTotal) * 100 : 0;
                  return (
                    <div
                      key={`bid-${idx}`}
                      style={{
                        position: "relative",
                        display: "grid",
                        gridTemplateColumns: "repeat(3, 1fr)",
                        gap: 8,
                        fontSize: 14,
                        padding: "4px 0",
                        borderRadius: 4,
                        overflow: "hidden",
                      }}
                    >
                      <div style={{ position: "relative", zIndex: 1 }}>
                        <span
                          style={{
                            color: "#0ecb81",
                            fontWeight: 500,
                          }}
                        >
                          {formatPrice(bid.price)}
                        </span>
                      </div>
                      <div style={{ position: "relative", zIndex: 1 }}>
                        {bid.quantity.toFixed(4)}
                      </div>
                      <div
                        style={{
                          position: "relative",
                          zIndex: 1,
                          color: "#848E9C",
                        }}
                      >
                        {(bid.total / 1000).toFixed(1)}K
                      </div>
                      <div
                        style={{
                          position: "absolute",
                          right: 0,
                          top: 0,
                          height: "100%",
                          width: `${widthPercent}%`,
                          backgroundColor: "#0ecb81",
                          opacity: 0.1,
                        }}
                      />
                    </div>
                  );
                })}
              </div>
            </Card>
          </Col>

          <Col xs={24} lg={8}>
            <Card
              style={{
                backgroundColor: "#181a20",
                borderColor: "#2b3139",
                color: "#fff",
              }}
              bodyStyle={{ padding: 16 }}
            >
              <Typography.Title
                level={4}
                style={{
                  margin: 0,
                  color: "#fff",
                  fontSize: 18,
                  marginBottom: 16,
                }}
              >
                Market Trades
              </Typography.Title>

              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 8,
                  color: "#848E9C",
                  fontSize: 12,
                  fontWeight: 500,
                  paddingBottom: 8,
                  marginBottom: 8,
                  borderBottom: "1px solid #2b3139",
                }}
              >
                <div>Price(USDT)</div>
                <div>Amount(BTC)</div>
                <div>Time</div>
              </div>

              <div
                style={{
                  maxHeight: 600,
                  overflowY: "auto",
                }}
              >
                {trades.length > 0 ? (
                  trades.slice(0, 20).map((trade, idx) => (
                    <div
                      key={`trade-${trade.tradeId || idx}`}
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(3, 1fr)",
                        gap: 8,
                        fontSize: 14,
                        padding: "4px 0",
                        borderRadius: 4,
                      }}
                    >
                      <div
                        style={{
                          fontWeight: 500,
                          color: trade.isBuyerMaker ? "#f6465d" : "#0ecb81",
                        }}
                      >
                        {formatPrice(trade.price)}
                      </div>
                      <div style={{ color: "#fff" }}>
                        {trade.quantity.toFixed(4)}
                      </div>
                      <div style={{ color: "#848E9C" }}>
                        {formatTime(trade.time)}
                      </div>
                    </div>
                  ))
                ) : (
                  <div
                    style={{
                      textAlign: "center",
                      color: "#848E9C",
                      padding: "32px 0",
                    }}
                  >
                    No trades available
                  </div>
                )}
              </div>
            </Card>
          </Col>
        </Row>
      </Content>
    </Layout>
  );
}

