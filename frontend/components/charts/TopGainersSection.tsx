"use client";

import { useState, useEffect } from "react";
import { Table, Button, Typography, Space } from "antd";
import type { ColumnsType } from "antd/es/table";
import { TrophyOutlined } from "@ant-design/icons";
import axios from "axios";
import { COLORS, SHADOWS, BORDER_RADIUS } from "@/constants/theme";

const { Title } = Typography;

interface CoinRanking {
  symbol: string;
  price: number;
  percent_change: number;
  volume?: number;
  timestamp: number;
}

interface RankingResponse {
  type: string;
  count: number;
  rankings: CoinRanking[];
  updated_at: string;
}

interface TopGainersSectionProps {
  apiBase?: string;
}

// Get coin icon color based on symbol
const getCoinIconColor = (symbol: string): string => {
  const colors: Record<string, string> = {
    BTC: "#f97316", // orange
    ETH: "#2563eb", // blue
    SOL: "#a855f7", // purple
    XRP: "#9ca3af", // gray
    ADA: "#60a5fa", // blue-400
    BNB: "#fbbf24", // yellow
    DOGE: "#fbbf24", // yellow
    DOT: "#e879f9", // pink
    MATIC: "#8b5cf6", // purple
    AVAX: "#ef4444", // red
    LINK: "#3b82f6", // blue
    UNI: "#10b981", // green
    LTC: "#6b7280", // gray
    ATOM: "#06b6d4", // cyan
    ETC: "#84cc16", // lime
  };
  
  const baseSymbol = symbol.replace("USDT", "");
  return colors[baseSymbol] || "#6b7280";
};

// Generate simple SVG chart path
const generateChartPath = (percentChange: number): string => {
  const isPositive = percentChange >= 0;
  const intensity = Math.min(Math.abs(percentChange) / 10, 1); // Normalize to 0-1
  
  // Simple path: start high/low, curve to end
  if (isPositive) {
    // Green upward curve
    const startY = 35 - (intensity * 10);
    const endY = 5;
    return `M0 ${startY} Q 10 ${startY - 5}, 20 ${startY - 8} T 40 ${startY - 12} T 60 ${startY - 15} T 80 ${startY - 18} T 100 ${endY}`;
  } else {
    // Red downward curve
    const startY = 5 + (intensity * 10);
    const endY = 35;
    return `M0 ${startY} Q 10 ${startY + 5}, 20 ${startY + 8} T 40 ${startY + 12} T 60 ${startY + 15} T 80 ${startY + 18} T 100 ${endY}`;
  }
};

export default function TopGainersSection({ apiBase }: TopGainersSectionProps) {
  const [rankings, setRankings] = useState<CoinRanking[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<"gainers" | "losers" | "volume">("gainers");
  
  // Priority: apiBase prop > browser detection > env variables > localhost
  const API_BASE = apiBase || 
    (typeof window !== "undefined" ? "http://crypto.local/api" : null) ||
    process.env.NEXT_PUBLIC_API_BASE ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";

  const fetchRankings = async () => {
    try {
      setLoading(true);
      const response = await axios.get<RankingResponse>(
        `${API_BASE}/ranking/top-gainers`,
        {
          params: {
            limit: 1000, // Display all coins
            type: activeTab === "volume" ? "gainers" : activeTab, // Volume uses gainers data for now
          },
        }
      );
      setRankings(response.data.rankings || []);
    } catch (error) {
      console.error("Error fetching rankings:", error);
      setRankings([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRankings();
    const interval = setInterval(fetchRankings, 60000); // Refresh every minute
    return () => clearInterval(interval);
  }, [activeTab, API_BASE]);

  const columns: ColumnsType<CoinRanking & { rank: number }> = [
    {
      title: "#",
      dataIndex: "rank",
      key: "rank",
      width: 60,
      align: "center",
      render: (rank: number) => (
        <span style={{ fontWeight: "bold", color: COLORS.text.muted }}>
          {rank}
        </span>
      ),
    },
    {
      title: "Asset",
      key: "asset",
      render: (_, record) => {
        const baseSymbol = record.symbol.replace("USDT", "");
        const iconColor = getCoinIconColor(record.symbol);
        
        return (
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <div
              style={{
                width: 24,
                height: 24,
                borderRadius: "50%",
                backgroundColor: iconColor,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: "#fff",
                fontSize: "10px",
                fontWeight: "bold",
                flexShrink: 0,
              }}
            >
              {baseSymbol[0]}
            </div>
            <div>
              <div style={{ fontWeight: "bold", color: COLORS.text.primary }}>
                {baseSymbol}
              </div>
              <div
                style={{
                  fontSize: "12px",
                  color: COLORS.text.muted,
                  fontWeight: "normal",
                }}
              >
                {record.symbol}
              </div>
            </div>
          </div>
        );
      },
    },
    {
      title: "Price",
      dataIndex: "price",
      key: "price",
      align: "right",
      render: (price: number) => (
        <span style={{ fontFamily: "monospace", color: COLORS.text.primary }}>
          ${price.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      ),
    },
    {
      title: "Change",
      dataIndex: "percent_change",
      key: "percent_change",
      align: "right",
      render: (change: number) => {
        const isPositive = change >= 0;
        const color = isPositive ? COLORS.trading.buy : COLORS.trading.sell;
        return (
          <span
            style={{
              fontFamily: "monospace",
              color,
              fontWeight: "semibold",
            }}
          >
            {isPositive ? "+" : ""}
            {change.toFixed(2)}%
          </span>
        );
      },
    },
    {
      title: "24h Vol",
      dataIndex: "volume",
      key: "volume",
      align: "right",
      render: (volume: number | undefined) => {
        if (!volume || volume === 0) {
          return (
            <span style={{ fontFamily: "monospace", color: COLORS.text.muted }}>
              -
            </span>
          );
        }
        // Format volume in millions/thousands
        const formatted = volume >= 1000000 
          ? `$${(volume / 1000000).toFixed(2)}M`
          : volume >= 1000
          ? `$${(volume / 1000).toFixed(2)}K`
          : `$${volume.toFixed(2)}`;
        
        return (
          <span style={{ fontFamily: "monospace", color: COLORS.text.primary }}>
            {formatted}
          </span>
        );
      },
    },
    {
      title: "Chart",
      key: "chart",
      align: "right",
      width: 120,
      render: (_, record) => {
        const chartColor = record.percent_change >= 0 ? COLORS.trading.buy : COLORS.trading.sell;
        const path = generateChartPath(record.percent_change);
        
        return (
          <div style={{ height: 32, width: 96, marginLeft: "auto" }}>
            <svg
              className="w-full h-full"
              fill="none"
              preserveAspectRatio="none"
              stroke={chartColor}
              strokeWidth="2"
              viewBox="0 0 100 40"
            >
              <path d={path} />
            </svg>
          </div>
        );
      },
    },
  ];

  const dataSource = rankings.map((ranking, index) => ({
    ...ranking,
    key: ranking.symbol,
    rank: index + 1,
  }));

  return (
    <div
      style={{
        backgroundColor: COLORS.background.secondary,
        borderRadius: BORDER_RADIUS.lg,
        border: `1px solid ${COLORS.border.primary}`,
        boxShadow: SHADOWS.md,
        overflow: "visible",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: `1px solid ${COLORS.border.primary}`,
          backgroundColor: `${COLORS.background.secondary}80`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <Title
          level={5}
          style={{
            margin: 0,
            color: COLORS.text.primary,
            display: "flex",
            alignItems: "center",
            gap: "8px",
            fontSize: "14px",
            fontWeight: 600,
          }}
        >
          <TrophyOutlined style={{ color: "#fbbf24" }} />
          Top Performers (1m)
        </Title>
        
        <Space size={8}>
          <Button
            type={activeTab === "gainers" ? "primary" : "text"}
            size="small"
            onClick={() => setActiveTab("gainers")}
            style={{
              fontSize: "12px",
              height: "24px",
              padding: "0 8px",
            }}
          >
            Gainers
          </Button>
          <Button
            type={activeTab === "losers" ? "primary" : "text"}
            size="small"
            onClick={() => setActiveTab("losers")}
            style={{
              fontSize: "12px",
              height: "24px",
              padding: "0 8px",
            }}
          >
            Losers
          </Button>
          <Button
            type={activeTab === "volume" ? "primary" : "text"}
            size="small"
            onClick={() => setActiveTab("volume")}
            style={{
              fontSize: "12px",
              height: "24px",
              padding: "0 8px",
            }}
          >
            Volume
          </Button>
        </Space>
      </div>

      {/* Table */}
      <div>
        <Table
          columns={columns}
          dataSource={dataSource}
          loading={loading}
          pagination={false}
          size="small"
          rowClassName={(record, index) => {
            // Add gradient background to first row
            if (index === 0) {
              return "ranking-gradient-row";
            }
            return "";
          }}
          style={{
            backgroundColor: COLORS.background.secondary,
          }}
        />
      </div>

      <style jsx global>{`
        .ranking-gradient-row {
          background: linear-gradient(
            180deg,
            rgba(59, 130, 246, 0.1) 0%,
            rgba(59, 130, 246, 0) 100%
          ) !important;
        }
        
        .ranking-gradient-row:hover {
          background: linear-gradient(
            180deg,
            rgba(59, 130, 246, 0.15) 0%,
            rgba(59, 130, 246, 0.05) 100%
          ) !important;
        }
        
        .ant-table-tbody > tr:hover > td {
          background-color: ${COLORS.background.hover} !important;
        }
        
        .ant-table-thead > tr > th {
          background-color: ${COLORS.background.secondary}80 !important;
          border-bottom: 1px solid ${COLORS.border.primary} !important;
          color: ${COLORS.text.muted} !important;
          font-size: 12px !important;
          text-transform: uppercase !important;
          font-weight: 500 !important;
        }
        
        .ant-table-tbody > tr > td {
          border-bottom: 1px solid ${COLORS.border.primary} !important;
        }
        
        @media (max-width: 640px) {
          .hidden-sm {
            display: none !important;
          }
        }
      `}</style>
    </div>
  );
}

