from typing import List, Optional
from pydantic import BaseModel, Field


class Candle(BaseModel):
    openTime: int = Field(..., description="Open time in ms")
    closeTime: Optional[int] = Field(None, description="Close time in ms")
    open: float
    high: float
    low: float
    close: float
    volume: float
    trades: Optional[int] = None

    def as_chart_point(self) -> dict:
        return {
            "openTime": self.openTime,
            "y": [self.open, self.high, self.low, self.close],
            "volume": self.volume,
        }


class OHLCResponse(BaseModel):
    symbol: str
    interval: str
    count: int
    candles: List[dict]


class LatestKline(BaseModel):
    symbol: str
    interval: str
    openTime: int
    closeTime: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quoteVolume: float
    trades: int
    isClosed: bool = Field(alias="x")

    class Config:
        populate_by_name = True


class OrderBookEntry(BaseModel):
    price: float = Field(..., description="Price level")
    quantity: float = Field(..., description="Quantity at this price level")
    total: Optional[float] = Field(None, description="Cumulative total (calculated)")


class OrderBook(BaseModel):
    symbol: str
    lastUpdateId: Optional[int] = None
    bids: List[OrderBookEntry] = Field(..., description="Buy orders (sorted descending by price)")
    asks: List[OrderBookEntry] = Field(..., description="Sell orders (sorted ascending by price)")
    timestamp: Optional[int] = Field(None, description="Timestamp in milliseconds")


class OrderBookResponse(BaseModel):
    symbol: str
    bids: List[OrderBookEntry]
    asks: List[OrderBookEntry]
    timestamp: Optional[int] = None


class Trade(BaseModel):
    symbol: str
    price: float
    quantity: float
    time: int = Field(..., description="Trade time in milliseconds")
    isBuyerMaker: bool = Field(..., description="True if buyer is maker (sell order)")
    tradeId: Optional[int] = None


class TradesResponse(BaseModel):
    symbol: str
    count: int
    trades: List[Trade]


class Prediction(BaseModel):
    symbol: str
    current_price: float
    predicted_price: float
    predicted_change: float = Field(..., description="Predicted price change in %")
    direction: str = Field(..., description="UP or DOWN")
    prediction_time: str = Field(..., description="When prediction was made")
    target_time: str = Field(..., description="Target prediction time (5 min ahead)")
    confidence_score: float = Field(..., description="Absolute value of predicted change")


class PredictionResponse(BaseModel):
    symbol: str
    prediction: Prediction


class PredictionsListResponse(BaseModel):
    count: int
    predictions: List[Prediction]


class PredictionHistory(BaseModel):
    symbol: str
    prediction_time: str
    predicted_price: float
    predicted_change: float
    actual_price: Optional[float] = None
    actual_change: Optional[float] = None
    accuracy: Optional[float] = None


class PredictionHistoryResponse(BaseModel):
    symbol: str
    count: int
    history: List[PredictionHistory]

