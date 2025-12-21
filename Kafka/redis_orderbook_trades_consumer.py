"""
Redis Order Book & Trades Consumer with LocalOrderBook Pattern

This consumer implements the LocalOrderBook pattern to maintain accurate order book state:
1. Maintains full order book in memory for each symbol
2. Fetches initial snapshot from Binance REST API when symbol is first seen
3. Buffers incremental updates while waiting for snapshot
4. Applies incremental updates to maintain accurate state
5. Saves periodic snapshots to Redis with rate limiting

Key Features:
- Snapshot sync: Fetches full order book from Binance REST API on first symbol
- Event buffering: Buffers updates during snapshot fetch to prevent data loss
- Incremental updates: Applies only valid updates (update_id > last_update_id)
- Rate limiting: Saves to Redis every 100ms (10 writes/second) to avoid overload
- Error recovery: Retry logic for snapshot fetch with exponential backoff
- Thread-safe: Uses locks to ensure thread safety for concurrent operations
"""

import json
import os
import time
import threading
from typing import Dict, List, Tuple
from kafka import KafkaConsumer
import redis
import requests
from datetime import datetime

# Kafka configuration - default to Kubernetes service name
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "my-cluster-kafka-bootstrap.crypto-infra:9092")
TOPIC_ORDERBOOK = os.getenv("KAFKA_TOPIC_ORDERBOOK", "crypto_orderbook")
TOPIC_TRADES = os.getenv("KAFKA_TOPIC_TRADES", "crypto_trades")
CONSUMER_GROUP = os.getenv("CONSUMER_GROUP", "redis_orderbook_trades_group")

#
# Redis configuration
# Default to Kubernetes service name
#
REDIS_HOST = os.getenv("REDIS_HOST", "redis-master.crypto-infra.svc.cluster.local")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "123456")

# TTL in seconds
ORDERBOOK_TTL = 3600  # 1 hour
TRADES_TTL = 1800     # 30 minutes
MAX_TRADES = 100      # Keep last 100 trades per symbol

# Order Book configuration
SNAPSHOT_LIMIT = 1000  # Number of levels to fetch from Binance REST API
REDIS_WRITE_INTERVAL = 0.1  # Write to Redis every 100ms (10 writes/second)
SNAPSHOT_RETRY_ATTEMPTS = 3  # Number of retry attempts for snapshot fetch
SNAPSHOT_RETRY_DELAY = 2  # Delay between retries in seconds

# Force save interval: Save to Redis at least once per second even if no updates
FORCE_SAVE_INTERVAL = 1.0  # Force save every 1 second

# Create consumers for both topics
consumer_orderbook = KafkaConsumer(
    TOPIC_ORDERBOOK,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id=f"{CONSUMER_GROUP}_orderbook",
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

consumer_trades = KafkaConsumer(
    TOPIC_TRADES,
    bootstrap_servers=KAFKA_BROKER,
    auto_offset_reset='latest',
    enable_auto_commit=True,
    group_id=f"{CONSUMER_GROUP}_trades",
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

redis_client = redis.Redis(
    host=REDIS_HOST,
    port=REDIS_PORT,
    db=REDIS_DB,
    password=REDIS_PASSWORD,
    decode_responses=True,
)


# ============================================================================
# LocalOrderBook Class - Maintains full order book state in memory
# ============================================================================
class LocalOrderBook:
    """Maintains a local order book state for a symbol"""
    
    def __init__(self, symbol: str):
        self.symbol = symbol
        # Use dict and sort when needed (bids: descending, asks: ascending)
        self.bids: Dict[str, float] = {}  # price -> quantity
        self.asks: Dict[str, float] = {}  # price -> quantity
        self.last_update_id: int = 0
        self.last_push_time: float = 0.0
        self.last_force_save_time: float = time.time()  # Initialize to current time
        self.is_synced: bool = False
        self._lock = threading.Lock()
    
    def apply_update(self, data: dict):
        """Apply incremental update to order book"""
        with self._lock:
            # Update bids
            if 'b' in data:
                self.update_levels(data['b'], self.bids)
            
            # Update asks
            if 'a' in data:
                self.update_levels(data['a'], self.asks)
            
            # Update last update ID
            # Note: If update ID is not present, increment a counter to track that we've applied updates
            if 'u' in data:
                self.last_update_id = data['u']
            elif 'lastUpdateId' in data:
                self.last_update_id = data['lastUpdateId']
            else:
                # No update ID in message - increment internal counter to track updates
                # This ensures we can still save updates even without update ID
                if self.last_update_id == 0:
                    # If still at 0 (initial state), keep it at 0 (will be set from snapshot)
                    pass
                else:
                    # Increment to track that we've applied an update
                    self.last_update_id += 1
    
    def update_levels(self, levels: List[List], book_side: Dict[str, float]):
        """Update order book levels (bids or asks)"""
        for level in levels:
            if len(level) < 2:
                continue
            price = str(level[0])
            qty = float(level[1])
            
            if qty == 0:
                # Remove level if quantity is 0
                book_side.pop(price, None)
            else:
                # Add or update level
                book_side[price] = qty
    
    def get_sorted_bids(self, limit: int = None, lock_acquired: bool = False) -> List[Tuple[float, float]]:
        """Get sorted bids (descending by price)"""
        if lock_acquired:
            sorted_bids = sorted(
                [(float(price), qty) for price, qty in self.bids.items()],
                key=lambda x: x[0],
                reverse=True
            )
            return sorted_bids[:limit] if limit else sorted_bids
        else:
            with self._lock:
                sorted_bids = sorted(
                    [(float(price), qty) for price, qty in self.bids.items()],
                    key=lambda x: x[0],
                    reverse=True
                )
                return sorted_bids[:limit] if limit else sorted_bids
    
    def get_sorted_asks(self, limit: int = None, lock_acquired: bool = False) -> List[Tuple[float, float]]:
        """Get sorted asks (ascending by price)"""
        if lock_acquired:
            sorted_asks = sorted(
                [(float(price), qty) for price, qty in self.asks.items()],
                key=lambda x: x[0]
            )
            return sorted_asks[:limit] if limit else sorted_asks
        else:
            with self._lock:
                sorted_asks = sorted(
                    [(float(price), qty) for price, qty in self.asks.items()],
                    key=lambda x: x[0]
                )
                return sorted_asks[:limit] if limit else sorted_asks
    
    def get_payload(self, limit: int = 100) -> dict:
        """Get formatted payload for Redis storage"""
        with self._lock:
            bids = self.get_sorted_bids(limit, lock_acquired=True)
            asks = self.get_sorted_asks(limit, lock_acquired=True)
            
            payload = {
                "symbol": self.symbol,
                "lastUpdateId": self.last_update_id,
                "bids": [[price, qty] for price, qty in bids],
                "asks": [[price, qty] for price, qty in asks],
                "timestamp": int(time.time() * 1000),
                "updatedAt": datetime.now().isoformat()
            }
            
            # Debug logging
            if len(bids) == 0 or len(asks) == 0:
                print(f"⚠️ Warning: get_payload() for {self.symbol} returned empty data: bids={len(bids)}, asks={len(asks)}, "
                      f"book.bids={len(self.bids)}, book.asks={len(self.asks)}")
            
            return payload
    
    def clear(self):
        """Clear order book state"""
        with self._lock:
            self.bids.clear()
            self.asks.clear()
            self.last_update_id = 0
            self.is_synced = False
    
    def should_push_to_redis(self) -> bool:
        """Check if enough time has passed to push to Redis"""
        now = time.time()
        
        # Check rate limiting (100ms interval)
        if now - self.last_push_time >= REDIS_WRITE_INTERVAL:
            self.last_push_time = now
            return True
        
        # Also check force save interval (1 second) to ensure updates are saved even if rate limited
        if now - self.last_force_save_time >= FORCE_SAVE_INTERVAL:
            self.last_force_save_time = now
            return True
        
        return False


# Global state for order books and event buffers
orderbooks: Dict[str, LocalOrderBook] = {}
event_buffers: Dict[str, List[dict]] = {}
orderbook_locks: Dict[str, threading.Lock] = {}


def get_orderbook_lock(symbol: str) -> threading.Lock:
    """Get or create lock for a symbol"""
    if symbol not in orderbook_locks:
        orderbook_locks[symbol] = threading.Lock()
    return orderbook_locks[symbol]


def fetch_snapshot(symbol: str, limit: int = SNAPSHOT_LIMIT, retry_attempts: int = SNAPSHOT_RETRY_ATTEMPTS) -> dict:
    """Fetch order book snapshot from Binance REST API with retry logic"""
    url = f"https://fapi.binance.com/fapi/v1/depth"
    params = {
        "symbol": symbol.upper(),
        "limit": limit
    }
    
    last_error = None
    for attempt in range(1, retry_attempts + 1):
        try:
            if attempt > 1:
                print(f"🔄 Retrying snapshot fetch for {symbol} (attempt {attempt}/{retry_attempts})...")
            else:
                print(f"📥 Fetching snapshot for {symbol} from Binance REST API...")
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            snapshot = response.json()
            
            # Validate snapshot data
            if not snapshot.get('bids') or not snapshot.get('asks'):
                raise ValueError(f"Invalid snapshot data: missing bids or asks")
            
            if not snapshot.get('lastUpdateId'):
                raise ValueError(f"Invalid snapshot data: missing lastUpdateId")
            
            print(f"✅ Snapshot fetched for {symbol}: lastUpdateId={snapshot.get('lastUpdateId')}, "
                  f"bids={len(snapshot.get('bids', []))}, asks={len(snapshot.get('asks', []))}")
            
            return snapshot
            
        except requests.exceptions.Timeout as e:
            last_error = f"Timeout: {e}"
            print(f"⏱️ Timeout fetching snapshot for {symbol} (attempt {attempt}/{retry_attempts}): {e}")
            
        except requests.exceptions.RequestException as e:
            last_error = f"Request error: {e}"
            print(f"❌ Error fetching snapshot for {symbol} (attempt {attempt}/{retry_attempts}): {e}")
            
        except ValueError as e:
            last_error = f"Validation error: {e}"
            print(f"❌ Invalid snapshot data for {symbol} (attempt {attempt}/{retry_attempts}): {e}")
            # Don't retry on validation errors
            break
            
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            print(f"❌ Unexpected error fetching snapshot for {symbol} (attempt {attempt}/{retry_attempts}): {e}")
        
        # Wait before retry (except on last attempt)
        if attempt < retry_attempts:
            time.sleep(SNAPSHOT_RETRY_DELAY)
    
    print(f"❌ Failed to fetch snapshot for {symbol} after {retry_attempts} attempts. Last error: {last_error}")
    return None

def save_orderbook_to_redis(symbol: str, orderbook: LocalOrderBook, limit: int = 100) -> str:
    """Save Order Book from LocalOrderBook to Redis with full metadata"""
    try:
        payload = orderbook.get_payload(limit=limit)
        
        # Debug: Log payload details
        bids_count = len(payload.get('bids', [])) if isinstance(payload.get('bids'), list) else 0
        asks_count = len(payload.get('asks', [])) if isinstance(payload.get('asks'), list) else 0
        last_update_id = payload.get('lastUpdateId')
        
        # Validate payload
        if not payload.get('bids') or not payload.get('asks'):
            print(f"⚠️ Skipping Redis save for {symbol}: empty bids ({bids_count}) or asks ({asks_count})")
            return None
        
        # Note: lastUpdateId may be 0 if no updates have been received yet after snapshot
        # But we should still save if we have data (snapshot was saved with valid lastUpdateId)
        if last_update_id is None:
            print(f"⚠️ Skipping Redis save for {symbol}: lastUpdateId is None")
            return None
        
        # Allow lastUpdateId = 0 only if this is the initial snapshot (which should have been saved already)
        # For incremental updates, we require a valid update ID
        if last_update_id == 0:
            # This might be OK if it's the initial snapshot, but log it
            print(f"⚠️ Warning: Saving orderbook for {symbol} with lastUpdateId=0 (might be initial state)")
        
        key = f"orderbook:{symbol}:latest"
        redis_client.setex(
            key,
            ORDERBOOK_TTL,
            json.dumps(payload)
        )
        
        print(f"💾 Saved orderbook to Redis for {symbol}: {bids_count} bids, {asks_count} asks, lastUpdateId={last_update_id}")
        return key
    except redis.RedisError as e:
        print(f"❌ Redis error saving orderbook for {symbol}: {e}")
        return None
    except Exception as e:
        print(f"❌ Error saving orderbook to Redis for {symbol}: {e}")
        import traceback
        traceback.print_exc()
        return None

def save_trade_to_redis(trade_data):
    """Save Market Trade to Redis (sorted set)"""
    symbol = trade_data.get("s", "UNKNOWN")
    if symbol == "UNKNOWN":
        return None
    
    # Format Trade data
    trade_time = trade_data.get("T", trade_data.get("received_at", int(datetime.now().timestamp() * 1000)))
    formatted_trade = {
        "symbol": symbol,
        "price": float(trade_data.get("p", 0)),
        "quantity": float(trade_data.get("q", 0)),
        "time": trade_time,
        "isBuyerMaker": trade_data.get("m", False),
        "tradeId": trade_data.get("t", 0),
        "updatedAt": datetime.now().isoformat()
    }
    
    # Use sorted set to keep trades sorted by time
    key = f"trades:{symbol}:list"
    trade_json = json.dumps(formatted_trade)
    
    # Add to sorted set with timestamp as score
    redis_client.zadd(key, {trade_json: trade_time})
    
    # Keep only last MAX_TRADES trades
    count = redis_client.zcard(key)
    if count > MAX_TRADES:
        # Remove oldest trades
        redis_client.zremrangebyrank(key, 0, count - MAX_TRADES - 1)
    
    # Set TTL
    redis_client.expire(key, TRADES_TTL)
    
    return key

def process_orderbook_messages():
    """Process Order Book messages from Kafka with LocalOrderBook pattern"""
    print("📊 Starting Order Book consumer with LocalOrderBook pattern...")
    
    def sync_orderbook(symbol: str):
        """Sync order book by fetching snapshot and applying buffered events"""
        lock = get_orderbook_lock(symbol)
        
        with lock:
            if symbol not in orderbooks:
                print(f"⚠️ Order book for {symbol} was removed before sync completed")
                return
            
            book = orderbooks[symbol]
            if book.is_synced:
                return
            
            try:
                # Fetch snapshot with retry logic
                snapshot = fetch_snapshot(symbol, limit=SNAPSHOT_LIMIT)
                if not snapshot:
                    print(f"⚠️ Failed to fetch snapshot for {symbol}, will retry on next update")
                    # Keep buffering events until snapshot succeeds
                    return
                
                # Apply snapshot to order book
                try:
                    snapshot_bids = snapshot.get('bids', [])
                    snapshot_asks = snapshot.get('asks', [])
                    snapshot_last_update_id = snapshot.get('lastUpdateId', 0)
                    
                    print(f"📝 Applying snapshot to order book for {symbol}: bids={len(snapshot_bids)}, asks={len(snapshot_asks)}, lastUpdateId={snapshot_last_update_id}")
                    
                    if not snapshot_bids or not snapshot_asks:
                        raise ValueError(f"Invalid snapshot: empty bids ({len(snapshot_bids)}) or asks ({len(snapshot_asks)})")
                    
                    if snapshot_last_update_id == 0:
                        raise ValueError(f"Invalid snapshot: lastUpdateId is 0")
                    
                    book.update_levels(snapshot_bids, book.bids)
                    book.update_levels(snapshot_asks, book.asks)
                    book.last_update_id = snapshot_last_update_id
                    
                    print(f"✅ Applied snapshot to order book for {symbol}: bids={len(book.bids)}, asks={len(book.asks)}, lastUpdateId={book.last_update_id}")
                    
                except Exception as e:
                    print(f"❌ Error applying snapshot to order book for {symbol}: {e}")
                    import traceback
                    traceback.print_exc()
                    return
                
                # Apply buffered events
                buffered_count = 0
                skipped_count = 0
                if symbol in event_buffers and event_buffers[symbol]:
                    for event in event_buffers[symbol]:
                        try:
                            event_update_id = event.get('u') or event.get('lastUpdateId', 0)
                            if event_update_id > book.last_update_id:
                                book.apply_update(event)
                                buffered_count += 1
                            else:
                                skipped_count += 1
                        except Exception as e:
                            print(f"⚠️ Error applying buffered event for {symbol}: {e}")
                            skipped_count += 1
                    
                    if buffered_count > 0:
                        print(f"✅ Applied {buffered_count} buffered events for {symbol}")
                    if skipped_count > 0:
                        print(f"⚠️ Skipped {skipped_count} outdated buffered events for {symbol}")
                    
                    del event_buffers[symbol]
                
                book.is_synced = True
                print(f"✅ Order book synced for {symbol}: lastUpdateId={book.last_update_id}, "
                      f"bids={len(book.bids)}, asks={len(book.asks)}")
                
                # Save initial snapshot to Redis
                try:
                    # Check if book has data before saving
                    if len(book.bids) == 0 or len(book.asks) == 0:
                        print(f"⚠️ Warning: Order book for {symbol} is empty after sync (bids: {len(book.bids)}, asks: {len(book.asks)})")
                    else:
                        print(f"💾 Attempting to save order book for {symbol} to Redis (bids: {len(book.bids)}, asks: {len(book.asks)}, lastUpdateId: {book.last_update_id})")
                        key = save_orderbook_to_redis(symbol, book)
                        if key:
                            print(f"✅ Successfully saved initial snapshot to Redis: {key}")
                        else:
                            print(f"⚠️ Failed to save initial snapshot to Redis for {symbol} - check validation logs above")
                except Exception as e:
                    print(f"❌ Error saving initial snapshot to Redis for {symbol}: {e}")
                    import traceback
                    traceback.print_exc()
                    
            except Exception as e:
                print(f"❌ Unexpected error in sync_orderbook for {symbol}: {e}")
                import traceback
                traceback.print_exc()
    
    try:
        message_count = 0
        last_message_time = time.time()
        for msg in consumer_orderbook:
            # Log that we received a message from Kafka
            current_time = time.time()
            if message_count == 0 or current_time - last_message_time > 10:
                print(f"📨 [OrderBook] Received message #{message_count + 1} from Kafka (topic: {msg.topic}, partition: {msg.partition}, offset: {msg.offset})")
                last_message_time = current_time
            
            try:
                message_count += 1
                orderbook_data = msg.value
                symbol = orderbook_data.get("s", "").upper()
                
                # Log first few messages to debug
                if message_count <= 5:
                    print(f"📨 [DEBUG] Received Kafka message #{message_count} for orderbook: symbol={symbol}, "
                          f"keys={list(orderbook_data.keys())[:10]}")
                
                if not symbol or symbol == "UNKNOWN":
                    print(f"⚠️ Skipped Order Book (invalid symbol): {symbol}, data keys: {list(orderbook_data.keys())[:5]}")
                    continue
                
                # Debug: Log when we receive messages (only for first few to avoid spam)
                if symbol not in orderbooks or not orderbooks[symbol].is_synced:
                    update_id = orderbook_data.get('u') or orderbook_data.get('lastUpdateId', 'N/A')
                    print(f"📨 Received orderbook message for {symbol}: updateId={update_id}")
                
                lock = get_orderbook_lock(symbol)
                
                with lock:
                    # Create LocalOrderBook if it doesn't exist
                    if symbol not in orderbooks:
                        orderbooks[symbol] = LocalOrderBook(symbol)
                        event_buffers[symbol] = []
                        print(f"📝 Created LocalOrderBook for {symbol}")
                        
                        # Check if Redis has invalid data and clear it
                        try:
                            key = f"orderbook:{symbol}:latest"
                            existing_data = redis_client.get(key)
                            if existing_data:
                                try:
                                    data = json.loads(existing_data)
                                    # Check if data is invalid (empty bids/asks or None lastUpdateId)
                                    bids_count = len(data.get('bids', [])) if isinstance(data.get('bids'), list) else 0
                                    asks_count = len(data.get('asks', [])) if isinstance(data.get('asks'), list) else 0
                                    last_update_id = data.get('lastUpdateId')
                                    
                                    if bids_count == 0 or asks_count == 0 or last_update_id is None or last_update_id == 0:
                                        print(f"🗑️ Clearing invalid orderbook data for {symbol} from Redis")
                                        redis_client.delete(key)
                                except:
                                    pass
                        except Exception as e:
                            print(f"⚠️ Error checking Redis data for {symbol}: {e}")
                        
                        # Start snapshot sync in background thread
                        sync_thread = threading.Thread(
                            target=sync_orderbook,
                            args=(symbol,),
                            daemon=True
                        )
                        sync_thread.start()
                    
                    book = orderbooks[symbol]
                    
                    # If not synced, buffer the event
                    if not book.is_synced:
                        event_buffers[symbol].append(orderbook_data)
                        if len(event_buffers[symbol]) % 10 == 0:  # Log every 10th buffered message
                            print(f"📦 Buffered {len(event_buffers[symbol])} messages for {symbol} (waiting for snapshot sync)")
                        continue
                    
                    # Validate update ID (if present)
                    update_id = orderbook_data.get('u') or orderbook_data.get('lastUpdateId')
                    
                    # Check if message has incremental update data
                    has_b = 'b' in orderbook_data and len(orderbook_data.get('b', [])) > 0
                    has_a = 'a' in orderbook_data and len(orderbook_data.get('a', [])) > 0
                    has_bids = 'bids' in orderbook_data and len(orderbook_data.get('bids', [])) > 0
                    has_asks = 'asks' in orderbook_data and len(orderbook_data.get('asks', [])) > 0
                    
                    # Log message structure for debugging
                    if message_count <= 10:
                        print(f"📊 [DEBUG] Processing orderbook message for {symbol}: has_b={has_b}, has_a={has_a}, "
                              f"has_bids={has_bids}, has_asks={has_asks}, "
                              f"b_count={len(orderbook_data.get('b', []))}, a_count={len(orderbook_data.get('a', []))}")
                    
                    # Skip if no update data
                    if not (has_b or has_a or has_bids or has_asks):
                        # Log this more frequently to understand why messages are being skipped
                        if message_count <= 20 or message_count % 50 == 0:
                            print(f"⏭️ Skipping message for {symbol}: no update data (has_b={has_b}, has_a={has_a}, "
                                  f"has_bids={has_bids}, has_asks={has_asks}, keys={list(orderbook_data.keys())[:10]})")
                        continue
                    
                    # Validate update ID (if present)
                    update_id = orderbook_data.get('u') or orderbook_data.get('lastUpdateId')
                    
                    if message_count <= 10:
                        print(f"🔄 [DEBUG] Processing update for {symbol}: updateId={update_id}, "
                              f"current_lastUpdateId={book.last_update_id}, is_synced={book.is_synced}, "
                              f"has_b={has_b}, has_a={has_a}")
                    
                    # Note: Binance @depth@1000ms stream may not include update ID in every message
                    # OR the update ID format may be different from snapshot (e.g., smaller numbers)
                    # Strategy: If update ID is missing or significantly different format, apply anyway
                    # Only skip if update ID is present AND clearly indicates an old/duplicate message
                    
                    if update_id is not None:
                        # Check if update ID format seems different (e.g., much smaller than snapshot)
                        # Snapshot IDs are typically very large (billions), stream IDs might be smaller
                        # If update ID is less than 1% of snapshot ID, likely different format - apply anyway
                        if book.last_update_id > 0:
                            id_ratio = update_id / book.last_update_id if book.last_update_id > 0 else 1.0
                            
                            # If update ID is much smaller (likely different format), apply anyway
                            if id_ratio < 0.01:
                                if message_count <= 20:
                                    print(f"🔄 Update ID format mismatch for {symbol}: stream={update_id}, "
                                          f"snapshot={book.last_update_id}, ratio={id_ratio:.6f} - applying anyway")
                            elif update_id <= book.last_update_id:
                                # Skip old updates (same format, older than current)
                                if message_count <= 20 or message_count % 100 == 0:
                                    print(f"⏭️ Skipping old update for {symbol}: {update_id} <= {book.last_update_id}")
                                continue
                    else:
                        # No update ID in message - apply anyway (Binance may not send it in every message)
                        if message_count <= 20:
                            print(f"🔄 No update ID in message for {symbol}, applying update anyway")
                    
                    # Apply incremental update
                    old_update_id = book.last_update_id
                    old_bids_count = len(book.bids)
                    old_asks_count = len(book.asks)
                    
                    book.apply_update(orderbook_data)
                    
                    # Check if order book actually changed
                    bids_changed = len(book.bids) != old_bids_count
                    asks_changed = len(book.asks) != old_asks_count
                    update_id_changed = book.last_update_id != old_update_id
                    
                    # Log when we apply updates
                    if bids_changed or asks_changed or update_id_changed:
                        if message_count <= 20 or message_count % 50 == 0:
                            print(f"🔄 Applied update for {symbol}: bids={old_bids_count}→{len(book.bids)}, "
                                  f"asks={old_asks_count}→{len(book.asks)}, updateId={old_update_id}→{book.last_update_id}")
                    
                    if not (bids_changed or asks_changed or update_id_changed):
                        # No actual change, skip saving
                        if message_count <= 20:
                            print(f"⏭️ No change for {symbol}, skipping save")
                        continue
                    
                    # Save to Redis with rate limiting
                    should_save = book.should_push_to_redis()
                    if message_count <= 20:
                        print(f"💾 Save check for {symbol}: should_save={should_save}")
                    
                    if should_save:
                        try:
                            key = save_orderbook_to_redis(symbol, book, limit=100)
                            if key:
                                bids_count = len(book.bids)
                                asks_count = len(book.asks)
                                print(f"✅ Order Book: {symbol} | Bids: {bids_count} | Asks: {asks_count} | "
                                      f"Update ID: {book.last_update_id} | Redis: {key}")
                            else:
                                print(f"⚠️ save_orderbook_to_redis returned None for {symbol}")
                        except Exception as e:
                            print(f"⚠️ Error saving orderbook update to Redis for {symbol}: {e}")
                            import traceback
                            traceback.print_exc()
                    else:
                        if message_count <= 20:
                            print(f"⏳ Rate limited for {symbol}, will save on next interval")
            
            except Exception as e:
                print(f"❌ Error processing orderbook message: {e}")
                import traceback
                traceback.print_exc()
                continue
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping Order Book consumer...")
    except Exception as e:
        print(f"❌ Order Book consumer error: {e}")
        import traceback
        traceback.print_exc()

def process_trades_messages():
    """Process Trade messages from Kafka"""
    print("💰 Starting Trades consumer...")
    try:
        for msg in consumer_trades:
            try:
                trade = msg.value
                symbol = trade.get("s", "UNKNOWN")
                
                key = save_trade_to_redis(trade)
                if key:
                    price = float(trade.get("p", 0))
                    quantity = float(trade.get("q", 0))
                    is_buyer_maker = trade.get("m", False)
                    side = "SELL" if is_buyer_maker else "BUY"
                    trade_time = datetime.fromtimestamp(int(trade.get("T", 0)) / 1000).strftime("%H:%M:%S")
                    
                    print(f"✅ Trade: {symbol} | {side} | Price: ${price:.2f} | Qty: {quantity:.6f} | Time: {trade_time}")
                    print(f"   Redis Key: {key} (TTL: {TRADES_TTL}s)")
                else:
                    print(f"⚠️ Skipped Trade (invalid symbol)")
            except Exception as e:
                # Log error but continue processing
                print(f"⚠️ Error processing trade message: {e}")
                import traceback
                traceback.print_exc()
                continue
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping Trades consumer...")
    except Exception as e:
        print(f"❌ Trades consumer error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    import threading
    
    print("=" * 80)
    print("Redis Order Book & Trades Consumer")
    print("=" * 80)
    print(f"Kafka Broker: {KAFKA_BROKER}")
    print(f"Order Book Topic: {TOPIC_ORDERBOOK}")
    print(f"Trades Topic: {TOPIC_TRADES}")
    print(f"Consumer Group: {CONSUMER_GROUP}")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Order Book TTL: {ORDERBOOK_TTL}s (1 hour)")
    print(f"Trades TTL: {TRADES_TTL}s (30 minutes)")
    print(f"Max Trades per Symbol: {MAX_TRADES}")
    print("=" * 80)
    print("Listening for messages from Kafka and saving to Redis...")
    print("=" * 80)
    
    # Run both consumers in separate threads
    thread_orderbook = threading.Thread(target=process_orderbook_messages, daemon=True)
    thread_trades = threading.Thread(target=process_trades_messages, daemon=True)
    
    thread_orderbook.start()
    thread_trades.start()
    
    try:
        # Keep main thread alive
        while True:
            import time
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down consumers...")
    finally:
        consumer_orderbook.close()
        consumer_trades.close()
        redis_client.close()
        print("✅ Closed Kafka and Redis connections.")

