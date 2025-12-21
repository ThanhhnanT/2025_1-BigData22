import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient

from .config import settings
from .schemas import (
    Candle, LatestKline, OHLCResponse,
    OrderBookResponse, OrderBookEntry, TradesResponse, Trade,
    Prediction, PredictionResponse, PredictionsListResponse,
    PredictionHistory, PredictionHistoryResponse,
    RankingResponse, CoinRanking
)
from .kafka_manager import SharedKafkaManager
from .indicators import calculate_indicators


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Connect to MongoDB
    mongo_client = AsyncIOMotorClient(settings.mongo_uri)
    app.state.mongo_client = mongo_client
    app.state.mongo_db = mongo_client[settings.mongo_db]
    
    # Test MongoDB connection
    try:
        await mongo_client.admin.command('ping')
        print(f"✅ Connected to MongoDB: {settings.mongo_db}")
    except Exception as e:
        print(f"❌ Failed to connect to MongoDB: {e}")

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
    
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Invalid JSON data in Redis for {symbol}: {str(e)}"
        )
    
    # Process bids and asks, calculate totals, and limit results
    bids_raw = data.get("bids", [])
    asks_raw = data.get("asks", [])
    
    # Validate data format
    if not isinstance(bids_raw, list) or not isinstance(asks_raw, list):
        raise HTTPException(
            status_code=500,
            detail=f"Invalid data format in Redis for {symbol}: bids and asks must be lists"
        )
    
    # Calculate cumulative totals for bids (descending) and asks (ascending)
    bids = []
    bids_total = 0.0
    try:
        for i, level in enumerate(bids_raw[:limit]):
            if not isinstance(level, list) or len(level) < 2:
                continue
            price = float(level[0])
            qty = float(level[1])
            bids_total += qty * price
            bids.append(OrderBookEntry(
                price=price,
                quantity=qty,
                total=bids_total
            ))
    except (ValueError, TypeError, IndexError) as e:
        print(f"Error processing bids for {symbol}: {e}")
        print(f"Bids raw data: {bids_raw[:5] if bids_raw else 'empty'}")
    
    asks = []
    asks_total = 0.0
    try:
        for i, level in enumerate(asks_raw[:limit]):
            if not isinstance(level, list) or len(level) < 2:
                continue
            price = float(level[0])
            qty = float(level[1])
            asks_total += qty * price
            asks.append(OrderBookEntry(
                price=price,
                quantity=qty,
                total=asks_total
            ))
    except (ValueError, TypeError, IndexError) as e:
        print(f"Error processing asks for {symbol}: {e}")
        print(f"Asks raw data: {asks_raw[:5] if asks_raw else 'empty'}")
    
    # Log warning if data is empty
    if len(bids) == 0 and len(asks) == 0:
        print(f"⚠️ Warning: Empty order book data for {symbol} from Redis")
        print(f"Raw data keys: {list(data.keys())}")
        print(f"Bids raw type: {type(bids_raw)}, length: {len(bids_raw) if isinstance(bids_raw, list) else 'N/A'}")
        print(f"Asks raw type: {type(asks_raw)}, length: {len(asks_raw) if isinstance(asks_raw, list) else 'N/A'}")
    
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
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as e:
                print(f"Error parsing orderbook JSON from Redis for {symbol}: {e}")
                data = None
            
            if data:
                bids_raw = data.get("bids", [])
                asks_raw = data.get("asks", [])
                
                # Validate and process bids
                bids = []
                bids_total = 0.0
                if isinstance(bids_raw, list):
                    for level in bids_raw[:20]:
                        if isinstance(level, list) and len(level) >= 2:
                            try:
                                price = float(level[0])
                                qty = float(level[1])
                                bids_total += qty * price
                                bids.append({"price": price, "quantity": qty, "total": bids_total})
                            except (ValueError, TypeError):
                                continue
                
                # Validate and process asks
                asks = []
                asks_total = 0.0
                if isinstance(asks_raw, list):
                    for level in asks_raw[:20]:
                        if isinstance(level, list) and len(level) >= 2:
                            try:
                                price = float(level[0])
                                qty = float(level[1])
                                asks_total += qty * price
                                asks.append({"price": price, "quantity": qty, "total": asks_total})
                            except (ValueError, TypeError):
                                continue
                
                # Only send if we have data
                if len(bids) > 0 or len(asks) > 0:
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
                else:
                    print(f"⚠️ Warning: Empty order book data for {symbol} from Redis (bids: {len(bids_raw) if isinstance(bids_raw, list) else 'N/A'}, asks: {len(asks_raw) if isinstance(asks_raw, list) else 'N/A'})")
        else:
            print(f"⚠️ No orderbook data in Redis for {symbol}")
    except Exception as e:
        print(f"Error loading initial orderbook from Redis: {e}")
        import traceback
        traceback.print_exc()
        # Don't raise - continue with streaming even if initial data fails
    
    # 2. Poll Redis periodically for real-time updates
    # Note: We poll Redis instead of streaming from Kafka because:
    # - Consumer maintains full order book in Redis
    # - Kafka only has incremental updates which we skip
    # - Redis has the latest full snapshot updated every 100ms
    last_update_id = None
    poll_interval = 0.2  # Poll every 200ms (5 times per second)
    
    async def poll_and_send_updates():
        """Poll Redis and send updates when order book changes"""
        nonlocal last_update_id
        key = f"orderbook:{symbol}:latest"
        
        try:
            raw = await redis_client.get(key)
            if not raw:
                return
            
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                return
            
            current_update_id = data.get("lastUpdateId")
            
            # Only send if update ID changed
            if current_update_id and current_update_id != last_update_id:
                # Debug logging (can be removed later)
                # print(f"🔄 Order book update detected for {symbol}: {last_update_id} → {current_update_id}")
                bids_raw = data.get("bids", [])
                asks_raw = data.get("asks", [])
                
                # Validate and process bids
                bids = []
                bids_total = 0.0
                if isinstance(bids_raw, list):
                    for level in bids_raw[:20]:
                        if isinstance(level, list) and len(level) >= 2:
                            try:
                                price = float(level[0])
                                qty = float(level[1])
                                bids_total += qty * price
                                bids.append({"price": price, "quantity": qty, "total": bids_total})
                            except (ValueError, TypeError):
                                continue
                
                # Validate and process asks
                asks = []
                asks_total = 0.0
                if isinstance(asks_raw, list):
                    for level in asks_raw[:20]:
                        if isinstance(level, list) and len(level) >= 2:
                            try:
                                price = float(level[0])
                                qty = float(level[1])
                                asks_total += qty * price
                                asks.append({"price": price, "quantity": qty, "total": asks_total})
                            except (ValueError, TypeError):
                                continue
                
                # Send update if we have valid data
                # Note: Send even if only one side has data (bids or asks) to allow partial updates
                if len(bids) > 0 or len(asks) > 0:
                    try:
                        payload = {
                            "type": "update",
                            "symbol": symbol,
                            "bids": bids,
                            "asks": asks,
                            "timestamp": data.get("timestamp")
                        }
                        # print(f"📤 Sending orderbook update to WebSocket for {symbol}: bids={len(bids)}, asks={len(asks)}")
                        await websocket.send_json(payload)
                        last_update_id = current_update_id
                    except (RuntimeError, WebSocketDisconnect):
                        raise  # Re-raise to stop polling
                else:
                    print(f"⚠️ Skipping WebSocket send for {symbol}: no bids or asks data")
        except (RuntimeError, WebSocketDisconnect):
            raise  # Re-raise to stop polling
        except Exception as e:
            # Log error but continue polling
            print(f"Error polling orderbook from Redis for {symbol}: {e}")
    
    # Set initial last_update_id from initial snapshot
    try:
        key = f"orderbook:{symbol}:latest"
        raw = await redis_client.get(key)
        if raw:
            data = json.loads(raw)
            last_update_id = data.get("lastUpdateId")
    except:
        pass
    
    # Start polling task
    try:
        while True:
            try:
                # Poll Redis for updates
                await poll_and_send_updates()
                
                # Also check for client disconnects
                try:
                    await asyncio.wait_for(websocket.receive(), timeout=poll_interval)
                except asyncio.TimeoutError:
                    # Timeout is OK, continue polling
                    continue
                except (WebSocketDisconnect, RuntimeError):
                    # Connection closed
                    break
            except (WebSocketDisconnect, RuntimeError):
                break
            except Exception as e:
                print(f"Error in orderbook websocket polling: {e}")
                await asyncio.sleep(poll_interval)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Error in orderbook websocket: {e}")


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


@app.get("/ranking/top-gainers", response_model=RankingResponse)
async def get_top_gainers(
    limit: int = Query(1000, ge=1, le=10000, description="Number of top coins to return"),
    type: str = Query("gainers", description="Type: 'gainers' or 'losers'"),
    redis_client=Depends(get_redis),
):
    """Get Top Gainers/Losers ranking from Redis"""
    redis_key = "ranking:top_gainers"
    
    try:
        raw = await redis_client.get(redis_key)
        if not raw:
            raise HTTPException(
                status_code=404,
                detail="No ranking data available. Spark streaming job may not be running."
            )
        
        rankings_data = json.loads(raw)
        
        if not isinstance(rankings_data, list):
            raise HTTPException(
                status_code=500,
                detail="Invalid ranking data format in Redis"
            )
        
        # Convert to CoinRanking objects
        rankings = [CoinRanking(**item) for item in rankings_data]
        
        # Filter by type (gainers or losers)
        if type == "losers":
            # Sort by percent_change ascending (most negative first)
            rankings = sorted(rankings, key=lambda x: x.percent_change)[:limit]
        else:
            # Sort by percent_change descending (highest first) - default gainers
            rankings = sorted(rankings, key=lambda x: x.percent_change, reverse=True)[:limit]
        
        return RankingResponse(
            type=type,
            count=len(rankings),
            rankings=rankings,
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON data in Redis: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading ranking data: {str(e)}"
        )


@app.get("/prediction/{symbol}", response_model=PredictionResponse)
async def get_prediction(
    symbol: str,
    redis_client=Depends(get_redis),
    mongo_db=Depends(get_mongo),
):
    """Get latest price prediction for a symbol from Redis (fallback to MongoDB)"""
    redis_key = f"crypto:prediction:{symbol}"
    
    try:
        # Try Redis first
        raw = await redis_client.get(redis_key)
        if raw:
            try:
                pred_data = json.loads(raw)
                return PredictionResponse(
                    symbol=symbol,
                    prediction=Prediction(**pred_data)
                )
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Error parsing prediction JSON from Redis for {symbol}: {e}")
                # Fall through to MongoDB
        
        # Fallback to MongoDB
        predictions_col = mongo_db["predictions"]
        latest_pred = await predictions_col.find_one(
            {"symbol": symbol},
            sort=[("prediction_time", -1)]
        )
        
        if latest_pred:
            # Convert MongoDB document to Prediction model
            pred_data = {
                "symbol": latest_pred.get("symbol", symbol),
                "current_price": float(latest_pred.get("close", 0)),
                "predicted_price": float(latest_pred.get("predicted_price", 0)),
                "predicted_change": float(latest_pred.get("predicted_change_pct", 0)),
                "direction": latest_pred.get("direction", "UP"),
                "prediction_time": latest_pred.get("prediction_time", ""),
                "target_time": latest_pred.get("target_time", ""),
                "confidence_score": float(abs(latest_pred.get("predicted_change_pct", 0)))
            }
            return PredictionResponse(
                symbol=symbol,
                prediction=Prediction(**pred_data)
            )
        
        raise HTTPException(
            status_code=404,
            detail=f"No prediction found for {symbol}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading prediction for {symbol}: {str(e)}"
        )


@app.get("/indicators/realtime")
async def get_realtime_indicators(
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    types: str = Query("ma7,ma25,ema12", description="Comma-separated indicator types (e.g., ma7,ma25,ema12,bollinger)"),
    limit: int = Query(200, ge=1, le=2000, description="Number of candles to use for calculation"),
    redis_client=Depends(get_redis),
):
    """
    Get real-time technical indicators calculated from Redis data.
    Results are cached in Redis for 5 minutes.
    """
    import hashlib
    
    # Parse indicator types
    indicator_types = [t.strip() for t in types.split(",") if t.strip()]
    if not indicator_types:
        raise HTTPException(status_code=400, detail="At least one indicator type is required")
    
    try:
        # Get OHLC data from Redis
        index_key = f"crypto:{symbol}:1m:index"
        timestamps = await redis_client.zrange(index_key, -limit, -1, withscores=True)
        
        if not timestamps:
            raise HTTPException(status_code=404, detail=f"No data found for {symbol}")
        
        # Get latest candle timestamp for cache key
        latest_timestamp = int(timestamps[-1][1]) if timestamps else 0
        
        # Build cache key
        types_hash = hashlib.md5(",".join(sorted(indicator_types)).encode()).hexdigest()[:8]
        cache_key = f"indicator:realtime:{symbol}:{types_hash}:{latest_timestamp}"
        
        # Check cache
        cached = await redis_client.get(cache_key)
        if cached:
            try:
                return json.loads(cached)
            except json.JSONDecodeError:
                pass  # Cache corrupted, recalculate
        
        # Fetch candles from Redis
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
                        "close": data["close"],
                        "open": data["open"],
                        "high": data["high"],
                        "low": data["low"],
                        "volume": data.get("volume", 0)
                    })
        
        if not candles:
            raise HTTPException(status_code=404, detail=f"No closed candles found for {symbol}")
        
        # Sort by openTime ascending
        candles.sort(key=lambda x: x["openTime"])
        
        # Calculate indicators
        indicators = calculate_indicators(candles, indicator_types)
        
        # Prepare response
        response = {
            "symbol": symbol,
            "interval": "1m",
            "indicators": indicators,
            "candle_count": len(candles),
            "last_timestamp": latest_timestamp
        }
        
        # Cache result for 5 minutes (300 seconds)
        await redis_client.setex(cache_key, 300, json.dumps(response))
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error calculating real-time indicators: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error calculating indicators: {str(e)}"
        )


@app.get("/indicators/historical")
async def get_historical_indicators(
    symbol: str = Query("BTCUSDT", description="Trading pair, e.g. BTCUSDT"),
    interval: str = Query("5m", description="Interval (5m, 1h, 4h, 1d)"),
    types: str = Query("ma7,ma25,ema12", description="Comma-separated indicator types"),
    collection: Optional[str] = Query(None, description="MongoDB collection name"),
    limit: int = Query(200, ge=1, le=2000),
    start: Optional[int] = Query(None, description="Start openTime (ms)"),
    end: Optional[int] = Query(None, description="End openTime (ms)"),
    mongo=Depends(get_mongo),
):
    """
    Get historical technical indicators from MongoDB (pre-calculated by Spark).
    If indicators are not found in MongoDB, returns empty dict.
    """
    # Parse indicator types
    indicator_types = [t.strip() for t in types.split(",") if t.strip()]
    if not indicator_types:
        raise HTTPException(status_code=400, detail="At least one indicator type is required")
    
    # Determine collection
    if collection:
        col_name = collection
    else:
        collection_map = {
            "5m": "5m_kline",
            "1h": "1h_kline",
            "4h": "4h_kline",
            "1d": "1d_kline",
        }
        col_name = collection_map.get(interval, "5m_kline")
    
    try:
        col = mongo[col_name]
        query = {"symbol": symbol, "interval": interval}
        if start is not None and end is not None:
            query["openTime"] = {"$gte": start, "$lte": end}
        elif start is not None:
            query["openTime"] = {"$gte": start}
        elif end is not None:
            query["openTime"] = {"$lte": end}
        
        # Projection to include indicators field
        projection = {
            "openTime": 1,
            "indicators": 1
        }
        
        cursor = (
            col.find(query, projection)
            .sort("openTime", 1)  # Ascending for chronological order
            .limit(limit)
        )
        docs = await cursor.to_list(length=limit)
        
        # Extract indicators from documents
        result_indicators = {ind_type: [] for ind_type in indicator_types}
        
        for doc in docs:
            indicators = doc.get("indicators", {})
            timestamp = doc.get("openTime", 0)
            
            for ind_type in indicator_types:
                if ind_type == "bollinger":
                    # Bollinger Bands is a nested object
                    bb = indicators.get("bollinger", {})
                    if not result_indicators[ind_type]:
                        result_indicators[ind_type] = {
                            "upper": [],
                            "middle": [],
                            "lower": []
                        }
                    result_indicators[ind_type]["upper"].append({
                        "x": timestamp,
                        "y": bb.get("upper")
                    })
                    result_indicators[ind_type]["middle"].append({
                        "x": timestamp,
                        "y": bb.get("middle")
                    })
                    result_indicators[ind_type]["lower"].append({
                        "x": timestamp,
                        "y": bb.get("lower")
                    })
                else:
                    # Simple indicators (ma, ema)
                    value = indicators.get(ind_type)
                    result_indicators[ind_type].append({
                        "x": timestamp,
                        "y": value
                    })
        
        return {
            "symbol": symbol,
            "interval": interval,
            "indicators": result_indicators,
            "count": len(docs),
            "from_cache": True  # Indicates data came from MongoDB (pre-calculated)
        }
        
    except Exception as e:
        print(f"Error fetching historical indicators: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching historical indicators: {str(e)}"
        )

