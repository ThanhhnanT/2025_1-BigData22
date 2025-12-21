/**
 * PredictionSection Component
 * 
 * Displays AI price prediction for a symbol
 */

import { useState, useEffect } from "react";
import { Typography } from "antd";
import axios from "axios";
import { COLORS, SHADOWS, BORDER_RADIUS } from "@/constants/theme";
import type { Prediction } from "@/types/trading";

const { Title } = Typography;

interface PredictionSectionProps {
  symbol: string;
  wsBase: string;
}

export default function PredictionSection({ symbol, wsBase }: PredictionSectionProps) {
  const [prediction, setPrediction] = useState<Prediction | null>(null);
  const [isLoadingPrediction, setIsLoadingPrediction] = useState<boolean>(false);

  // ============================================================================
  // PREDICTION FETCHING - Poll every 1 minute
  // ============================================================================
  useEffect(() => {
    const API_BASE = wsBase.replace(/^ws/, "http");
    let isMounted = true;
    let pollInterval: NodeJS.Timeout | null = null;
    
    const fetchPrediction = async () => {
      if (!isMounted) return;
      
      try {
        setIsLoadingPrediction(true);
        const response = await axios.get(`${API_BASE}/prediction/${symbol}`);
        if (response.data && response.data.prediction && isMounted) {
          setPrediction(response.data.prediction);
        }
      } catch (error: any) {
        // If 404 or no data, keep existing prediction (don't clear it)
        if (error.response?.status === 404) {
          console.log(`[Prediction] No prediction found for ${symbol}, keeping existing data`);
        } else {
          console.error(`[Prediction] Error fetching prediction for ${symbol}:`, error);
        }
      } finally {
        if (isMounted) {
          setIsLoadingPrediction(false);
        }
      }
    };
    
    // Fetch immediately when symbol changes
    fetchPrediction();
    
    // Poll every 1 minute (60000ms)
    pollInterval = setInterval(() => {
      if (isMounted) {
        fetchPrediction();
      }
    }, 60000);
    
    return () => {
      isMounted = false;
      if (pollInterval) {
        clearInterval(pollInterval);
      }
    };
  }, [symbol, wsBase]);

  // ============================================================================
  // UTILITY FUNCTIONS FOR PREDICTION
  // ============================================================================
  const formatPredictionTime = (timeStr: string): string => {
    try {
      const date = new Date(timeStr);
      return date.toLocaleTimeString("en-US", {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return timeStr;
    }
  };

  const getSymbolDisplayName = (symbol: string): string => {
    // Convert BTCUSDT to BTC/USDT
    if (symbol.endsWith("USDT")) {
      return `${symbol.slice(0, -4)}/USDT`;
    }
    return symbol;
  };

  // ============================================================================
  // RENDER
  // ============================================================================
  return (
    <section style={{
      backgroundColor: COLORS.background.secondary,
      borderRadius: BORDER_RADIUS.lg,
      border: `1px solid ${COLORS.border.primary}`,
      boxShadow: SHADOWS.md,
      overflow: 'hidden',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
    }}>
      <div style={{
        padding: '8px 12px',
        borderBottom: `1px solid ${COLORS.border.primary}`,
        backgroundColor: 'rgba(31, 41, 55, 0.5)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        flexShrink: 0,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ 
            fontSize: '18px', 
            color: '#a855f7' // purple-500
          }}>🧠</span>
          <Title level={5} style={{ margin: 0, color: COLORS.text.primary, fontSize: '14px' }}>
            AI Price Prediction
          </Title>
        </div>
        <span style={{
          fontSize: '10px',
          fontFamily: 'monospace',
          backgroundColor: 'rgba(168, 85, 247, 0.1)',
          color: '#c084fc', // purple-300
          padding: '2px 6px',
          borderRadius: BORDER_RADIUS.sm,
          border: '1px solid rgba(168, 85, 247, 0.2)',
        }}>
          BETA
        </span>
      </div>

      <div style={{ padding: '12px 12px 8px 12px', display: 'flex', flexDirection: 'column', gap: '10px' }}>
        {isLoadingPrediction && !prediction ? (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            color: COLORS.text.secondary,
            fontSize: '14px',
          }}>
            Loading prediction...
          </div>
        ) : prediction ? (
          <>
            {/* Symbol and Current Price */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <div style={{
                  width: '32px',
                  height: '32px',
                  borderRadius: '50%',
                  backgroundColor: '#3b82f6', // blue-500
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  color: 'white',
                  fontSize: '12px',
                  fontWeight: 'bold',
                  boxShadow: SHADOWS.sm,
                }}>
                  {symbol.slice(0, 1)}
                </div>
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 'bold', color: COLORS.text.primary }}>
                    {getSymbolDisplayName(prediction.symbol)}
                  </div>
                  <div style={{ fontSize: '12px', color: COLORS.text.secondary }}>
                    {symbol === 'BTCUSDT' ? 'Bitcoin' : symbol === 'ETHUSDT' ? 'Ethereum' : 'Cryptocurrency'}
                  </div>
                </div>
              </div>
              <div style={{ textAlign: 'right' }}>
                <div style={{ fontSize: '12px', color: COLORS.text.secondary, marginBottom: '4px' }}>Current</div>
                <div style={{ fontSize: '14px', fontFamily: 'monospace', fontWeight: 'medium', color: COLORS.text.primary }}>
                  ${prediction.current_price.toFixed(4)}
                </div>
              </div>
            </div>

            {/* Timeline */}
            <div style={{ position: 'relative', padding: '10px 0' }}>
              {/* Gradient line */}
              <div style={{
                position: 'absolute',
                top: '50%',
                left: 0,
                right: 0,
                height: '2px',
                background: `linear-gradient(to right, ${COLORS.border.primary}, ${COLORS.border.secondary || COLORS.border.primary}, ${COLORS.border.primary})`,
                zIndex: 0,
              }} />
              
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '8px', position: 'relative', zIndex: 1 }}>
                {/* Current time */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                  <div style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    backgroundColor: COLORS.text.secondary,
                    border: `4px solid ${COLORS.background.secondary}`,
                  }} />
                  <span style={{ fontSize: '10px', fontFamily: 'monospace', color: COLORS.text.secondary, marginTop: '4px' }}>
                    {formatPredictionTime(prediction.prediction_time)}
                  </span>
                </div>

                {/* Status badge */}
                <div style={{
                  backgroundColor: COLORS.background.secondary,
                  border: `1px solid ${COLORS.border.primary}`,
                  borderRadius: '9999px',
                  padding: '4px 12px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  zIndex: 10,
                  boxShadow: SHADOWS.sm,
                }}>
                  <span style={{
                    width: '8px',
                    height: '8px',
                    borderRadius: '50%',
                    backgroundColor: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                    animation: 'pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite',
                  }} />
                  <span style={{
                    fontSize: '12px',
                    fontWeight: 'semibold',
                    color: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                    letterSpacing: '0.05em',
                  }}>
                    {prediction.direction === 'UP' ? 'BULLISH' : 'BEARISH'}
                  </span>
                </div>

                {/* Target time */}
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}>
                  <div style={{
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    backgroundColor: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                    border: `4px solid ${COLORS.background.secondary}`,
                    boxShadow: `0 0 8px ${prediction.direction === 'UP' ? 'rgba(16, 185, 129, 0.5)' : 'rgba(239, 68, 68, 0.5)'}`,
                  }} />
                  <span style={{
                    fontSize: '10px',
                    fontFamily: 'monospace',
                    color: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                    marginTop: '4px',
                    fontWeight: 'bold',
                  }}>
                    {formatPredictionTime(prediction.target_time)}
                  </span>
                </div>
              </div>
            </div>

            {/* Target Price and Expected Change Grid */}
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
              <div style={{
                backgroundColor: 'rgba(55, 65, 81, 0.4)',
                borderRadius: BORDER_RADIUS.md,
                padding: '8px',
                border: `1px solid ${COLORS.border.primary}`,
              }}>
                <div style={{ fontSize: '10px', color: COLORS.text.secondary, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                  Target Price
                </div>
                <div style={{ fontSize: '16px', fontFamily: 'monospace', fontWeight: 'bold', color: COLORS.text.primary, display: 'flex', alignItems: 'end', gap: '4px' }}>
                  ${prediction.predicted_price.toFixed(4)}
                  <span style={{ fontSize: '12px', color: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error }}>
                    {prediction.direction === 'UP' ? '📈' : '📉'}
                  </span>
                </div>
              </div>
              <div style={{
                backgroundColor: 'rgba(55, 65, 81, 0.4)',
                borderRadius: BORDER_RADIUS.md,
                padding: '8px',
                border: `1px solid ${COLORS.border.primary}`,
              }}>
                <div style={{ fontSize: '10px', color: COLORS.text.secondary, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                  Exp. Change
                </div>
                <div style={{
                  fontSize: '16px',
                  fontFamily: 'monospace',
                  fontWeight: 'bold',
                  color: prediction.direction === 'UP' ? COLORS.status.success : COLORS.status.error,
                }}>
                  {prediction.predicted_change >= 0 ? '+' : ''}{prediction.predicted_change.toFixed(2)}%
                </div>
              </div>
            </div>

            {/* Confidence Score */}
            <div style={{ fontSize: '10px', textAlign: 'center', color: COLORS.text.secondary, marginTop: '2px', marginBottom: 0 }}>
              Prediction confidence: <span style={{ color: COLORS.text.primary, fontWeight: 'medium' }}>
                {prediction.confidence_score.toFixed(1)}%
              </span> based on ML model
            </div>
          </>
        ) : (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            padding: '20px',
            color: COLORS.text.secondary,
            fontSize: '14px',
          }}>
            No prediction available yet
          </div>
        )}
      </div>
    </section>
  );
}

