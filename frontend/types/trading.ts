/**
 * Shared types for trading dashboard components
 */

export type TimeRangeMode = "realtime" | "7day" | "30day" | "6month" | "1year";

export interface SymbolOption {
  value: string;
  label: string;
}

// =============================================================================
// TECHNICAL INDICATORS TYPES
// =============================================================================

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

// =============================================================================
// ORDER BOOK & TRADES TYPES (Currently disabled for MongoDB-only mode)
// =============================================================================

export interface OrderBookEntry {
  price: number;
  quantity: number;
  total: number;
}

export interface Trade {
  symbol: string;
  price: number;
  quantity: number;
  time: number;
  isBuyerMaker: boolean;
  tradeId?: number;
}

export interface OrderBookMessage {
  type: "initial" | "update";
  symbol: string;
  bids: OrderBookEntry[];
  asks: OrderBookEntry[];
  timestamp?: number;
}

export interface TradesMessage {
  type: "initial" | "realtime";
  symbol: string;
  trades?: Trade[];
  trade?: Trade;
}

// =============================================================================
// PREDICTION TYPES
// =============================================================================

export interface Prediction {
  symbol: string;
  current_price: number;
  predicted_price: number;
  predicted_change: number; // Percentage change
  direction: "UP" | "DOWN";
  prediction_time: string; // ISO timestamp
  target_time: string; // ISO timestamp (next 5 minutes)
  confidence_score: number; // Absolute value of predicted_change
}

export interface PredictionResponse {
  symbol: string;
  prediction: Prediction;
}

// =============================================================================
// INDICATOR API TYPES
// =============================================================================

export interface IndicatorDataPoint {
  x: number; // timestamp
  y: number | null; // indicator value
}

export interface BollingerBandsData {
  upper: IndicatorDataPoint[];
  middle: IndicatorDataPoint[];
  lower: IndicatorDataPoint[];
}

export interface IndicatorsResponse {
  symbol: string;
  interval: string;
  indicators: {
    [key: string]: IndicatorDataPoint[] | BollingerBandsData;
  };
  candle_count?: number;
  count?: number;
  last_timestamp?: number;
  from_cache?: boolean;
}
