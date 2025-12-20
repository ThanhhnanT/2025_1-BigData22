#!/usr/bin/env python3
"""
Script to clear Redis data
"""

import os
import redis

REDIS_HOST = os.getenv("REDIS_HOST", "my-redis-master.crypto-infra.svc.cluster.local")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "123456")

print("=" * 80)
print("🗑️  Clearing Redis Data")
print("=" * 80)
print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
print(f"DB: {REDIS_DB}")
print("=" * 80)

try:
    # Connect to Redis
    redis_client = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        password=REDIS_PASSWORD,
        decode_responses=True
    )
    
    # Test connection
    redis_client.ping()
    print("✅ Connected to Redis")
    
    print("\n🗑️  Clearing all data in DB 0...")
    
    # Get all keys
    all_keys = redis_client.keys("*")
    
    if all_keys:
        print(f"   Found {len(all_keys)} keys to delete")
        
        # Delete in batches to avoid memory issues
        batch_size = 1000
        deleted_count = 0
        
        for i in range(0, len(all_keys), batch_size):
            batch = all_keys[i:i + batch_size]
            redis_client.delete(*batch)
            deleted_count += len(batch)
            print(f"   Deleted {deleted_count}/{len(all_keys)} keys...", end='\r')
        
        print(f"\n✅ Deleted {deleted_count} keys")
    else:
        print("   No keys found - Redis is already empty")
    
    redis_client.close()
    print("\n✅ Done!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()

