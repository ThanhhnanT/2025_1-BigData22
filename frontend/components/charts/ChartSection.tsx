"use client";

import { Typography } from "antd";
import ChartEmbedded from "./ChartEmbedded";
import { COLORS, SHADOWS, BORDER_RADIUS } from "@/constants/theme";
import type { TimeRangeMode, TechnicalIndicatorsConfig } from "@/types/trading";

const { Title, Text } = Typography;

/**
 * Get time range label based on mode
 */
function getTimeRangeLabel(mode: TimeRangeMode): string {
  const labels: Record<TimeRangeMode, string> = {
    realtime: "Real-Time (1m)",
    "7day": "7 Day (5m)",
    "30day": "30 Day (1h)",
    "6month": "6 Month (4h)",
    "1year": "1 Year (1d)",
  };
  return labels[mode];
}

/**
 * ChartSection Component
 * Full-width chart container with title and embedded chart
 */
interface ChartSectionProps {
  symbol: string;
  mode: TimeRangeMode;
  indicators: TechnicalIndicatorsConfig;
}

export default function ChartSection({ symbol, mode, indicators }: ChartSectionProps) {
  const displaySymbol = symbol.replace("USDT", "/USDT");
  const timeRangeLabel = getTimeRangeLabel(mode);

  return (
    <section
      style={{
        backgroundColor: COLORS.background.secondary,
        borderRadius: BORDER_RADIUS.lg,
        border: `1px solid ${COLORS.border.primary}`,
        boxShadow: SHADOWS.md,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
        width: "100%",
        height: "100%",
      }}
    >
      {/* Chart Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: `1px solid ${COLORS.border.primary}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          backgroundColor: "rgba(31, 41, 55, 0.5)",
          flexShrink: 0,
        }}
      >
        <Title level={5} style={{ margin: 0, color: COLORS.text.primary, display: "flex", alignItems: "center", gap: "8px" }}>
          {displaySymbol}{" "}
          <Text style={{ color: COLORS.text.primary, fontSize: "14px", fontWeight: "normal" }}>
            - {timeRangeLabel}
          </Text>
        </Title>
      </div>

      {/* Chart Container */}
      <div
        style={{
          padding: "16px",
          backgroundColor: COLORS.background.tertiary,
          position: "relative",
          flex: 1,
          overflowX: "auto",
          minHeight: 0,
        }}
      >
        <div style={{ width: "100%", height: "100%", minWidth: "800px" }}>
          <ChartEmbedded symbol={symbol} mode={mode} indicators={indicators} />
        </div>
      </div>
    </section>
  );
}
