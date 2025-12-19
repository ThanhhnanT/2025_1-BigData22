import asyncio
import json
from contextlib import asynccontextmanager
from typing import Optional

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings
from .schemas import (
    Candle, LatestKline, OHLCResponse,
    OrderBookResponse, OrderBookEntry, TradesResponse, Trade
)
from .kafka_manager import SharedKafkaManager


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_client = AsyncIOMotorClient(settings.mongo_uri)
    app.state.mongo_client = mongo_client
    app.state.mongo_db = mongo_client[settings.mongo_db]

    redis_client = redis.Redis(
        host=settings.redis_host,
        port=settings.redis_port,
        db=settings.redis_db,
        password=settings.redis_password,
        decode_responses=True,
    )
    app.state.redis = redis_client

    kafka_manager = SharedKafkaManager(kafka_bootstrap=settings.kafka_bootstrap)
    app.state.kafka_manager = kafka_manager

    yield


    await kafka_manager.shutdown()
    await redis_client.aclose()
    mongo_client.close()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_mongo(request: Request):
    return request.app.state.mongo_db


async def get_redis(request: Request):
    return request.app.state.redis


@app.get("/")
async def root():
    return {"message": "Hello World"}

@app.get("/health")
async def health():
    return {"status": "ok", "service": settings.app_name}


@app.get("/symbols")
async def list_symbols():
    return {"symbols": settings.symbols}

# get from mongodb
@app.get("/ohlc", response_model=OHLCResponse)
async def get_ohlc(
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    interval: Optional[str] = Query(None, description="Interval (matches stored docs)"),
    collection: Optional[str] = Query(None, description="MongoDB collection name (e.g. kline_5m, kline_1h)"),
    limit: int = Query(200, ge=1, le=2000),
    start: Optional[int] = Query(None, description="Start openTime (ms)"),
    end: Optional[int] = Query(None, description="End openTime (ms)"),
    mongo=Depends(get_mongo),
):
    # Determine collection to use
    if collection:
        col_name = collection
    else:
        col_name = settings.mongo_collection_ohlc
    
    if not interval:
        if collection:
            # Map collection names to intervals
            collection_to_interval = {
                "5m_kline": "5m",
                "1h_kline": "1h",
                "4h_kline": "4h",
                "1d_kline": "1d",
            }
            interval = collection_to_interval.get(collection, "5m")
        else:
            interval = "5m"
    
    col = mongo[col_name]
    query = {"symbol": symbol, "interval": interval}
    if start is not None and end is not None:
        query["openTime"] = {"$gte": start, "$lte": end}
    elif start is not None:
        query["openTime"] = {"$gte": start}
    elif end is not None:
        query["openTime"] = {"$lte": end}

    cursor = (
        col.find(query)
        .sort("openTime", -1)
        .limit(limit)
    )
    docs = await cursor.to_list(length=limit)
    candles = [Candle(**doc).as_chart_point() for doc in reversed(docs)]

    return OHLCResponse(symbol=symbol, interval=interval, count=len(candles), candles=candles)


@app.get("/latest", response_model=LatestKline)
async def latest_kline(
    symbol: str = Query("BTCUSDT"),
    redis_client=Depends(get_redis),
):
    key = f"crypto:{symbol}:1m:latest"
    raw = await redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail="No data for symbol")
    data = json.loads(raw)
    return LatestKline(**data)


@app.get("/ohlc/realtime", response_model=OHLCResponse)
async def get_ohlc_realtime(
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    limit: int = Query(200, ge=1, le=2000, description="Number of candles to return"),
    start: Optional[int] = Query(None, description="Start openTime (ms) - load candles before this time"),
    end: Optional[int] = Query(None, description="End openTime (ms)"),
    redis_client=Depends(get_redis),
):
    """
    Get OHLC data from Redis for realtime mode (1m interval).
    Used for lazy-loading historical data when user scrolls/pans backward.
    """
    index_key = f"crypto:{symbol}:1m:index"
    
    try:
        # Get timestamps from sorted set
        if start is not None:
            # Load candles before start time (for backward scrolling)
            # Get all candles before start, then take the N most recent ones
            all_before = await redis_client.zrangebyscore(
                index_key,
                "-inf",
                start - 1,
                withscores=True
            )
            # Sort by score (timestamp) descending to get most recent first
            all_before.sort(key=lambda x: x[1], reverse=True)
            # Take the N most recent candles before start
            timestamps = all_before[:limit]
            # Reverse to get oldest first (for proper chronological order)
            timestamps.reverse()
        elif end is not None:
            # Load candles up to end time
            timestamps = await redis_client.zrangebyscore(
                index_key,
                "-inf",
                end,
                withscores=True,
                start=0,
                num=limit
            )
            timestamps = sorted(timestamps, key=lambda x: x[1])  # Sort ascending
        else:
            # Load latest N candles
            timestamps = await redis_client.zrange(
                index_key,
                -limit,
                -1,
                withscores=True
            )
        
        candles = []
        for ts_str, score in timestamps:
            key = f"crypto:{symbol}:1m:{ts_str}"
            raw = await redis_client.get(key)
            if raw:
                data = json.loads(raw)
                # Only include closed candles
                if data.get("x", False):
                    candles.append({
                        "openTime": data["openTime"],
                        "y": [data["open"], data["high"], data["low"], data["close"]],
                        "volume": data["volume"],
                    })
        
        # Sort by openTime ascending
        candles.sort(key=lambda x: x["openTime"])
        
        return OHLCResponse(
            symbol=symbol,
            interval="1m",
            count=len(candles),
            candles=candles
        )
    except Exception as e:
        print(f"Error loading realtime OHLC from Redis: {e}")
        raise HTTPException(status_code=500, detail=f"Error loading data: {str(e)}")


@app.get("/orderbook", response_model=OrderBookResponse)
async def get_orderbook(
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    limit: int = Query(20, ge=1, le=100, description="Number of levels per side"),
    redis_client=Depends(get_redis),
):
    """Get Order Book snapshot from Redis"""
    key = f"orderbook:{symbol}:latest"
    raw = await redis_client.get(key)
    if not raw:
        raise HTTPException(status_code=404, detail=f"No order book data for {symbol}")
    
    data = json.loads(raw)
    
    # Process bids and asks, calculate totals, and limit results
    bids_raw = data.get("bids", [])
    asks_raw = data.get("asks", [])
    
    # Calculate cumulative totals for bids (descending) and asks (ascending)
    bids = []
    bids_total = 0.0
    for i, (price, qty) in enumerate(bids_raw[:limit]):
        bids_total += qty * price
        bids.append(OrderBookEntry(
            price=price,
            quantity=qty,
            total=bids_total
        ))
    
    asks = []
    asks_total = 0.0
    for i, (price, qty) in enumerate(asks_raw[:limit]):
        asks_total += qty * price
        asks.append(OrderBookEntry(
            price=price,
            quantity=qty,
            total=asks_total
        ))
    
    return OrderBookResponse(
        symbol=symbol,
        bids=bids,
        asks=asks,
        timestamp=data.get("timestamp")
    )


@app.get("/trades", response_model=TradesResponse)
async def get_trades(
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    limit: int = Query(50, ge=1, le=100, description="Number of trades to return"),
    redis_client=Depends(get_redis),
):
    """Get Market Trades from Redis"""
    key = f"trades:{symbol}:list"
    
    # Get trades from sorted set (sorted by time, descending)
    trades_raw = await redis_client.zrange(key, -limit, -1, withscores=False)
    
    if not trades_raw:
        raise HTTPException(status_code=404, detail=f"No trades data for {symbol}")
    
    # Parse and reverse (oldest first)
    trades = []
    for trade_json in reversed(trades_raw):
        trade_data = json.loads(trade_json)
        trades.append(Trade(
            symbol=trade_data.get("symbol", symbol),
            price=trade_data.get("price", 0),
            quantity=trade_data.get("quantity", 0),
            time=trade_data.get("time", 0),
            isBuyerMaker=trade_data.get("isBuyerMaker", False),
            tradeId=trade_data.get("tradeId")
        ))
    
    return TradesResponse(
        symbol=symbol,
        count=len(trades),
        trades=trades
    )


@app.websocket("/ws/kline")
async def ws_kline(
    websocket: WebSocket,
    symbol: str,
    limit: int = Query(100, ge=1, le=500, description="Số candle từ Redis khi connect"),
):
    await websocket.accept()
    redis_client = websocket.app.state.redis
    kafka_manager = websocket.app.state.kafka_manager
    
    # 1. Gửi dữ liệu hiện tại từ Redis trước (để có context)
    try:
        index_key = f"crypto:{symbol}:1m:index"
        # Lấy N candle gần nhất từ Redis (sorted set)
        timestamps = await redis_client.zrange(index_key, -limit, -1)
        
        candles_from_redis = []
        for ts in timestamps:
            key = f"crypto:{symbol}:1m:{ts}"
            raw = await redis_client.get(key)
            if raw:
                data = json.loads(raw)
                # Chỉ gửi candle đã đóng (x=true) từ Redis
                if data.get("x", False):
                    candles_from_redis.append(data)
        
        # Sắp xếp theo openTime
        candles_from_redis.sort(key=lambda x: x.get("openTime", 0))
        
        # Gửi batch candles từ Redis
        if candles_from_redis:
            await websocket.send_json({
                "type": "initial",
                "candles": candles_from_redis
            })
        
        # Gửi latest candle (có thể đang mở x=false)
        latest_key = f"crypto:{symbol}:1m:latest"
        latest_raw = await redis_client.get(latest_key)
        if latest_raw:
            latest_data = json.loads(latest_raw)
            await websocket.send_json({
                "type": "latest",
                "candle": latest_data
            })
    except Exception as e:
        print(f"Error loading from Redis: {e}")
    
    # 2. Subscribe to shared Kafka consumer
    try:
        await kafka_manager.subscribe(settings.kafka_topic, symbol, websocket)
        
        # Keep connection alive and monitor for disconnects
        try:
            while True:
                # Try to receive with timeout to detect disconnects
                try:
                    await asyncio.wait_for(websocket.receive(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Timeout is OK, connection still alive
                    continue
                except (WebSocketDisconnect, RuntimeError):
                    # Connection closed
                    break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"Error in kline websocket: {e}")
    finally:
        # Unsubscribe when connection closes
        await kafka_manager.unsubscribe(settings.kafka_topic, symbol, websocket)


@app.websocket("/ws/orderbook")
async def ws_orderbook(
    websocket: WebSocket,
    symbol: str,
):
    """WebSocket endpoint for real-time Order Book updates"""
    await websocket.accept()
    redis_client = websocket.app.state.redis
    kafka_manager = websocket.app.state.kafka_manager
    
    # 1. Send initial snapshot from Redis
    try:
        key = f"orderbook:{symbol}:latest"
        raw = await redis_client.get(key)
        if raw:
            data = json.loads(raw)
            bids_raw = data.get("bids", [])
            asks_raw = data.get("asks", [])
            
            # Calculate totals
            bids = []
            bids_total = 0.0
            for price, qty in bids_raw[:20]:
                bids_total += qty * price
                bids.append({"price": price, "quantity": qty, "total": bids_total})
            
            asks = []
            asks_total = 0.0
            for price, qty in asks_raw[:20]:
                asks_total += qty * price
                asks.append({"price": price, "quantity": qty, "total": asks_total})
            
            try:
                await websocket.send_json({
                    "type": "initial",
                    "symbol": symbol,
                    "bids": bids,
                    "asks": asks,
                    "timestamp": data.get("timestamp")
                })
            except (RuntimeError, WebSocketDisconnect) as send_err:
                print(f"Error sending initial orderbook data: {send_err}")
                raise  # Re-raise to close connection properly
    except Exception as e:
        print(f"Error loading initial orderbook from Redis: {e}")
        # Don't raise - continue with streaming even if initial data fails
    
    # 2. Subscribe to shared Kafka consumer
    try:
        await kafka_manager.subscribe("crypto_orderbook", symbol, websocket)
        
        # Keep connection alive and monitor for disconnects
        try:
            while True:
                # Try to receive with timeout to detect disconnects
                try:
                    await asyncio.wait_for(websocket.receive(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Timeout is OK, connection still alive
                    continue
                except (WebSocketDisconnect, RuntimeError):
                    # Connection closed
                    break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"Error in orderbook websocket: {e}")
    finally:
        # Unsubscribe when connection closes
        await kafka_manager.unsubscribe("crypto_orderbook", symbol, websocket)


@app.websocket("/ws/trades")
async def ws_trades(
    websocket: WebSocket,
    symbol: str,
    limit: int = Query(50, ge=1, le=100),
):
    """WebSocket endpoint for real-time Market Trades"""
    await websocket.accept()
    redis_client = websocket.app.state.redis
    kafka_manager = websocket.app.state.kafka_manager
    
    # 1. Send initial trades from Redis
    try:
        key = f"trades:{symbol}:list"
        trades_raw = await redis_client.zrange(key, -limit, -1, withscores=False)
        
        trades = []
        for trade_json in reversed(trades_raw):
            trade_data = json.loads(trade_json)
            trades.append({
                "symbol": trade_data.get("symbol", symbol),
                "price": trade_data.get("price", 0),
                "quantity": trade_data.get("quantity", 0),
                "time": trade_data.get("time", 0),
                "isBuyerMaker": trade_data.get("isBuyerMaker", False),
                "tradeId": trade_data.get("tradeId")
            })
        
        if trades:
            try:
                await websocket.send_json({
                    "type": "initial",
                    "symbol": symbol,
                    "trades": trades
                })
            except (RuntimeError, WebSocketDisconnect) as send_err:
                print(f"Error sending initial trades data: {send_err}")
                raise  # Re-raise to close connection properly
    except Exception as e:
        print(f"Error loading initial trades from Redis: {e}")
        # Don't raise - continue with streaming even if initial data fails
    
    # 2. Subscribe to shared Kafka consumer
    try:
        await kafka_manager.subscribe("crypto_trades", symbol, websocket)
        
        # Keep connection alive and monitor for disconnects
        try:
            while True:
                # Try to receive with timeout to detect disconnects
                try:
                    await asyncio.wait_for(websocket.receive(), timeout=1.0)
                except asyncio.TimeoutError:
                    # Timeout is OK, connection still alive
                    continue
                except (WebSocketDisconnect, RuntimeError):
                    # Connection closed
                    break
        except WebSocketDisconnect:
            pass
        except Exception as e:
            print(f"Error in trades websocket: {e}")
    finally:
        # Unsubscribe when connection closes
        await kafka_manager.unsubscribe("crypto_trades", symbol, websocket)

