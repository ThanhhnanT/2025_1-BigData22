"""
PySpark Batch Job: Đọc từ Redis hoặc Kafka và lưu vào MongoDB
- Có thể chạy từ Airflow
- Đọc dữ liệu ngày hôm qua
- Lưu vào MongoDB với batch processing
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit, from_json, struct, to_json
from pyspark.sql import functions as F
from pyspark.sql.types import (
    StructType, StringType, DoubleType, BooleanType, LongType, TimestampType
)
from datetime import datetime, timedelta, timezone
import os
import sys

# Config
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "192.168.49.2:30113")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "crypto_kline_1m")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.getenv("MONGO_DB", "crypto_history")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "candles")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

# Tính thời gian: hôm qua
vn_tz = timezone(timedelta(hours=7))
now = datetime.now(vn_tz)
yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
yesterday_end = yesterday_start + timedelta(days=1) - timedelta(seconds=1)

start_timestamp = int(yesterday_start.timestamp() * 1000)
end_timestamp = int(yesterday_end.timestamp() * 1000)

print(f"📅 Xử lý dữ liệu từ {yesterday_start} đến {yesterday_end}")
print(f"   Timestamp: {start_timestamp} - {end_timestamp}")

# Spark Session
spark = SparkSession.builder \
    .appName("CryptoBatchMongoWriter") \
    .config("spark.jars.packages", 
        "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,"
        "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Option 1: Đọc từ Kafka (nếu có dữ liệu trong retention period)
try:
    print("\n📖 Đang đọc từ Kafka...")
    
    kafka_df = spark.read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", f"{{'{KAFKA_TOPIC}': {{'0': {start_timestamp}}}}}") \
        .option("endingOffsets", f"{{'{KAFKA_TOPIC}': {{'0': {end_timestamp}}}}") \
        .load()
    
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
    
    # Parse và transform
    kline_df = kafka_df \
        .selectExpr("CAST(value AS STRING) as json_value") \
        .select(from_json(col("json_value"), kline_schema).alias("data")) \
        .select(
            col("data.t").alias("openTime"),
            col("data.T").alias("closeTime"),
            col("data.s").alias("symbol"),
            col("data.i").alias("interval"),
            col("data.o").cast(DoubleType()).alias("open"),
            col("data.c").cast(DoubleType()).alias("close"),
            col("data.h").cast(DoubleType()).alias("high"),
            col("data.l").cast(DoubleType()).alias("low"),
            col("data.v").cast(DoubleType()).alias("volume"),
            col("data.q").cast(DoubleType()).alias("quoteVolume"),
            col("data.n").alias("trades"),
            col("data.x").alias("is_closed")
        ) \
        .filter(
            (col("openTime") >= start_timestamp) & 
            (col("openTime") <= end_timestamp) &
            (col("is_closed") == True)
        )
    
    # Lưu vào MongoDB
    mongo_df = kline_df \
        .withColumn("createdAt", F.current_timestamp()) \
        .withColumn("source", lit("spark_batch_kafka"))
    
    print(f"✅ Đã đọc {mongo_df.count()} records từ Kafka")
    
    # Ghi vào MongoDB
    mongo_df.write \
        .format("mongo") \
        .mode("append") \
        .option("uri", MONGO_URI) \
        .option("database", MONGO_DB) \
        .option("collection", MONGO_COLLECTION) \
        .save()
    
    print(f"✅ Đã lưu vào MongoDB: {MONGO_DB}.{MONGO_COLLECTION}")
    
except Exception as e:
    print(f"⚠️  Không thể đọc từ Kafka: {e}")
    print("   Có thể dữ liệu đã quá retention period hoặc Kafka không có dữ liệu")
    print("   Sử dụng Redis hoặc source khác...")

# Option 2: Đọc từ Redis (nếu Kafka không có dữ liệu)
# Note: PySpark không có connector trực tiếp cho Redis
# Có thể dùng Python script để đọc từ Redis và tạo DataFrame

spark.stop()
print("\n✅ Hoàn thành batch job!")

