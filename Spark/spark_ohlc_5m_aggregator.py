"""
PySpark Streaming: Aggregate OHLC 5 phút từ kline 1 phút
- Đọc từ Kafka
- Filter kline đã đóng (x=true)
- Aggregate 5 kline 1m → 1 kline 5m
- Lưu vào Redis và MongoDB
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, window, first, last, max, min, sum
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StringType, DoubleType, BooleanType, LongType
)
import os

# Config
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "192.168.49.2:30113")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "crypto_kline_1m")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "crypto_history")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "candles")
CHECKPOINT_LOCATION = os.getenv("CHECKPOINT_LOCATION", "/tmp/spark_ohlc_5m_checkpoint")

# Spark Session
spark = SparkSession.builder \
    .appName("CryptoOHLC5mAggregator") \
    .config("spark.jars.packages", 
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
        "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1") \
    .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Schema
kline_schema = StructType() \
    .add("t", LongType(), True) \
    .add("T", LongType(), True) \
    .add("s", StringType(), True) \
    .add("i", StringType(), True) \
    .add("o", StringType(), True) \
    .add("c", StringType(), True) \
    .add("h", StringType(), True) \
    .add("l", StringType(), True) \
    .add("v", StringType(), True) \
    .add("q", StringType(), True) \
    .add("n", LongType(), True) \
    .add("x", BooleanType(), True)

# Đọc từ Kafka
kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "latest") \
    .load()

# Parse và transform
kline_df = kafka_df \
    .selectExpr("CAST(value AS STRING) as json_value") \
    .select(from_json(col("json_value"), kline_schema).alias("data")) \
    .select(
        col("data.t").alias("open_time"),
        col("data.T").alias("close_time"),
        col("data.s").alias("symbol"),
        col("data.i").alias("interval"),
        col("data.o").cast(DoubleType()).alias("open"),
        col("data.c").cast(DoubleType()).alias("close"),
        col("data.h").cast(DoubleType()).alias("high"),
        col("data.l").cast(DoubleType()).alias("low"),
        col("data.v").cast(DoubleType()).alias("volume"),
        col("data.q").cast(DoubleType()).alias("quote_volume"),
        col("data.n").alias("trades"),
        col("data.x").alias("is_closed")
    ) \
    .filter(col("is_closed") == True) \
    .withColumn("event_time", (col("open_time") / 1000).cast("timestamp"))

# Aggregate OHLC 5 phút
ohlc_5m = kline_df \
    .withWatermark("event_time", "10 minutes") \
    .groupBy(
        window(col("event_time"), "5 minutes"),
        col("symbol")
    ) \
    .agg(
        first("open_time").alias("open_time"),
        last("close_time").alias("close_time"),
        first("open").alias("open"),
        max("high").alias("high"),
        min("low").alias("low"),
        last("close").alias("close"),
        sum("volume").alias("volume"),
        sum("quote_volume").alias("quote_volume"),
        sum("trades").alias("trades")
    ) \
    .withColumn("interval", lit("5m")) \
    .withColumn("is_closed", lit(True)) \
    .select(
        col("symbol"),
        col("interval"),
        col("open_time"),
        col("close_time"),
        col("open"),
        col("high"),
        col("low"),
        col("close"),
        col("volume"),
        col("quote_volume"),
        col("trades"),
        col("is_closed"),
        col("window.start").alias("window_start"),
        col("window.end").alias("window_end")
    )

# Custom ForeachWriter để ghi vào Redis và MongoDB
class RedisMongoForeachWriter:
    """Ghi vào cả Redis và MongoDB"""
    
    def __init__(self, redis_host, redis_port, mongo_uri, mongo_db, mongo_collection):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.mongo_uri = mongo_uri
        self.mongo_db = mongo_db
        self.mongo_collection = mongo_collection
        self.redis_client = None
        self.mongo_client = None
        self.mongo_col = None
    
    def open(self, partition_id, epoch_id):
        """Mở kết nối"""
        import redis
        from pymongo import MongoClient
        
        # Redis
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=0,
            decode_responses=True
        )
        
        # MongoDB
        self.mongo_client = MongoClient(self.mongo_uri)
        self.mongo_col = self.mongo_client[self.mongo_db][self.mongo_collection]
        
        return True
    
    def process(self, row):
        """Xử lý từng row"""
        import json
        from datetime import datetime
        
        try:
            # Tạo Redis key
            redis_key = f"crypto:{row.symbol}:5m:{row.open_time}"
            
            # Tạo value
            redis_value = {
                "symbol": row.symbol,
                "interval": "5m",
                "open_time": row.open_time,
                "close_time": row.close_time,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
                "quote_volume": float(row.quote_volume) if row.quote_volume else 0,
                "trades": int(row.trades) if row.trades else 0,
                "is_closed": True,
                "created_at": datetime.now().isoformat()
            }
            
            # Lưu vào Redis
            self.redis_client.setex(redis_key, 86400 * 7, json.dumps(redis_value))
            
            # Index
            index_key = f"crypto:{row.symbol}:5m:index"
            self.redis_client.zadd(index_key, {str(row.open_time): row.open_time})
            self.redis_client.expire(index_key, 86400 * 30)
            
            # Latest
            latest_key = f"crypto:{row.symbol}:5m:latest"
            self.redis_client.setex(latest_key, 86400, json.dumps(redis_value))
            
            # Lưu vào MongoDB
            mongo_doc = {
                "symbol": row.symbol,
                "interval": "5m",
                "openTime": row.open_time,
                "closeTime": row.close_time,
                "open": float(row.open),
                "high": float(row.high),
                "low": float(row.low),
                "close": float(row.close),
                "volume": float(row.volume),
                "quoteVolume": float(row.quote_volume) if row.quote_volume else 0,
                "trades": int(row.trades) if row.trades else 0,
                "createdAt": datetime.now(),
                "source": "spark_streaming"
            }
            
            self.mongo_col.update_one(
                {
                    "symbol": mongo_doc["symbol"],
                    "interval": mongo_doc["interval"],
                    "openTime": mongo_doc["openTime"]
                },
                {"$set": mongo_doc},
                upsert=True
            )
            
        except Exception as e:
            print(f"❌ Lỗi khi ghi dữ liệu: {e}")
    
    def close(self, error):
        """Đóng kết nối"""
        if self.redis_client:
            self.redis_client.close()
        if self.mongo_client:
            self.mongo_client.close()

# Ghi vào Redis và MongoDB
query = ohlc_5m \
    .writeStream \
    .foreach(RedisMongoForeachWriter(
        REDIS_HOST, REDIS_PORT, 
        MONGO_URI, MONGO_DB, MONGO_COLLECTION
    )) \
    .outputMode("update") \
    .trigger(processingTime='1 minute') \
    .start()

print("=" * 80)
print("PySpark OHLC 5m Aggregator đã khởi động")
print(f"Kafka Broker: {KAFKA_BROKER}")
print(f"Topic: {KAFKA_TOPIC}")
print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
print(f"MongoDB: {MONGO_URI}/{MONGO_DB}/{MONGO_COLLECTION}")
print("=" * 80)
print("Đang aggregate OHLC 5m và ghi vào Redis + MongoDB...")
print("=" * 80)

query.awaitTermination()

