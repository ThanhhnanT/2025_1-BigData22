import asyncio
import json
import contextlib
from collections import defaultdict
from typing import Dict, Set, Optional
from concurrent.futures import ThreadPoolExecutor

from kafka import KafkaConsumer
from fastapi import WebSocket, WebSocketDisconnect


class SharedKafkaManager:
    """
    Manages shared Kafka consumers for WebSocket connections.
    One consumer per topic/symbol combination, broadcasting to all subscribers.
    """
    
    def __init__(self, kafka_bootstrap: str):
        self.kafka_bootstrap = kafka_bootstrap
        self.subscribers: Dict[str, Set[WebSocket]] = defaultdict(set)
        self.consumers: Dict[str, KafkaConsumer] = {}
        self.streaming_tasks: Dict[str, asyncio.Task] = {}
        self.executor = ThreadPoolExecutor(max_workers=3)  # 1 per topic type
        self._locks: Dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._running: Dict[str, bool] = {}
    
    async def subscribe(self, topic: str, symbol: str, websocket: WebSocket):
        """Subscribe WebSocket to a topic/symbol combination"""
        key = f"{topic}:{symbol}"
        
        async with self._locks[key]:
            self.subscribers[key].add(websocket)
            
            # Start consumer if it doesn't exist
            if key not in self.consumers:
                await self._start_consumer(topic, symbol, key)
    
    async def unsubscribe(self, topic: str, symbol: str, websocket: WebSocket):
        """Unsubscribe WebSocket from a topic/symbol combination"""
        key = f"{topic}:{symbol}"
        
        async with self._locks[key]:
            self.subscribers[key].discard(websocket)
            
            # If no more subscribers, stop consumer
            if not self.subscribers[key] and key in self.consumers:
                await self._stop_consumer(key)
    
    async def _start_consumer(self, topic: str, symbol: str, key: str):
        """Start shared consumer for topic/symbol combination"""
        consumer = KafkaConsumer(
            topic,
            bootstrap_servers=self.kafka_bootstrap,
            group_id=None,
            enable_auto_commit=False,
            auto_offset_reset='latest',
            value_deserializer=lambda x: json.loads(x.decode('utf-8'))
        )
        self.consumers[key] = consumer
        self._running[key] = True
        
        # Start streaming task
        task = asyncio.create_task(self._stream_messages(topic, symbol, key))
        self.streaming_tasks[key] = task
    
    async def _stream_messages(self, topic: str, symbol: str, key: str):
        """Stream messages from Kafka and broadcast to all subscribers"""
        consumer = self.consumers[key]
        running = True
        
        def poll_messages():
            """Sync function to poll messages from Kafka"""
            messages = []
            try:
                msg_pack = consumer.poll(timeout_ms=1000)
                for topic_partition, msgs in msg_pack.items():
                    for msg in msgs:
                        messages.append(msg.value)
            except Exception as e:
                print(f"Error polling {key}: {e}")
            return messages
        
        try:
            while running and self._running.get(key, False):
                try:
                    # Poll messages from Kafka in thread pool
                    messages = await asyncio.get_event_loop().run_in_executor(
                        self.executor, poll_messages
                    )
                    
                    # Filter and broadcast messages
                    for msg in messages:
                        if not msg:
                            continue
                        
                        # Filter by symbol
                        msg_symbol = msg.get("s", "")
                        if msg_symbol != symbol:
                            continue
                        
                        # Format message based on topic type
                        formatted_msg = self._format_message(topic, symbol, msg)
                        if not formatted_msg:
                            continue
                        
                        # Broadcast to all subscribers
                        disconnected = set()
                        async with self._locks[key]:
                            subscribers_copy = list(self.subscribers[key])
                        
                        for ws in subscribers_copy:
                            try:
                                await ws.send_json(formatted_msg)
                            except (RuntimeError, WebSocketDisconnect):
                                # WebSocket disconnected, will be removed
                                disconnected.add(ws)
                        
                        # Remove disconnected websockets
                        if disconnected:
                            async with self._locks[key]:
                                for ws in disconnected:
                                    self.subscribers[key].discard(ws)
                            
                            # Stop consumer if no more subscribers
                            async with self._locks[key]:
                                if not self.subscribers[key]:
                                    running = False
                                    break
                    
                    # Sleep to avoid CPU spinning
                    await asyncio.sleep(0.1)
                except asyncio.CancelledError:
                    running = False
                    break
                except Exception as e:
                    print(f"Error in stream loop for {key}: {e}")
                    await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
        finally:
            print(f"Streaming task finished for {key}")
    
    def _format_message(self, topic: str, symbol: str, msg: dict) -> Optional[dict]:
        """Format Kafka message to WebSocket format based on topic type"""
        if "kline" in topic.lower() or "candle" in topic.lower():
            # Kline message format
            open_time = msg.get("t")
            is_closed = msg.get("x", False)
            
            candle_data = {
                "symbol": symbol,
                "interval": msg.get("i", "1m"),
                "openTime": open_time,
                "closeTime": msg.get("T"),
                "open": float(msg.get("o", 0)),
                "high": float(msg.get("h", 0)),
                "low": float(msg.get("l", 0)),
                "close": float(msg.get("c", 0)),
                "volume": float(msg.get("v", 0)),
                "quoteVolume": float(msg.get("q", 0)),
                "trades": int(msg.get("n", 0)),
                "x": is_closed,
            }
            
            # Determine message type based on candle state
            # If candle is closed, it's a new completed candle (realtime)
            # If candle is not closed, it's an update to the forming candle (update)
            # This matches the original logic where updates to same openTime = "update"
            return {
                "type": "update" if not is_closed else "realtime",
                "candle": candle_data
            }
        
        elif "orderbook" in topic.lower():
            # Orderbook message format
            bids_raw = msg.get("bids", [])
            asks_raw = msg.get("asks", [])
            
            # Calculate totals
            bids = []
            bids_total = 0.0
            for price, qty in bids_raw[:20]:
                bids_total += qty * price
                bids.append({
                    "price": float(price),
                    "quantity": float(qty),
                    "total": bids_total
                })
            
            asks = []
            asks_total = 0.0
            for price, qty in asks_raw[:20]:
                asks_total += qty * price
                asks.append({
                    "price": float(price),
                    "quantity": float(qty),
                    "total": asks_total
                })
            
            return {
                "type": "update",
                "symbol": symbol,
                "bids": bids,
                "asks": asks,
                "timestamp": msg.get("received_at")
            }
        
        elif "trades" in topic.lower():
            # Trades message format
            trade = {
                "symbol": symbol,
                "price": float(msg.get("p", 0)),
                "quantity": float(msg.get("q", 0)),
                "time": msg.get("T", msg.get("received_at", 0)),
                "isBuyerMaker": msg.get("m", False),
                "tradeId": msg.get("t")
            }
            
            return {
                "type": "realtime",
                "trade": trade
            }
        
        return None
    
    async def _stop_consumer(self, key: str):
        """Stop consumer when no more subscribers"""
        print(f"Stopping consumer for {key} (no more subscribers)")
        
        # Mark as not running
        self._running[key] = False
        
        # Cancel streaming task
        if key in self.streaming_tasks:
            task = self.streaming_tasks[key]
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            del self.streaming_tasks[key]
        
        # Close consumer
        if key in self.consumers:
            self.consumers[key].close()
            del self.consumers[key]
        
        print(f"Consumer stopped for {key}")
    
    async def shutdown(self):
        """Shutdown all consumers and cleanup resources"""
        print("Shutting down SharedKafkaManager...")
        
        # Stop all consumers
        keys = list(self.consumers.keys())
        for key in keys:
            await self._stop_consumer(key)
        
        # Shutdown executor
        self.executor.shutdown(wait=True)
        
        print("SharedKafkaManager shutdown complete")

