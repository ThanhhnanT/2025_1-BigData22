/**
 * OrderBookTradesSection Component
 * 
 * This component contains the Order Book and Market Trades functionality
 * that requires Redis/Kafka/WebSocket infrastructure.
 */

import { useState, useEffect, useRef } from "react";
import { Table, Button, Space, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import axios from "axios";
import { COLORS, SHADOWS, BORDER_RADIUS } from "@/constants/theme";
import type { OrderBookEntry, Trade, OrderBookMessage, TradesMessage, Prediction } from "@/types/trading";

const { Title } = Typography;

interface OrderBookTradesSectionProps {
  symbol: string;
  wsBase: string;
}

export default function OrderBookTradesSection({ symbol, wsBase }: OrderBookTradesSectionProps) {
  // ============================================================================
  // STATE - Order Book & Trades
  // ============================================================================
  const [bids, setBids] = useState<OrderBookEntry[]>([]);
  const [asks, setAsks] = useState<OrderBookEntry[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);
  const [granularity, setGranularity] = useState<string>("0.1");
  const [isLoadingOrderBook, setIsLoadingOrderBook] = useState<boolean>(true);
  const [bidsUpdateCounter, setBidsUpdateCounter] = useState<number>(0); // Counter to force re-render
  
  // ============================================================================
  // STATE - Prediction
  // ============================================================================
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [isLoadingPrediction, setIsLoadingPrediction] = useState<boolean>(false);
  
  // Debug: Log when bids/asks state changes
  useEffect(() => {
    if (bids.length > 0) {
      console.log(`[OrderBook State] Bids updated: ${bids.length} levels, first bid: ${bids[0].price}, counter: ${bidsUpdateCounter}`);
    }
  }, [bids, bidsUpdateCounter]);
  
  useEffect(() => {
    if (asks.length > 0) {
      console.log(`[OrderBook State] Asks updated: ${asks.length} levels, first ask: ${asks[0].price}`);
    }
  }, [asks]);

  // ============================================================================
  // REFS - WebSocket Management
  // ============================================================================
  const wsOrderBookRef = useRef<WebSocket | null>(null);
  const wsTradesRef = useRef<WebSocket | null>(null);
  const reconnectTimerOB = useRef<NodeJS.Timeout | null>(null);
  const reconnectTimerTrades = useRef<NodeJS.Timeout | null>(null);
  const currentSymbolRef = useRef<string>(symbol);
  const isChangingSymbolRef = useRef<boolean>(false);

  // ============================================================================
  // UTILITY FUNCTIONS
  // ============================================================================
  const formatPrice = (price: number): string => {
    const decimals = granularity === "0.01" ? 2 : 1;
    return price.toFixed(decimals);
  };

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

  // ============================================================================
  // TABLE DEFINITIONS
  // ============================================================================
  const orderBookColumns: ColumnsType<OrderBookEntry & { key: string; type: 'ask' | 'bid' }> = [
    {
      title: 'Price(USDT)',
      dataIndex: 'price',
      key: 'price',
      align: 'left',
      render: (price: number, record) => (
        <span style={{ color: record.type === 'ask' ? COLORS.trading.sell : COLORS.trading.buy }}>
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
        <span style={{ color: COLORS.text.primary }}>{quantity.toFixed(4)}</span>
      ),
    },
    {
      title: 'Total',
      dataIndex: 'total',
      key: 'total',
      align: 'right',
      render: (total: number) => (
        <span style={{ color: COLORS.text.primary }}>{(total / 1000).toFixed(1)}K</span>
      ),
    },
  ];

  const tradesColumns: ColumnsType<Trade> = [
    {
      title: 'Price(USDT)',
      dataIndex: 'price',
      key: 'price',
      align: 'left',
      render: (price: number, record) => (
        <span style={{ color: record.isBuyerMaker ? COLORS.trading.sell : COLORS.trading.buy }}>
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
        <span style={{ color: COLORS.text.primary }}>{quantity.toFixed(4)}</span>
      ),
    },
    {
      title: 'Time',
      dataIndex: 'time',
      key: 'time',
      align: 'right',
      render: (time: number) => (
        <span style={{ color: COLORS.text.primary }}>{formatTime(time)}</span>
      ),
    },
  ];

  // ============================================================================
  // DATA PREPARATION
  // ============================================================================
  const asksData = asks.reverse().map((ask, idx) => ({
    ...ask,
    key: `ask-${idx}`,
    type: 'ask' as const,
  }));

  const bidsData = bids.map((bid, idx) => ({
    ...bid,
    key: `bid-${bid.price}-${idx}`, // Use price in key to force re-render when price changes
    type: 'bid' as const,
  }));

  const tradesData = trades.map((trade, idx) => ({
    ...trade,
    key: `trade-${trade.tradeId || idx}`,
  }));

  // ============================================================================
  // WEBSOCKET MANAGEMENT & DATA FETCHING
  // ============================================================================
  useEffect(() => {
    // Derive API_BASE from wsBase inside useEffect to avoid dependency issues
    const API_BASE = wsBase.replace(/^ws/, "http");
    let isMounted = true;
    let connectTimeoutOB: NodeJS.Timeout | null = null;
    let connectTimeoutTrades: NodeJS.Timeout | null = null;
    let connectDelay: NodeJS.Timeout | null = null;
    
    // Mark that we're changing symbol to prevent reconnections
    isChangingSymbolRef.current = true;
    
    // Close existing WebSockets FIRST before updating symbol
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
    
    // Fetch initial snapshot from REST API
    async function fetchInitialData() {
      setIsLoadingOrderBook(true);
      try {
        // Fetch Order Book
        const obRes = await axios.get(`${API_BASE}/orderbook`, {
          params: { symbol, limit: 20 },
        });
        if (obRes.data && isMounted) {
          const bidsData = obRes.data.bids || [];
          const asksData = obRes.data.asks || [];
          
          setBids(bidsData);
          setAsks(asksData);
          
          // Calculate current price (mid price)
          if (bidsData.length > 0 && asksData.length > 0) {
            const midPrice = (bidsData[0].price + asksData[0].price) / 2;
            setCurrentPrice(midPrice);
          } else if (bidsData.length > 0) {
            // If only bids, use best bid
            setCurrentPrice(bidsData[0].price);
          } else if (asksData.length > 0) {
            // If only asks, use best ask
            setCurrentPrice(asksData[0].price);
          }
          
          setIsLoadingOrderBook(false);
          
          // Debug logging only if no data
          if (bidsData.length === 0 && asksData.length === 0) {
            console.warn(`[OrderBook] No bids or asks data for ${symbol} from REST API`);
          }
        } else {
          setIsLoadingOrderBook(false);
        }
      } catch (err: any) {
        console.error(`[OrderBook] Error fetching orderbook for ${symbol}:`, err);
        if (err.response) {
          console.error(`[OrderBook] Response status: ${err.response.status}`, err.response.data);
        }
        setIsLoadingOrderBook(false);
      }

      try {
        // Fetch Trades
        const tradesRes = await axios.get(`${API_BASE}/trades`, {
          params: { symbol, limit: 50 },
        });
        if (tradesRes.data && tradesRes.data.trades && isMounted) {
          setTrades(tradesRes.data.trades.reverse()); // Show newest first
          // Update current price from latest trade
          if (tradesRes.data.trades.length > 0) {
            const latestTrade = tradesRes.data.trades[tradesRes.data.trades.length - 1];
            setCurrentPrice(latestTrade.price);
          }
        }
      } catch (err) {
        console.error("Error fetching trades:", err);
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

      const wsUrl = `${wsBase}/ws/orderbook?symbol=${targetSymbol}`;
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
          
          // Only process if symbol matches current symbol
          if (data.symbol && data.symbol !== currentSymbol) {
            return;
          }
          
          if (data.type === "initial" || data.type === "update") {
            const bidsData = data.bids || [];
            const asksData = data.asks || [];
            
            // Debug logging
            console.log(`[OrderBook WS] Received update for ${currentSymbol}: bids=${bidsData.length}, asks=${asksData.length}`);
            if (bidsData.length > 0) {
              console.log(`[OrderBook WS] First bid: ${bidsData[0].price}, Last bid: ${bidsData[bidsData.length - 1].price}`);
            }
            if (asksData.length > 0) {
              console.log(`[OrderBook WS] First ask: ${asksData[0].price}, Last ask: ${asksData[asksData.length - 1].price}`);
            }
            
            // Only update if we have valid data (don't clear existing data with empty arrays)
            if (bidsData.length > 0 || asksData.length > 0) {
              if (bidsData.length > 0) {
                console.log(`[OrderBook WS] Updating bids for ${currentSymbol}: ${bidsData.length} levels, first bid price: ${bidsData[0].price}`);
                // Force state update by creating new array reference
                setBids([...bidsData]);
                // Increment counter to force Table re-render
                setBidsUpdateCounter(prev => prev + 1);
              } else {
                console.warn(`[OrderBook WS] No bids in update for ${currentSymbol}, keeping existing bids`);
              }
              if (asksData.length > 0) {
                console.log(`[OrderBook WS] Updating asks for ${currentSymbol}: ${asksData.length} levels, first ask price: ${asksData[0].price}`);
                // Force state update by creating new array reference
                setAsks([...asksData]);
              } else {
                console.warn(`[OrderBook WS] No asks in update for ${currentSymbol}, keeping existing asks`);
              }
              setIsLoadingOrderBook(false);
              
              // Update current price
              if (bidsData.length > 0 && asksData.length > 0) {
                const midPrice = (bidsData[0].price + asksData[0].price) / 2;
                setCurrentPrice(midPrice);
              } else if (bidsData.length > 0) {
                // If only bids, use best bid
                setCurrentPrice(bidsData[0].price);
              } else if (asksData.length > 0) {
                // If only asks, use best ask
                setCurrentPrice(asksData[0].price);
              }
            } else {
              // Empty update - log warning but don't clear existing data
              console.warn(`[OrderBook WS] Received empty update for ${currentSymbol}, keeping existing data`);
            }
          }
        } catch (err) {
          console.error("[OrderBook WS] Error parsing Order Book message:", err, event.data);
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
        const expectedSymbol = targetSymbol;
        
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

      const wsUrl = `${wsBase}/ws/trades?symbol=${targetSymbol}&limit=50`;
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
          
          // Only process if symbol matches current symbol
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
              setCurrentPrice((prevPrice) => {
                if (prevPrice > 0) {
                  const change = ((newPrice - prevPrice) / prevPrice) * 100;
                  setPriceChange(change);
                }
                return newPrice;
              });
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
        const expectedSymbol = targetSymbol;
        
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
  }, [symbol, wsBase]);

  // ============================================================================
  // PREDICTION FETCHING - Poll every 1 minute
  // ============================================================================
  useEffect(() => {
    const API_BASE = wsBase.replace(/^ws/, "http");
    let isMounted = true;
    let pollInterval: NodeJS.Timeout | null = null;
    
    const fetchPrediction = async () => {
      if (!isMounted) return;
      
      try {
        setIsLoadingPrediction(true);
        const response = await axios.get(`${API_BASE}/prediction/${symbol}`);
        if (response.data && response.data.prediction && isMounted) {
          setPrediction(response.data.prediction);
        }
      } catch (error: any) {
        // If 404 or no data, keep existing prediction (don't clear it)
        if (error.response?.status === 404) {
          console.log(`[Prediction] No prediction found for ${symbol}, keeping existing data`);
        } else {
          console.error(`[Prediction] Error fetching prediction for ${symbol}:`, error);
        }
      } finally {
        if (isMounted) {
          setIsLoadingPrediction(false);
        }
      }
    };
    
    // Fetch immediately when symbol changes
    fetchPrediction();
    
    // Poll every 1 minute (60000ms)
    pollInterval = setInterval(() => {
      if (isMounted) {
        fetchPrediction();
      }
    }, 60000);
    
    return () => {
      isMounted = false;
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [symbol, wsBase]);

  // ============================================================================
  // UTILITY FUNCTIONS FOR PREDICTION
  // ============================================================================
  const formatPredictionTime = (timeStr: string): string => {
    try {
      const date = new Date(timeStr);
      return date.toLocaleTimeString("en-US", {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return timeStr;
    }
  };

  const getSymbolDisplayName = (symbol: string): string => {
    // Convert BTCUSDT to BTC/USDT
    if (symbol.endsWith("USDT")) {
      return `${symbol.slice(0, -4)}/USDT`;
    }
    return symbol;
  };

  // ============================================================================
  // RENDER
  // ============================================================================
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '100%', height: '100%' }}>
      {/* AI Price Prediction Section */}
      <section style={{
        backgroundColor: COLORS.background.secondary,
        borderRadius: BORDER_RADIUS.lg,
        border: `1px solid ${COLORS.border.primary}`,
        boxShadow: SHADOWS.md,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
      }}>
        <div style={{
          padding: '12px 16px',
          borderBottom: `1px solid ${COLORS.border.primary}`,
          backgroundColor: 'rgba(31, 41, 55, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ 
              fontSize: '18px', 
              color: '#a855f7' // purple-500
            }}>🧠</span>
            <Title level={5} style={{ margin: 0, color: COLORS.text.primary, fontSize: '14px' }}>
              AI Price Prediction
            </Title>
          </div>
          <span style={{
            fontSize: '10px',
            fontFamily: 'monospace',
            backgroundColor: 'rgba(168, 85, 247, 0.1)',
            color: '#c084fc', // purple-300
            padding: '2px 6px',
            borderRadius: BORDER_RADIUS.sm,
            border: '1px solid rgba(168, 85, 247, 0.2)',
          }}>
            BETA
          </span>
        </div>

        <div style={{ padding: '16px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {isLoadingPrediction && !prediction ? (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '20px',
              color: COLORS.text.secondary,
              fontSize: '14px',
            }}>
              Loading prediction...
            </div>
          ) : prediction ? (
            <>
              {/* Symbol and Current Price */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <div style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '50%',
                    backgroundColor: '#3b82f6', // blue-500
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'white',
                    fontSize: '12px',
                    fontWeight: 'bold',
                    boxShadow: SHADOWS.sm,
                  }}>
                    {symbol.slice(0, 1)}
                  </div>
                  <div>
                    <div style={{ fontSize: '14px', fontWeight: 'bold', color: COLORS.text.primary }}>
                      {getSymbolDisplayName(prediction.symbol)}
                    </div>
                    <div style={{ fontSize: '12px', color: COLORS.text.secondary }}>
                      {symbol === 'BTCUSDT' ? 'Bitcoin' : symbol === 'ETHUSDT' ? 'Ethereum' : 'Cryptocurrency'}
                    </div>
                  </div>
                </div>
                <div style={{ textAlign: 'right' }}>
                  <div style={{ fontSize: '12px', color: COLORS.text.secondary, marginBottom: '4px' }}>Current</div>
                  <div style={{ fontSize: '14px', fontFamily: 'monospace', fontWeight: 'medium', color: COLORS.text.primary }}>
                    ${prediction.current_price.toFixed(4)}
                  </div>
                </div>
              </div>

              {/* Timeline */}
              <div style={{ position: 'relative', padding: '16px 0' }}>
                {/* Gradient line */}
                <div style={{
                  position: 'absolute',
                  top: '50%',
                  left: 0,
                  right: 0,
                  height: '2px',
                  background: `linear-gradient(to right, ${COLORS.border.primary}, ${COLORS.border.secondary || COLORS.border.primary}, ${COLORS.border.primary})`,
                  zIndex: 0,
                }} />
                
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', position: 'relative', zIndex: 1 }}>
                  {/* Current time */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                    <div style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      backgroundColor: COLORS.text.secondary,
                      border: `4px solid ${COLORS.background.secondary}`,
                    }} />
                    <span style={{ fontSize: '10px', fontFamily: 'monospace', color: COLORS.text.secondary, marginTop: '4px' }}>
                      {formatPredictionTime(prediction.prediction_time)}
                    </span>
                  </div>

                  {/* Status badge */}
                  <div style={{
                    backgroundColor: COLORS.background.secondary,
                    border: `1px solid ${COLORS.border.primary}`,
                    borderRadius: '9999px',
                    padding: '4px 12px',
                    display: 'flex',
                    alignItems: 'center',
                    gap: '8px',
                    zIndex: 10,
                    boxShadow: SHADOWS.sm,
                  }}>
                    <span style={{
                      width: '8px',
                      height: '8px',
                      borderRadius: '50%',
                      backgroundColor: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                      animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                    }} />
                    <span style={{
                      fontSize: '12px',
                      fontWeight: 'semibold',
                      color: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                      letterSpacing: '0.05em',
                    }}>
                      {prediction.direction === 'UP' ? 'BULLISH' : 'BEARISH'}
                    </span>
                  </div>

                  {/* Target time */}
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                    <div style={{
                      width: '10px',
                      height: '10px',
                      borderRadius: '50%',
                      backgroundColor: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                      border: `4px solid ${COLORS.background.secondary}`,
                      boxShadow: `0 0 8px ${prediction.direction === 'UP' ? 'rgba(16, 185, 129, 0.5)' : 'rgba(239, 68, 68, 0.5)'}`,
                    }} />
                    <span style={{
                      fontSize: '10px',
                      fontFamily: 'monospace',
                      color: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                      marginTop: '4px',
                      fontWeight: 'bold',
                    }}>
                      {formatPredictionTime(prediction.target_time)}
                    </span>
                  </div>
                </div>
              </div>

              {/* Target Price and Expected Change Grid */}
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
                <div style={{
                  backgroundColor: 'rgba(55, 65, 81, 0.4)',
                  borderRadius: BORDER_RADIUS.md,
                  padding: '10px',
                  border: `1px solid ${COLORS.border.primary}`,
                }}>
                  <div style={{ fontSize: '10px', color: COLORS.text.secondary, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                    Target Price
                  </div>
                  <div style={{ fontSize: '16px', fontFamily: 'monospace', fontWeight: 'bold', color: COLORS.text.primary, display: 'flex', alignItems: 'end', gap: '4px' }}>
                    ${prediction.predicted_price.toFixed(4)}
                    <span style={{ fontSize: '12px', color: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error }}>
                      {prediction.direction === 'UP' ? '📈' : '📉'}
                    </span>
                  </div>
                </div>
                <div style={{
                  backgroundColor: 'rgba(55, 65, 81, 0.4)',
                  borderRadius: BORDER_RADIUS.md,
                  padding: '10px',
                  border: `1px solid ${COLORS.border.primary}`,
                }}>
                  <div style={{ fontSize: '10px', color: COLORS.text.secondary, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                    Exp. Change
                  </div>
                  <div style={{
                    fontSize: '16px',
                    fontFamily: 'monospace',
                    fontWeight: 'bold',
                    color: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                  }}>
                    {prediction.predicted_change >= 0 ? '+' : ''}{prediction.predicted_change.toFixed(2)}%
                  </div>
                </div>
              </div>

              {/* Confidence Score */}
              <div style={{ fontSize: '10px', textAlign: 'center', color: COLORS.text.secondary, marginTop: '4px' }}>
                Prediction confidence: <span style={{ color: COLORS.text.primary, fontWeight: 'medium' }}>
                  {prediction.confidence_score.toFixed(1)}%
                </span> based on ML model
              </div>
            </>
          ) : (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              padding: '20px',
              color: COLORS.text.secondary,
              fontSize: '14px',
            }}>
              No prediction available yet
            </div>
          )}
        </div>
      </section>

      {/* Order Book Section */}
      <section style={{
        backgroundColor: COLORS.background.secondary,
        borderRadius: BORDER_RADIUS.lg,
        border: `1px solid ${COLORS.border.primary}`,
        boxShadow: SHADOWS.md,
        overflow: 'visible',
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
      }}>
        <div style={{
          padding: '12px 16px',
          borderBottom: `1px solid ${COLORS.border.primary}`,
          backgroundColor: 'rgba(31, 41, 55, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <Title level={5} style={{ margin: 0, color: COLORS.text.primary, fontSize: '14px' }}>Order Book</Title>
          <Space size={4} style={{ fontSize: '12px', backgroundColor: COLORS.background.hover, padding: '2px', borderRadius: BORDER_RADIUS.sm }}>
            <Button
              type={granularity === "0.1" ? "primary" : "text"}
              onClick={() => setGranularity("0.1")}
              size="small"
              style={{
                backgroundColor: granularity === "0.1" ? '#4b5563' : 'transparent',
                color: COLORS.text.primary,
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
                color: COLORS.text.primary,
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

        {/* Order Book Tables (Asks, Current Price, Bids) */}
        <div style={{ flex: 1, overflow: 'visible', display: 'flex', flexDirection: 'column' }}>
          {/* Asks Table */}
          <div style={{ flex: 1, overflowY: 'visible', overflow: 'visible' }}>
            {isLoadingOrderBook ? (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: COLORS.text.secondary,
                fontSize: '14px',
              }}>
                Loading...
              </div>
            ) : asksData.length > 0 ? (
              <Table
                columns={orderBookColumns}
                dataSource={asksData}
                pagination={false}
                size="small"
                className="order-book-table"
                rowClassName="relative order-book-row-ask"
              />
            ) : (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: COLORS.text.primary,
                fontSize: '14px',
              }}>
                No data
              </div>
            )}
          </div>

          {/* Current Price Display */}
          <div style={{
            position: 'sticky',
            top: 0,
            bottom: 0,
            zIndex: 20,
            padding: '12px 0',
            margin: '4px 0',
            borderTop: `1px solid ${COLORS.border.primary}`,
            borderBottom: `1px solid ${COLORS.border.primary}`,
            backgroundColor: 'rgba(31, 41, 55, 0.9)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '12px',
            flexShrink: 0,
          }}>
            <span style={{ fontSize: '20px', fontWeight: 'bold', color: COLORS.status.success }}>
              {currentPrice > 0 ? formatPrice(currentPrice) : "—"}
            </span>
            {priceChange !== 0 && (
              <span style={{
                fontSize: '14px',
                color: priceChange >= 0 ? COLORS.status.success : COLORS.status.error,
              }}>
                {priceChange >= 0 ? "↑" : "↓"} {Math.abs(priceChange).toFixed(2)}%
              </span>
            )}
            <span style={{ fontSize: '12px', color: COLORS.text.primary }}>
              ≈ ${currentPrice > 0 ? formatPrice(currentPrice) : "—"}
            </span>
          </div>

          {/* Bids Table */}
          <div style={{ flex: 1, overflowY: 'visible', overflow: 'visible' }}>
            {isLoadingOrderBook ? (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: COLORS.text.secondary,
                fontSize: '14px',
              }}>
                Loading...
              </div>
            ) : bidsData.length > 0 ? (
              <Table
                columns={orderBookColumns}
                dataSource={bidsData}
                pagination={false}
                size="small"
                className="order-book-table"
                rowClassName="relative order-book-row-bid"
                key={`bids-table-${bidsData[0]?.price || 'empty'}-${bidsUpdateCounter}`} // Force re-render when bids change
                rowKey={(record) => `bid-${record.price}-${record.quantity}`} // Explicit rowKey for better React reconciliation
              />
            ) : (
              <div style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%',
                color: COLORS.text.primary,
                fontSize: '14px',
              }}>
                No data
              </div>
            )}
          </div>
        </div>
      </section>

      {/* Market Trades Section */}
      <section style={{
        backgroundColor: COLORS.background.secondary,
        borderRadius: BORDER_RADIUS.lg,
        border: `1px solid ${COLORS.border.primary}`,
        boxShadow: SHADOWS.md,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        flex: 1,
        minHeight: 0,
      }}>
        <div style={{
          padding: '12px 16px',
          borderBottom: `1px solid ${COLORS.border.primary}`,
          backgroundColor: 'rgba(31, 41, 55, 0.5)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexShrink: 0,
        }}>
          <Title level={5} style={{ margin: 0, color: COLORS.text.primary, fontSize: '14px' }}>Market Trades</Title>
        </div>

        <div style={{ flex: 1, overflowY: 'visible', overflow: 'visible', maxHeight: 'none' }}>
          {tradesData.length > 0 ? (
            <Table
              columns={tradesColumns}
              dataSource={tradesData}
              pagination={false}
              size="small"
              className="trades-table"
              rowClassName="trades-table-row"
            />
          ) : (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              height: '100%',
              color: COLORS.text.primary,
              fontSize: '14px',
            }}>
              No data
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

