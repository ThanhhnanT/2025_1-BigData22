"use client";

import { Modal, Switch, ColorPicker, Divider, Typography, Space } from "antd";
import type { Color } from "antd/es/color-picker";

const { Title, Text } = Typography;

export interface IndicatorConfig {
  enabled: boolean;
  color: string;
  label: string;
  period?: number;
}

export interface TechnicalIndicatorsConfig {
  ma7: IndicatorConfig;
  ma25: IndicatorConfig;
  ma99: IndicatorConfig;
  ema12: IndicatorConfig;
  ema26: IndicatorConfig;
  ema50: IndicatorConfig;
  bollinger: IndicatorConfig;
}

interface TechnicalIndicatorsModalProps {
  open: boolean;
  onClose: () => void;
  indicators: TechnicalIndicatorsConfig;
  onChange: (indicators: TechnicalIndicatorsConfig) => void;
}

export default function TechnicalIndicatorsModal({
  open,
  onClose,
  indicators,
  onChange,
}: TechnicalIndicatorsModalProps) {
  // Use indicators directly as the source of truth instead of local state that can get out of sync
  const localIndicators = indicators;

  const handleToggle = (key: keyof TechnicalIndicatorsConfig) => {
    const updated = {
      ...localIndicators,
      [key]: {
        ...localIndicators[key],
        enabled: !localIndicators[key].enabled,
      },
    };
    onChange(updated);
  };

  const handleColorChange = (key: keyof TechnicalIndicatorsConfig, color: Color) => {
    const updated = {
      ...localIndicators,
      [key]: {
        ...localIndicators[key],
        color: typeof color === "string" ? color : color.toHexString(),
      },
    };
    onChange(updated);
  };

  const renderIndicatorRow = (
    key: keyof TechnicalIndicatorsConfig,
    label: string,
    description?: string
  ) => {
    const indicator = localIndicators[key];
    return (
      <div
        key={key}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 0",
          borderBottom: "1px solid #374151",
        }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Text style={{ color: "#fff", fontWeight: 500 }}>{label}</Text>
            {indicator.period && (
              <Text style={{ color: "#9ca3af", fontSize: "12px" }}>
                (Period: {indicator.period})
              </Text>
            )}
          </div>
          {description && (
            <Text style={{ color: "#9ca3af", fontSize: "12px", display: "block", marginTop: "4px" }}>
              {description}
            </Text>
          )}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <ColorPicker
            value={indicator.color}
            onChange={(color) => handleColorChange(key, color)}
            size="small"
            disabled={!indicator.enabled}
            style={{ opacity: indicator.enabled ? 1 : 0.5 }}
          />
          <Switch
            checked={indicator.enabled}
            onChange={() => handleToggle(key)}
            style={{
              backgroundColor: indicator.enabled ? "#3b82f6" : "#4b5563",
            }}
          />
        </div>
      </div>
    );
  };

  const mainIndicatorsTab = (
    <div style={{ padding: "8px 0" }}>
      {/* Moving Averages */}
      <Space orientation="vertical" style={{ width: "100%", marginBottom: "16px" }}>
        <Title level={5} style={{ color: "#3b82f6", margin: "8px 0" }}>
          Moving Averages (MA)
        </Title>
        {renderIndicatorRow(
          "ma7",
          "MA 7",
          "7-period Simple Moving Average for short-term trends"
        )}
        {renderIndicatorRow(
          "ma25",
          "MA 25",
          "25-period Simple Moving Average for medium-term trends"
        )}
        {renderIndicatorRow(
          "ma99",
          "MA 99",
          "99-period Simple Moving Average for long-term trends"
        )}
      </Space>

      <Divider style={{ borderColor: "#374151", margin: "16px 0" }} />

      {/* Exponential Moving Averages */}
      <Space orientation="vertical" style={{ width: "100%", marginBottom: "16px" }}>
        <Title level={5} style={{ color: "#10b981", margin: "8px 0" }}>
          Exponential Moving Averages (EMA)
        </Title>
        {renderIndicatorRow(
          "ema12",
          "EMA 12",
          "12-period Exponential Moving Average for fast response"
        )}
        {renderIndicatorRow(
          "ema26",
          "EMA 26",
          "26-period Exponential Moving Average for slower response"
        )}
        {renderIndicatorRow(
          "ema50",
          "EMA 50",
          "50-period Exponential Moving Average for trend confirmation"
        )}
      </Space>

      <Divider style={{ borderColor: "#374151", margin: "16px 0" }} />

      {/* Bollinger Bands */}
      <Space orientation="vertical" style={{ width: "100%", marginBottom: "16px" }}>
        <Title level={5} style={{ color: "#ec4899", margin: "8px 0" }}>
          Volatility Indicators
        </Title>
        {renderIndicatorRow(
          "bollinger",
          "Bollinger Bands",
          "Volatility bands based on standard deviation"
        )}
      </Space>
    </div>
  );



  return (
    <Modal
      title={
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span>📈</span>
          <span>Technical Indicators</span>
        </div>
      }
      open={open}
      onCancel={onClose}
      footer={null}
      width={600}
      styles={{
        body: {
          backgroundColor: "#1f2937",
          color: "#fff",
          maxHeight: "70vh",
          overflowY: "auto",
        },
        header: {
          backgroundColor: "#1f2937",
          color: "#fff",
          borderBottom: "1px solid #374151",
        },
      }}
    >
      {mainIndicatorsTab}
    </Modal>
  );
}
