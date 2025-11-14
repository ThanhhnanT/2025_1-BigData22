"""
PySpark Streaming: Đọc từ Kafka và lưu vào Redis
- Filter kline khi x=true (đã đóng)
- Lưu vào Redis với structured data
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, when, lit, struct
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StringType, DoubleType, BooleanType, 
    LongType, TimestampType
)
import os

# Config
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "192.168.49.2:30113")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "crypto_kline_1m")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
CHECKPOINT_LOCATION = os.getenv("CHECKPOINT_LOCATION", "/tmp/spark_redis_checkpoint")

# Spark Session với Kafka package
spark = SparkSession.builder \
    .appName("CryptoRedisWriter") \
    .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0") \
    .config("spark.sql.streaming.checkpointLocation", CHECKPOINT_LOCATION) \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Schema cho kline data từ Binance
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

# Parse JSON và transform
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
        col("data.x").alias("is_closed"),
        F.current_timestamp().alias("processed_at")
    )

# Filter chỉ lấy kline đã đóng (x=true)
closed_klines = kline_df.filter(col("is_closed") == True)

# Tạo Redis key và value
redis_data = closed_klines \
    .withColumn("redis_key", 
        F.concat(
            lit("crypto:"),
            col("symbol"),
            lit(":1m:"),
            col("open_time").cast(StringType())
        )
    ) \
    .withColumn("redis_value",
        F.to_json(
            struct(
                col("symbol"),
                lit("1m").alias("interval"),
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
                F.date_format(col("processed_at"), "yyyy-MM-dd HH:mm:ss").alias("updated_at")
            )
        )
    ) \
    .select("redis_key", "redis_value", "symbol", "open_time", "is_closed")

# Custom ForeachWriter để ghi vào Redis
class RedisForeachWriter:
    """Custom ForeachWriter để ghi dữ liệu vào Redis"""
    
    def __init__(self, redis_host, redis_port):
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_client = None
    
    def open(self, partition_id, epoch_id):
        """Mở kết nối Redis"""
        import redis
        self.redis_client = redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            db=0,
            decode_responses=True
        )
        return True
    
    def process(self, row):
        """Xử lý từng row"""
        try:
            key = row.redis_key
            value = row.redis_value
            
            # Lưu vào Redis với TTL 24h
            self.redis_client.setex(key, 86400, value)
            
            # Lưu vào sorted set index
            index_key = f"crypto:{row.symbol}:1m:index"
            self.redis_client.zadd(index_key, {str(row.open_time): row.open_time})
            self.redis_client.expire(index_key, 86400 * 7)  # 7 ngày
            
            # Lưu latest
            latest_key = f"crypto:{row.symbol}:1m:latest"
            self.redis_client.setex(latest_key, 86400, value)
            
        except Exception as e:
            print(f"❌ Lỗi khi ghi vào Redis: {e}")
    
    def close(self, error):
        """Đóng kết nối Redis"""
        if self.redis_client:
            self.redis_client.close()

# Ghi vào Redis
query = redis_data \
    .writeStream \
    .foreach(RedisForeachWriter(REDIS_HOST, REDIS_PORT)) \
    .outputMode("append") \
    .trigger(processingTime='10 seconds') \
    .start()

print("=" * 80)
print("PySpark Redis Writer đã khởi động")
print(f"Kafka Broker: {KAFKA_BROKER}")
print(f"Topic: {KAFKA_TOPIC}")
print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
print("=" * 80)
print("Đang lắng nghe và ghi vào Redis...")
print("=" * 80)

query.awaitTermination()

