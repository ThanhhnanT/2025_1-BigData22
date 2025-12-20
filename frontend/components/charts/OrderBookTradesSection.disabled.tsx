/**
 * OrderBookTradesSection Component (DISABLED)
 * 
 * This component contains the Order Book and Market Trades functionality
 * that requires Redis/Kafka/WebSocket infrastructure.
 * 
 * Currently commented out for MongoDB-only mode.
 * To re-enable:
 * 1. Ensure Redis and Kafka services are running
 * 2. Uncomment the WebSocket management code
 * 3. Import this component in TradingDashboard
 * 4. Add state management for order book and trades data
 */

/*
import { useState, useEffect, useRef } from "react";
import { Table, Button, Space, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import { COLORS, SHADOWS, BORDER_RADIUS } from "@/constants/theme";
import type { OrderBookEntry, Trade } from "@/types/trading";

const { Title } = Typography;

interface OrderBookTradesSectionProps {
  symbol: string;
  wsBase: string;
}

export default function OrderBookTradesSection({ symbol, wsBase }: OrderBookTradesSectionProps) {
  // ============================================================================
  // STATE - Order Book & Trades (Disabled for MongoDB-only mode)
  // ============================================================================
  const [bids, setBids] = useState<OrderBookEntry[]>([]);
  const [asks, setAsks] = useState<OrderBookEntry[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [currentPrice, setCurrentPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);
  const [granularity, setGranularity] = useState<string>("0.1");

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

  const tradesData = trades.slice(0, 6).map((trade, idx) => ({
    ...trade,
    key: `trade-${trade.tradeId || idx}`,
  }));

  // ============================================================================
  // WEBSOCKET MANAGEMENT (To be implemented)
  // ============================================================================
  useEffect(() => {
    // WebSocket connection logic here
    // Connect to order book and trades streams
    // Handle reconnection logic
    
    return () => {
      // Cleanup WebSocket connections
    };
  }, [symbol, wsBase]);

  // ============================================================================
  // RENDER
  // ============================================================================
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', width: '100%', height: '100%' }}>
      // Order Book Section
      <section style={{
        backgroundColor: COLORS.background.secondary,
        borderRadius: BORDER_RADIUS.lg,
        border: `1px solid ${COLORS.border.primary}`,
        boxShadow: SHADOWS.md,
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column',
        height: '400px',
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

        // Order Book Tables (Asks, Current Price, Bids)
        <div style={{ flex: 1, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
          // Asks Table
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {asksData.length > 0 ? (
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

          // Current Price Display
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

          // Bids Table
          <div style={{ flex: 1, overflowY: 'auto' }}>
            {bidsData.length > 0 ? (
              <Table
                columns={orderBookColumns}
                dataSource={bidsData}
                pagination={false}
                size="small"
                className="order-book-table"
                rowClassName="relative order-book-row-bid"
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

      // Market Trades Section
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
  );
}
*/

// Export placeholder for future use
export default function OrderBookTradesSection() {
  return null;
}
