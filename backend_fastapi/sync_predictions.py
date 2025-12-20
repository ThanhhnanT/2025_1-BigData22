#!/usr/bin/env python3
"""
Sync predictions from MongoDB to Redis
Use this to populate Redis when predictions are saved only to MongoDB
"""

import os
import json
from datetime import datetime
from pymongo import MongoClient
import redis

# Configuration - use local services
MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:123456@localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "CRYPTO")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "123456")

def sync_predictions_to_redis():
    """
    Read latest predictions from MongoDB and save to Redis
    """
    print("=" * 70)
    print("Syncing predictions from MongoDB to Redis")
    print("=" * 70)
    
    try:
        # Connect to MongoDB
        print("\n1. Connecting to MongoDB...")
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        mongo_db = mongo_client[MONGO_DB]
        predictions_col = mongo_db["predictions"]
        
        # Get count
        count = predictions_col.count_documents({})
        print(f"   Found {count} total prediction records")
        
        if count == 0:
            print("   ERROR: No predictions in MongoDB!")
            print("   Run: python Spark/batch/predict_price.py")
            return
        
        # Connect to Redis
        print("\n2. Connecting to Redis...")
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
                socket_connect_timeout=5
            )
            redis_client.ping()
            print(f"   Connected to Redis at {REDIS_HOST}:{REDIS_PORT}")
        except Exception as e:
            print(f"   ERROR: Cannot connect to Redis: {e}")
            print(f"   Ensure Redis is running: docker ps | grep redis")
            return
        
        # Get latest predictions per symbol
        print("\n3. Reading latest predictions from MongoDB...")
        
        # Group by symbol and get latest prediction for each
        pipeline = [
            {"$sort": {"prediction_time": -1}},
            {"$group": {
                "_id": "$symbol",
                "doc": {"$first": "$$ROOT"}
            }},
            {"$replaceRoot": {"newRoot": "$doc"}}
        ]
        
        latest_predictions = list(predictions_col.aggregate(pipeline))
        print(f"   Found {len(latest_predictions)} unique symbols with predictions")
        
        # Save to Redis
        print("\n4. Saving to Redis...")
        saved_count = 0
        failed_count = 0
        
        for pred in latest_predictions:
            try:
                symbol = pred.get("symbol", "UNKNOWN")
                
                # Prepare Redis value
                redis_value = {
                    "symbol": pred.get("symbol"),
                    "current_price": float(pred.get("close", 0)),
                    "predicted_price": float(pred.get("predicted_price", 0)),
                    "predicted_change": float(pred.get("predicted_change_pct", 0)),
                    "direction": pred.get("direction", "UNKNOWN"),
                    "prediction_time": pred.get("prediction_time"),
                    "target_time": pred.get("target_time"),
                    "confidence_score": float(abs(pred.get("predicted_change_pct", 0)))
                }
                
                # Save to Redis
                key = f"crypto:prediction:{symbol}"
                redis_client.setex(
                    key,
                    300,  # 5 minutes TTL
                    json.dumps(redis_value)
                )
                saved_count += 1
                
                direction = redis_value["direction"]
                change = redis_value["predicted_change"]
                print(f"   {symbol:<10} -> {direction:>4} ({change:>6.2f}%)")
                
            except Exception as e:
                failed_count += 1
                print(f"   ERROR syncing {symbol}: {e}")
        
        print(f"\n5. Sync Result:")
        print(f"   Saved: {saved_count}")
        print(f"   Failed: {failed_count}")
        
        if saved_count > 0:
            print("\n   SUCCESS! Predictions are now available in Redis")
            print("   Try: curl http://localhost:8000/predictions")
        
        # Close connections
        redis_client.close()
        mongo_client.close()
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


def check_redis_status():
    """Check current Redis status"""
    print("\n" + "=" * 70)
    print("Current Redis Status")
    print("=" * 70)
    
    try:
        redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=5
        )
        redis_client.ping()
        print(f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}\n")
        
        # Scan for prediction keys
        cursor = 0
        keys = []
        while True:
            cursor, partial_keys = redis_client.scan(cursor, match="crypto:prediction:*", count=100)
            keys.extend(partial_keys)
            if cursor == 0:
                break
        
        print(f"Prediction keys in Redis: {len(keys)}")
        
        if keys:
            print("\nCached Predictions:")
            print("-" * 70)
            for key in sorted(keys):
                val = redis_client.get(key)
                if val:
                    pred = json.loads(val)
                    symbol = pred.get("symbol", "N/A")
                    current = pred.get("current_price", 0)
                    predicted = pred.get("predicted_price", 0)
                    change = pred.get("predicted_change", 0)
                    direction = pred.get("direction", "N/A")
                    
                    print(f"{symbol:<10} | {direction:>4} ({change:>6.2f}%) | "
                          f"${current:>10.2f} -> ${predicted:>10.2f}")
        else:
            print("No predictions cached in Redis")
            print("Run sync_predictions.py to populate Redis from MongoDB")
        
        redis_client.close()
        
    except Exception as e:
        print(f"Cannot connect to Redis: {e}")
        print("Ensure Redis is running: docker ps")


if __name__ == "__main__":
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 15 + "MongoDB -> Redis Prediction Sync" + " " * 21 + "║")
    print("╚" + "=" * 68 + "╝")
    
    # Check current status first
    check_redis_status()
    
    # Then sync
    print("\n")
    response = input("Sync MongoDB predictions to Redis? (y/n): ").strip().lower()
    if response == 'y':
        sync_predictions_to_redis()
    else:
        print("Skipped.")
    
    print("\n")
