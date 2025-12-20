from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, min, max, desc, to_json, struct, count
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StringType, DoubleType, LongType, StructField

KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "crypto_kline_1m"
SPARK_KAFKA_PACKAGE = 'org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0'
CHECKPOINT_PATH = "/tmp/spark/gainers_1m_cp"

KLINE_SCHEMA = StructType([
    StructField("s", StringType()),   # symbol
    StructField("c", StringType()),   # close price
    StructField("t", LongType()),     # timestamp (ms)
])

spark = SparkSession.builder \
    .appName("TopGainers1m") \
    .config("spark.jars.packages", SPARK_KAFKA_PACKAGE) \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# Read data from Kafka
raw_kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .load()

# Parse JSON
kline_df = raw_kafka_df.selectExpr("CAST(value AS STRING) as json_value") \
    .select(F.from_json(col("json_value"), KLINE_SCHEMA).alias("data")) \
    .select("data.*")

processed_df = kline_df \
    .withColumn("close_price_num", col("c").cast(DoubleType())) \
    .filter(col("close_price_num").isNotNull()) \
    .withColumn("event_ts", (col("t")/1000).cast("timestamp"))

# 1-minute window aggregation: open and close price
gainers_1m = processed_df \
    .withWatermark("event_ts", "2 minutes") \
    .groupBy(F.window(col("event_ts"), "1 minute"), col("s")) \
    .agg(
        F.min(F.struct(col("t"), col("close_price_num"))).alias("first_struct"),
        F.max(F.struct(col("t"), col("close_price_num"))).alias("last_struct"),
        count("s").alias("trade_count")
    ) \
    .select(
        col("window").start.alias("window_start"),
        col("s"),
        col("first_struct").getField("close_price_num").alias("open_price"),
        col("last_struct").getField("close_price_num").alias("close_price"),
        ((col("last_struct").getField("close_price_num") - col("first_struct").getField("close_price_num"))
         / col("first_struct").getField("close_price_num") * 100).alias("percent_change"),
        col("trade_count")
    ) \
    .orderBy(desc("percent_change"))

# Query 1: write to console
console_query = gainers_1m.writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", "false") \
    .option("checkpointLocation", CHECKPOINT_PATH + "_console") \
    .trigger(processingTime='10 seconds') \
    .start()

# Query 2: write to Kafka (commented for now)
# output_df = gainers_1m.select(
#     col("s").alias("key"),
#     to_json(struct("window_start","s","open_price","close_price","percent_change","trade_count")).alias("value")
# )
#
# kafka_query = output_df.writeStream \
#     .outputMode("complete") \
#     .format("kafka") \
#     .option("kafka.bootstrap.servers", KAFKA_BROKER) \
#     .option("topic", "crypto_gainers_1m") \
#     .option("checkpointLocation", CHECKPOINT_PATH + "_kafka") \
#     .start()

console_query.awaitTermination()
# kafka_query.awaitTermination()
