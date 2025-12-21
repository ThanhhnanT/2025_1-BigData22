/**
 * OrderBookSection Component
 * 
 * This component displays the Order Book with bids and asks
 */

import { useState, useEffect, useRef } from "react";
import { Table, Button, Space, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import axios from "axios";
import { COLORS, SHADOWS, BORDER_RADIUS } from "@/constants/theme";
import type { OrderBookEntry, OrderBookMessage } from "@/types/trading";

const { Title } = Typography;

interface OrderBookSectionProps {
  symbol: string;
  wsBase: string;
}

export default function OrderBookSection({ symbol, wsBase }: OrderBookSectionProps) {
  const [bids, setBids] = useState<OrderBookEntry[]>([]);
  const [asks, setAsks] = useState<OrderBookEntry[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);
  const [granularity, setGranularity] = useState<string>("0.1");
  const [isLoadingOrderBook, setIsLoadingOrderBook] = useState<boolean>(true);
  const [bidsUpdateCounter, setBidsUpdateCounter] = useState<number>(0);
  
  const wsOrderBookRef = useRef<WebSocket | null>(null);
  const reconnectTimerOB = useRef<NodeJS.Timeout | null>(null);
  const currentSymbolRef = useRef<string>(symbol);
  const isChangingSymbolRef = useRef<boolean>(false);

  const formatPrice = (price: number): string => {
    const decimals = granularity === "0.01" ? 2 : 1;
    return price.toFixed(decimals);
  };

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

  const asksData = asks.reverse().map((ask, idx) => ({
    ...ask,
    key: `ask-${idx}`,
    type: 'ask' as const,
  }));

  const bidsData = bids.map((bid, idx) => ({
    ...bid,
    key: `bid-${bid.price}-${idx}`,
    type: 'bid' as const,
  }));

  useEffect(() => {
    const API_BASE = wsBase.replace(/^ws/, "http");
    let isMounted = true;
    let connectTimeoutOB: NodeJS.Timeout | null = null;
    let connectDelay: NodeJS.Timeout | null = null;
    
    isChangingSymbolRef.current = true;
    
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
    if (reconnectTimerOB.current) {
      clearTimeout(reconnectTimerOB.current);
      reconnectTimerOB.current = null;
    }
    
    currentSymbolRef.current = symbol;
    
    connectDelay = setTimeout(() => {
      isChangingSymbolRef.current = false;
    }, 100);
    
    setBids([]);
    setAsks([]);
    setCurrentPrice(0);
    setPriceChange(0);
    
    async function fetchInitialData() {
      setIsLoadingOrderBook(true);
      try {
        const obRes = await axios.get(`${API_BASE}/orderbook`, {
          params: { symbol, limit: 20 },
        });
        if (obRes.data && isMounted) {
          const bidsData = obRes.data.bids || [];
          const asksData = obRes.data.asks || [];
          
          setBids(bidsData);
          setAsks(asksData);
          
          if (bidsData.length > 0 && asksData.length > 0) {
            const midPrice = (bidsData[0].price + asksData[0].price) / 2;
            setCurrentPrice(midPrice);
          } else if (bidsData.length > 0) {
            setCurrentPrice(bidsData[0].price);
          } else if (asksData.length > 0) {
            setCurrentPrice(asksData[0].price);
          }
          
          setIsLoadingOrderBook(false);
        } else {
          setIsLoadingOrderBook(false);
        }
      } catch (err: any) {
        console.error(`[OrderBook] Error fetching orderbook for ${symbol}:`, err);
        setIsLoadingOrderBook(false);
      }
    }

    fetchInitialData();

    function connectOrderBookWS() {
      if (isChangingSymbolRef.current) {
        return;
      }
      
      const targetSymbol = currentSymbolRef.current;
      
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
      
      if (reconnectTimerOB.current) {
        clearTimeout(reconnectTimerOB.current);
        reconnectTimerOB.current = null;
      }

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
          
          if (data.symbol && data.symbol !== currentSymbol) {
            return;
          }
          
          if (data.type === "initial" || data.type === "update") {
            const bidsData = data.bids || [];
            const asksData = data.asks || [];
            
            if (bidsData.length > 0 || asksData.length > 0) {
              if (bidsData.length > 0) {
                setBids([...bidsData]);
                setBidsUpdateCounter(prev => prev + 1);
              }
              if (asksData.length > 0) {
                setAsks([...asksData]);
              }
              setIsLoadingOrderBook(false);
              
              if (bidsData.length > 0 && asksData.length > 0) {
                const midPrice = (bidsData[0].price + asksData[0].price) / 2;
                setCurrentPrice(midPrice);
              } else if (bidsData.length > 0) {
                setCurrentPrice(bidsData[0].price);
              } else if (asksData.length > 0) {
                setCurrentPrice(asksData[0].price);
              }
            }
          }
        } catch (err) {
          console.error("[OrderBook WS] Error parsing Order Book message:", err, event.data);
        }
      };

      ws.onclose = (event) => {
        if (wsOrderBookRef.current === ws) {
          wsOrderBookRef.current = null;
        }
        
        if (!isMounted || isChangingSymbolRef.current) {
          return;
        }
        
        const currentSymbol = currentSymbolRef.current;
        const expectedSymbol = targetSymbol;
        
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

    connectTimeoutOB = setTimeout(() => {
      if (isMounted && !isChangingSymbolRef.current) {
        connectOrderBookWS();
      }
    }, 150);

    return () => {
      isMounted = false;
      isChangingSymbolRef.current = true;
      
      if (connectTimeoutOB) {
        clearTimeout(connectTimeoutOB);
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
      if (reconnectTimerOB.current) {
        clearTimeout(reconnectTimerOB.current);
        reconnectTimerOB.current = null;
      }
    };
  }, [symbol, wsBase]);

  return (
    <section style={{
      backgroundColor: COLORS.background.secondary,
      borderRadius: BORDER_RADIUS.lg,
      border: `1px solid ${COLORS.border.primary}`,
      boxShadow: SHADOWS.md,
      overflow: 'visible',
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      width: '100%',
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

      <div style={{ flex: 1, overflow: 'visible', display: 'flex', flexDirection: 'column' }}>
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
              key={`bids-table-${bidsData[0]?.price || 'empty'}-${bidsUpdateCounter}`}
              rowKey={(record) => `bid-${record.price}-${record.quantity}`}
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
  );
}

