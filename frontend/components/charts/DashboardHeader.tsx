"use client";

import { Typography } from "antd";
import { COLORS, SHADOWS } from "@/constants/theme";

const { Title } = Typography;

/**
 * StatusIndicator Component
 * Displays a colored dot with pulse animation and status text
 */
interface StatusIndicatorProps {
  status: "online" | "offline" | "connecting";
  label: string;
  size?: "sm" | "md";
}

function StatusIndicator({ status, label, size = "md" }: StatusIndicatorProps) {
  const colors = {
    online: COLORS.status.success,
    offline: COLORS.status.error,
    connecting: COLORS.status.warning,
  };

  const dotSize = size === "sm" ? "8px" : "12px";
  const color = colors[status];

  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", color: COLORS.text.primary }}>
      <span style={{ position: "relative", display: "flex", height: dotSize, width: dotSize }}>
        <span
          style={{
            position: "absolute",
            animation: status === "online" ? "ping 1s cubic-bezier(0, 0, 0.2, 1) infinite" : "none",
            height: "100%",
            width: "100%",
            borderRadius: "50%",
            backgroundColor: color,
            opacity: 0.75,
          }}
        ></span>
        <span
          style={{
            position: "relative",
            display: "inline-flex",
            borderRadius: "50%",
            height: dotSize,
            width: dotSize,
            backgroundColor: color,
          }}
        ></span>
      </span>
      <span>{label}</span>
    </div>
  );
}

/**
 * DashboardHeader Component
 * Main header with branding and system status
 */
export default function DashboardHeader() {
  return (
    <header
      style={{
        backgroundColor: COLORS.background.secondary,
        borderBottom: `1px solid ${COLORS.border.primary}`,
        padding: "16px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        boxShadow: SHADOWS.sm,
      }}
    >
      {/* Logo and Title */}
      <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
        <div
          style={{
            height: "12px",
            width: "12px",
            borderRadius: "50%",
            backgroundColor: COLORS.status.info,
            animation: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
          }}
        ></div>
        <Title level={4} style={{ margin: 0, color: COLORS.text.primary, display: "flex", alignItems: "center", gap: "8px" }}>
          <span style={{ color: COLORS.status.info }}>📊</span>
          Crypto Dashboard
        </Title>
      </div>

      {/* System Status */}
      <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
        <StatusIndicator status="online" label="System Operational" size="sm" />
      </div>
    </header>
  );
}
