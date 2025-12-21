"""
Technical Indicators Calculation Service
Calculates SMA, EMA, and Bollinger Bands for OHLC data
"""
import numpy as np
import pandas as pd
from typing import List, Dict, Optional, Any


def calculate_sma(candles: List[Dict[str, Any]], period: int) -> List[Dict[str, Any]]:
    """
    Calculate Simple Moving Average
    
    Args:
        candles: List of candle dicts with 'openTime' and 'close' fields
        period: Period for SMA calculation
    
    Returns:
        List of dicts with 'x' (timestamp) and 'y' (SMA value or None)
    """
    if not candles or len(candles) < period:
        return [{"x": c.get("openTime", 0), "y": None} for c in candles]
    
    # Extract close prices
    closes = [c.get("close", 0) for c in candles]
    timestamps = [c.get("openTime", 0) for c in candles]
    
    # Calculate SMA using pandas for efficiency
    df = pd.DataFrame({"close": closes, "timestamp": timestamps})
    sma = df["close"].rolling(window=period, min_periods=period).mean()
    
    result = []
    for i, (ts, value) in enumerate(zip(timestamps, sma)):
        result.append({
            "x": ts,
            "y": float(value) if pd.notna(value) else None
        })
    
    return result


def calculate_ema(candles: List[Dict[str, Any]], period: int) -> List[Dict[str, Any]]:
    """
    Calculate Exponential Moving Average
    
    Args:
        candles: List of candle dicts with 'openTime' and 'close' fields
        period: Period for EMA calculation
    
    Returns:
        List of dicts with 'x' (timestamp) and 'y' (EMA value or None)
    """
    if not candles or len(candles) < period:
        return [{"x": c.get("openTime", 0), "y": None} for c in candles]
    
    # Extract close prices
    closes = [c.get("close", 0) for c in candles]
    timestamps = [c.get("openTime", 0) for c in candles]
    
    # Calculate EMA using pandas
    df = pd.DataFrame({"close": closes, "timestamp": timestamps})
    ema = df["close"].ewm(span=period, adjust=False).mean()
    
    result = []
    for i, (ts, value) in enumerate(zip(timestamps, ema)):
        # EMA needs at least 'period' values to be valid
        if i < period - 1:
            result.append({"x": ts, "y": None})
        else:
            result.append({
                "x": ts,
                "y": float(value) if pd.notna(value) else None
            })
    
    return result


def calculate_bollinger_bands(
    candles: List[Dict[str, Any]], 
    period: int = 20, 
    std_dev: float = 2.0
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Calculate Bollinger Bands (Upper, Middle, Lower)
    
    Args:
        candles: List of candle dicts with 'openTime' and 'close' fields
        period: Period for Bollinger Bands calculation (default 20)
        std_dev: Standard deviation multiplier (default 2.0)
    
    Returns:
        Dict with 'upper', 'middle', 'lower' keys, each containing list of dicts
    """
    if not candles or len(candles) < period:
        empty = [{"x": c.get("openTime", 0), "y": None} for c in candles]
        return {"upper": empty, "middle": empty, "lower": empty}
    
    # Extract close prices
    closes = [c.get("close", 0) for c in candles]
    timestamps = [c.get("openTime", 0) for c in candles]
    
    # Calculate using pandas
    df = pd.DataFrame({"close": closes, "timestamp": timestamps})
    
    # Middle band is SMA
    middle = df["close"].rolling(window=period, min_periods=period).mean()
    
    # Standard deviation
    std = df["close"].rolling(window=period, min_periods=period).std()
    
    # Upper and lower bands
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    result_upper = []
    result_middle = []
    result_lower = []
    
    for i, ts in enumerate(timestamps):
        if i < period - 1:
            result_upper.append({"x": ts, "y": None})
            result_middle.append({"x": ts, "y": None})
            result_lower.append({"x": ts, "y": None})
        else:
            result_upper.append({
                "x": ts,
                "y": float(upper.iloc[i]) if pd.notna(upper.iloc[i]) else None
            })
            result_middle.append({
                "x": ts,
                "y": float(middle.iloc[i]) if pd.notna(middle.iloc[i]) else None
            })
            result_lower.append({
                "x": ts,
                "y": float(lower.iloc[i]) if pd.notna(lower.iloc[i]) else None
            })
    
    return {
        "upper": result_upper,
        "middle": result_middle,
        "lower": result_lower
    }


def calculate_indicators(
    candles: List[Dict[str, Any]],
    indicator_types: List[str]
) -> Dict[str, Any]:
    """
    Calculate multiple indicators at once
    
    Args:
        candles: List of candle dicts with OHLC data
        indicator_types: List of indicator strings like ['ma7', 'ma25', 'ema12', 'bollinger']
    
    Returns:
        Dict with indicator names as keys and calculated values as values
    """
    result = {}
    
    for ind_type in indicator_types:
        if ind_type.startswith("ma"):
            # Extract period from indicator name (e.g., "ma7" -> 7)
            try:
                period = int(ind_type[2:])
                result[ind_type] = calculate_sma(candles, period)
            except ValueError:
                continue
        
        elif ind_type.startswith("ema"):
            # Extract period from indicator name (e.g., "ema12" -> 12)
            try:
                period = int(ind_type[3:])
                result[ind_type] = calculate_ema(candles, period)
            except ValueError:
                continue
        
        elif ind_type == "bollinger":
            # Default Bollinger Bands (period=20, std_dev=2.0)
            result[ind_type] = calculate_bollinger_bands(candles, period=20, std_dev=2.0)
    
    return result

