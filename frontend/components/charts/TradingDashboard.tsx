"use client";

import { useEffect, useState } from "react";
import axios from "axios";
import { Row, Col } from "antd";
import DashboardHeader from "./DashboardHeader";
import ControlPanel from "./ControlPanel";
import ChartSection from "./ChartSection";
import DashboardFooter from "./DashboardFooter";
import TechnicalIndicatorsModal from "./TechnicalIndicatorsModal";
import OrderBookTradesSection from "./OrderBookTradesSection";
import { COLORS } from "@/constants/theme";
import type { TimeRangeMode, TechnicalIndicatorsConfig } from "@/types/trading";
import "./TradingDashboard.css";

/**
 * TradingDashboard Component
 * Main dashboard orchestrating all sub-components
 */
export default function TradingDashboard() {

  const [symbol, setSymbol] = useState<string>("BTCUSDT");
  const [symbols, setSymbols] = useState<string[]>([]);
  const [currentTime, setCurrentTime] = useState<string>("");
  const [mode, setMode] = useState<TimeRangeMode>("realtime");
  const [indicatorsModalOpen, setIndicatorsModalOpen] = useState<boolean>(false);
  const [indicators, setIndicators] = useState<TechnicalIndicatorsConfig>({
    ma7: { enabled: false, color: "#f59e0b", label: "MA 7", period: 7 },
    ma25: { enabled: false, color: "#3b82f6", label: "MA 25", period: 25 },
    ma99: { enabled: false, color: "#8b5cf6", label: "MA 99", period: 99 },
    ema12: { enabled: false, color: "#10b981", label: "EMA 12", period: 12 },
    ema26: { enabled: false, color: "#06b6d4", label: "EMA 26", period: 26 },
    ema50: { enabled: false, color: "#84cc16", label: "EMA 50", period: 50 },
    bollinger: { enabled: false, color: "#ec4899", label: "Bollinger Bands", period: 20 },
  });

  const API_BASE =
    process.env.NEXT_PUBLIC_API_BASE ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000";

  // Convert HTTP to WebSocket URL
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
    const updateTime = () => setCurrentTime(new Date().toLocaleTimeString());
    updateTime();
    const interval = setInterval(updateTime, 1000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={{ minHeight: "100vh", backgroundColor: COLORS.background.primary, color: COLORS.text.primary }}>
      {/* Header */}
      <DashboardHeader />

      {/* Main Content */}
      <main
        style={{
          padding: "16px 24px 32px",
          maxWidth: "1536px",
          margin: "0 auto",
        }}
      >
        {/* Control Panel */}
        <ControlPanel
          symbol={symbol}
          symbols={symbols}
          mode={mode}
          onSymbolChange={setSymbol}
          onModeChange={setMode}
          onIndicatorsClick={() => setIndicatorsModalOpen(true)}
        />

        {/* Chart Section */}
        <Row gutter={[24, 24]} style={{ height: "calc(100vh - 250px)", minHeight: "600px" }}>
          <Col xs={24} lg={18} style={{ height: "100%", display: "flex" }}>
            <ChartSection symbol={symbol} mode={mode} indicators={indicators} />
          </Col>
          
          {/* Order Book & Trades Section */}
          <Col xs={24} lg={6} style={{ height: "100%", display: "flex" }}>
            <OrderBookTradesSection symbol={symbol} wsBase={WS_BASE} />
          </Col>
        </Row>

        {/* Footer */}
        <DashboardFooter currentTime={currentTime} />
      </main>

      {/* Technical Indicators Modal */}
      <TechnicalIndicatorsModal
        open={indicatorsModalOpen}
        onClose={() => setIndicatorsModalOpen(false)}
        indicators={indicators}
        onChange={setIndicators}
      />
    </div>
  );
}
