/**
 * MarketTradesSection Component
 * 
 * This component displays the Market Trades
 */

import { useState, useEffect, useRef } from "react";
import { Table, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import axios from "axios";
import { COLORS, SHADOWS, BORDER_RADIUS } from "@/constants/theme";
import type { Trade, TradesMessage } from "@/types/trading";

const { Title } = Typography;

interface MarketTradesSectionProps {
  symbol: string;
  wsBase: string;
}

export default function MarketTradesSection({ symbol, wsBase }: MarketTradesSectionProps) {
  const [trades, setTrades] = useState<Trade[]>([]);
  const [granularity] = useState<string>("0.1");
  
  const wsTradesRef = useRef<WebSocket | null>(null);
  const reconnectTimerTrades = useRef<NodeJS.Timeout | null>(null);
  const currentSymbolRef = useRef<string>(symbol);
  const isChangingSymbolRef = useRef<boolean>(false);

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

  const tradesData = trades.map((trade, idx) => ({
    ...trade,
    key: `trade-${trade.tradeId || idx}`,
  }));

  useEffect(() => {
    const API_BASE = wsBase.replace(/^ws/, "http");
    let isMounted = true;
    let connectTimeoutTrades: NodeJS.Timeout | null = null;
    let connectDelay: NodeJS.Timeout | null = null;
    
    isChangingSymbolRef.current = true;
    
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
    if (reconnectTimerTrades.current) {
      clearTimeout(reconnectTimerTrades.current);
      reconnectTimerTrades.current = null;
    }
    
    currentSymbolRef.current = symbol;
    
    connectDelay = setTimeout(() => {
      isChangingSymbolRef.current = false;
    }, 100);
    
    setTrades([]);
    
    async function fetchInitialData() {
      try {
        const tradesRes = await axios.get(`${API_BASE}/trades`, {
          params: { symbol, limit: 50 },
        });
        if (tradesRes.data && tradesRes.data.trades && isMounted) {
          setTrades(tradesRes.data.trades.reverse());
        }
      } catch (err) {
        console.error("Error fetching trades:", err);
      }
    }

    fetchInitialData();

    function connectTradesWS() {
      if (isChangingSymbolRef.current) {
        return;
      }
      
      const targetSymbol = currentSymbolRef.current;
      
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
      
      if (reconnectTimerTrades.current) {
        clearTimeout(reconnectTimerTrades.current);
        reconnectTimerTrades.current = null;
      }

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
          
          if (data.symbol && data.symbol !== currentSymbol) {
            return;
          }
          
          if (data.type === "initial" && data.trades) {
            setTrades(data.trades.reverse());
          } else if (data.type === "realtime" && data.trade) {
            if (data.trade.symbol && data.trade.symbol !== currentSymbol) {
              return;
            }
            setTrades((prev) => {
              const updated = [data.trade!, ...prev];
              return updated.slice(0, 50);
            });
          }
        } catch (err) {
          console.error("Error parsing Trades message:", err);
        }
      };

      ws.onclose = (event) => {
        if (wsTradesRef.current === ws) {
          wsTradesRef.current = null;
        }
        
        if (!isMounted || isChangingSymbolRef.current) {
          return;
        }
        
        const currentSymbol = currentSymbolRef.current;
        const expectedSymbol = targetSymbol;
        
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

    connectTimeoutTrades = setTimeout(() => {
      if (isMounted && !isChangingSymbolRef.current) {
        connectTradesWS();
      }
    }, 150);

    return () => {
      isMounted = false;
      isChangingSymbolRef.current = true;
      
      if (connectTimeoutTrades) {
        clearTimeout(connectTimeoutTrades);
      }
      if (connectDelay) {
        clearTimeout(connectDelay);
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
      if (reconnectTimerTrades.current) {
        clearTimeout(reconnectTimerTrades.current);
        reconnectTimerTrades.current = null;
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
  );
}

