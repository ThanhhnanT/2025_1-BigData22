#!/usr/bin/env python3
"""
Top Gainers Ranking - Spark Streaming Job
Calculates rolling 1-minute % change and stores top gainers in Redis
"""

import os
import json
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, max, desc, to_json, struct
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StringType, DoubleType, LongType, BooleanType, StructField
from pyspark.sql.window import Window
import redis

# Environment variables
# Kafka: default to Kubernetes service name, fallback to localhost for local testing
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "my-cluster-kafka-bootstrap.crypto-infra:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "crypto_kline_1m")
SPARK_KAFKA_PACKAGE = 'org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0'
CHECKPOINT_PATH = os.getenv("CHECKPOINT_PATH", "/tmp/spark/ranking_top_gainers_cp")

# Redis: default to Kubernetes service name
REDIS_HOST = os.getenv("REDIS_HOST", "redis-master.crypto-infra.svc.cluster.local")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "123456")

REDIS_KEY = "ranking:top_gainers"
TOP_N = 10000  # Number of coins to store (increased to show all coins)
TTL_SECONDS = 60  # TTL for Redis key

KLINE_SCHEMA = StructType([
    StructField("s", StringType()),   # symbol
    StructField("c", StringType()),   # close price
    StructField("t", LongType()),     # timestamp (ms)
    StructField("x", BooleanType()),  # is candle closed (true/false as boolean)
    StructField("v", StringType()),   # volume (base asset)
    StructField("q", StringType()),   # quote volume (USDT) - this is 24h volume
])

spark = SparkSession.builder \
    .appName("TopGainersRanking") \
    .config("spark.jars.packages", SPARK_KAFKA_PACKAGE) \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# Read from Kafka
# Note: Spark Streaming tự động tạo consumer group riêng, không ảnh hưởng đến redis_consumer.py
# Sử dụng "latest" để chỉ đọc dữ liệu mới từ khi Spark Streaming start
raw_kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .option("failOnDataLoss", "false") \
    .option("maxOffsetsPerTrigger", "1000") \
    .load()

# Parse JSON - add error handling for malformed JSON
kline_df = raw_kafka_df.selectExpr("CAST(value AS STRING) as json_value") \
    .select(F.from_json(col("json_value"), KLINE_SCHEMA).alias("data")) \
    .select("data.*") \
    .filter(col("s").isNotNull())  # Filter out null rows from failed parsing

processed_df = kline_df \
    .withColumn("close_price_num", col("c").cast(DoubleType())) \
    .withColumn("volume_num", col("q").cast(DoubleType())) \
    .filter(col("close_price_num").isNotNull()) \
    .filter(col("s").isNotNull()) \
    .filter(col("t").isNotNull()) \
    .filter(col("x") == True) \
    .withColumn("event_ts", (col("t")/1000).cast("timestamp"))

# Aggregate: lấy giá close mới nhất và tổng volume trong mỗi cửa sổ 1 phút
agg_df = processed_df \
    .withWatermark("event_ts", "2 minutes") \
    .groupBy(F.window(col("event_ts"), "1 minutes"), col("s")) \
    .agg(
        F.max(F.struct(col("t"), col("close_price_num"), col("volume_num"))).alias("latest_struct"),
        F.sum("volume_num").alias("total_volume")
    ) \
    .select(
        col("s").alias("symbol"),
        col("window").start.alias("window_start"),
        col("latest_struct").getField("close_price_num").alias("close_price"),
        col("latest_struct").getField("t").alias("timestamp"),
        col("total_volume").alias("volume")
    )

# foreachBatch để tính rolling % change và lưu vào Redis
def process_batch(batch_df, batch_id):
    print(f"Batch {batch_id}: Processing batch...")
    row_count = batch_df.count()
    print(f"Batch {batch_id}: Received {row_count} rows")
    
    if batch_df.rdd.isEmpty():
        print(f"Batch {batch_id}: Empty dataframe, skipping")
        return
    
    try:
        # Calculate rolling % change using window function
        w = Window.partitionBy("symbol").orderBy("window_start")
        result = batch_df.withColumn("prev_close", F.lag("close_price").over(w)) \
                         .withColumn("prev_timestamp", F.lag("timestamp").over(w)) \
                         .filter(col("prev_close").isNotNull()) \
                         .withColumn("percent_change",
                                     ((col("close_price") - col("prev_close")) / col("prev_close") * 100))
        
        # Get latest data per symbol (most recent window) and sum volume
        latest_per_symbol = result.groupBy("symbol").agg(
            F.max(F.struct("window_start", "close_price", "percent_change", "timestamp", "volume")).alias("latest"),
            F.sum("volume").alias("total_volume_24h")
        ).select(
            col("symbol"),
            col("latest.window_start").alias("window_start"),
            col("latest.close_price").alias("close_price"),
            col("latest.percent_change").alias("percent_change"),
            col("latest.timestamp").alias("timestamp"),
            col("total_volume_24h").alias("volume")
        )
        
        # Sort by percent_change descending and take top N
        ranked = latest_per_symbol.orderBy(F.desc("percent_change")).limit(TOP_N)
        
        # Collect results
        rankings = ranked.collect()
        
        if not rankings:
            print(f"Batch {batch_id}: No rankings to save")
            return
        
        # Format data for Redis
        rankings_data = []
        for row in rankings:
            rankings_data.append({
                "symbol": row["symbol"],
                "price": float(row["close_price"]),
                "percent_change": float(row["percent_change"]),
                "volume": float(row["volume"]) if row["volume"] else 0.0,
                "market_cap": None,  # Market cap cần fetch từ API khác (CoinGecko/CMC)
                "timestamp": int(row["timestamp"])
            })
        
        # Connect to Redis and save with retry logic
        max_retries = 3
        retry_delay = 1  # seconds
        success = False
        
        for attempt in range(max_retries):
            redis_client = None
            try:
                redis_client = redis.Redis(
                    host=REDIS_HOST,
                    port=REDIS_PORT,
                    db=REDIS_DB,
                    password=REDIS_PASSWORD,
                    decode_responses=True,
                    socket_timeout=5,  # 5 seconds timeout
                    socket_connect_timeout=5,  # 5 seconds connection timeout
                    retry_on_timeout=True,
                    health_check_interval=30,  # Check connection health every 30 seconds
                )
                
                # Test connection first
                redis_client.ping()
                
                # Save rankings as JSON string with TTL
                redis_client.setex(
                    REDIS_KEY,
                    TTL_SECONDS,
                    json.dumps(rankings_data)
                )
                
                print(f"Batch {batch_id}: Saved {len(rankings_data)} top gainers to Redis")
                top3_str = ", ".join([f"{r['symbol']}: {r['percent_change']:.2f}%" for r in rankings_data[:3]])
                print(f"  Top 3: {top3_str}")
                success = True
                
            except (redis.ConnectionError, redis.TimeoutError, redis.RedisError) as e:
                print(f"Batch {batch_id}: Redis connection error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"Batch {batch_id}: Failed to connect to Redis after {max_retries} attempts. Skipping this batch.")
            except Exception as e:
                print(f"Batch {batch_id}: Unexpected error connecting to Redis: {e}")
                raise
            finally:
                # Always close connection if it was created
                if redis_client:
                    try:
                        redis_client.close()
                    except:
                        pass
            
            if success:
                break  # Success, exit retry loop
        
        if not success:
            print(f"Batch {batch_id}: Could not save to Redis after {max_retries} attempts. Continuing with next batch.")
            
    except Exception as e:
        print(f"Batch {batch_id}: Error processing batch: {e}")
        import traceback
        traceback.print_exc()

# Start streaming query
query = agg_df.writeStream \
    .outputMode("complete") \
    .foreachBatch(process_batch) \
    .option("checkpointLocation", CHECKPOINT_PATH) \
    .trigger(processingTime='1 minute') \
    .start()

print("=" * 80)
print("Top Gainers Ranking Streaming Job Started")
print(f"Kafka Broker: {KAFKA_BROKER}")
print(f"Kafka Topic: {KAFKA_TOPIC}")
print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
print(f"Redis Key: {REDIS_KEY}")
print(f"TTL: {TTL_SECONDS} seconds")
print(f"Checkpoint: {CHECKPOINT_PATH}")
print("=" * 80)

query.awaitTermination()


