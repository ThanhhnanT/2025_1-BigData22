"use client";

import { COLORS } from "@/constants/theme";

/**
 * DashboardFooter Component
 * Footer with status message and last updated time
 */
interface DashboardFooterProps {
  currentTime: string;
}

export default function DashboardFooter({ currentTime }: DashboardFooterProps) {
  return (
    <footer
      style={{
        fontSize: "12px",
        color: COLORS.text.primary,
        paddingTop: "8px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
      }}
    >
      <p style={{ margin: 0, color: COLORS.text.primary }}>
        Historical cryptocurrency data powered by MongoDB
      </p>
      <p style={{ margin: 0, color: COLORS.text.primary }}>
        Last updated: <span style={{ color: COLORS.text.primary }}>{currentTime || "--:--:--"}</span>
      </p>
    </footer>
  );
}
