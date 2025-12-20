"use client";

import { Select, Button } from "antd";
import { COLORS, SHADOWS, BORDER_RADIUS } from "@/constants/theme";
import type { TimeRangeMode, SymbolOption } from "@/types/trading";

/**
 * StatusIndicator Component (for connection status)
 */
interface StatusIndicatorProps {
  status: "connected" | "disconnected";
}

function ConnectionStatus({ status }: StatusIndicatorProps) {
  const isConnected = status === "connected";
  
  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <label style={{ fontSize: "12px", fontWeight: 500, color: COLORS.text.primary, marginBottom: "4px" }}>
        Live Status
      </label>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "6px",
          fontSize: "14px",
          fontWeight: 600,
          color: isConnected ? COLORS.status.success : COLORS.status.error,
        }}
      >
        <span style={{ position: "relative", display: "flex", height: "8px", width: "8px" }}>
          <span
            style={{
              position: "absolute",
              animation: isConnected ? "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite" : "none",
              height: "100%",
              width: "100%",
              borderRadius: "50%",
              backgroundColor: isConnected ? COLORS.status.success : COLORS.status.error,
              opacity: 0.75,
            }}
          ></span>
          <span
            style={{
              position: "relative",
              display: "inline-flex",
              borderRadius: "50%",
              height: "8px",
              width: "8px",
              backgroundColor: isConnected ? COLORS.status.success : COLORS.status.error,
            }}
          ></span>
        </span>
        {isConnected ? "Connected" : "Disconnected"}
      </div>
    </div>
  );
}

/**
 * SymbolSelector Component
 */
interface SymbolSelectorProps {
  symbol: string;
  symbols: string[];
  onChange: (symbol: string) => void;
}

function SymbolSelector({ symbol, symbols, onChange }: SymbolSelectorProps) {
  const symbolOptions: SymbolOption[] = symbols.map((s) => ({
    value: s,
    label: s.replace("USDT", "/USDT"),
  }));

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <label style={{ fontSize: "12px", fontWeight: 500, color: COLORS.text.primary, marginBottom: "4px" }}>
        Symbol
      </label>
      <Select
        value={symbol}
        onChange={onChange}
        options={symbolOptions.length > 0 ? symbolOptions : [{ value: "BTCUSDT", label: "BTC/USDT" }]}
        style={{ width: 160 }}
        size="middle"
        className="custom-select"
      />
    </div>
  );
}

/**
 * TimeRangeSelector Component
 */
interface TimeRangeSelectorProps {
  mode: TimeRangeMode;
  onChange: (mode: TimeRangeMode) => void;
}

function TimeRangeSelector({ mode, onChange }: TimeRangeSelectorProps) {
  const ranges: { value: TimeRangeMode; label: string }[] = [
    { value: "realtime", label: "Realtime" },
    { value: "7day", label: "7 Day" },
    { value: "30day", label: "30 Day" },
    { value: "6month", label: "6 Month" },
    { value: "1year", label: "1 Year" },
  ];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        backgroundColor: COLORS.background.secondary,
        padding: "4px",
        borderRadius: BORDER_RADIUS.md,
        gap: "4px",
      }}
    >
      {ranges.map((range) => (
        <Button
          key={range.value}
          type={mode === range.value ? "primary" : "default"}
          onClick={() => onChange(range.value)}
          size="small"
          style={{
            backgroundColor: mode === range.value ? COLORS.background.hover : "transparent",
            color: COLORS.text.primary,
            border: "none",
          }}
        >
          {range.label}
        </Button>
      ))}
    </div>
  );
}

/**
 * ControlPanel Component
 * Main control panel with symbol selector, time range buttons, and indicators button
 */
interface ControlPanelProps {
  symbol: string;
  symbols: string[];
  mode: TimeRangeMode;
  onSymbolChange: (symbol: string) => void;
  onModeChange: (mode: TimeRangeMode) => void;
  onIndicatorsClick: () => void;
}

export default function ControlPanel({
  symbol,
  symbols,
  mode,
  onSymbolChange,
  onModeChange,
  onIndicatorsClick,
}: ControlPanelProps) {
  return (
    <section
      style={{
        backgroundColor: COLORS.background.secondary,
        padding: "16px",
        borderRadius: BORDER_RADIUS.lg,
        border: `1px solid ${COLORS.border.primary}`,
        boxShadow: SHADOWS.sm,
        display: "flex",
        flexDirection: "column",
        gap: "16px",
        marginBottom: "24px",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
        {/* Status and Symbol Row */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", flexWrap: "wrap" }}>
          <ConnectionStatus status="connected" />
          <SymbolSelector symbol={symbol} symbols={symbols} onChange={onSymbolChange} />
        </div>

        {/* Time Range Selector */}
        <TimeRangeSelector mode={mode} onChange={onModeChange} />

        {/* Technical Indicators Button */}
        <div style={{ display: "flex", gap: "8px" }}>
          <Button
            onClick={onIndicatorsClick}
            style={{
              backgroundColor: COLORS.status.info,
              color: COLORS.text.primary,
              border: "none",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            size="middle"
          >
            <span>📈</span>
            Technical Indicators
          </Button>
        </div>
      </div>
    </section>
  );
}
