from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, max, desc, to_json, struct
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StringType, DoubleType, LongType, StructField
from pyspark.sql.window import Window

KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "crypto_kline_1m"
SPARK_KAFKA_PACKAGE = 'org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0'
CHECKPOINT_PATH = "/tmp/spark/rolling_change_cp"

KLINE_SCHEMA = StructType([
    StructField("s", StringType()),   # symbol
    StructField("c", StringType()),   # close price
    StructField("t", LongType()),     # timestamp (ms)
])

spark = SparkSession.builder \
    .appName("RollingChangeRanking") \
    .config("spark.jars.packages", SPARK_KAFKA_PACKAGE) \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

# Read from Kafka
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

# Aggregate: lấy giá close mới nhất trong mỗi cửa sổ 5 phút
agg_df = processed_df \
    .withWatermark("event_ts", "2 minutes") \
    .groupBy(F.window(col("event_ts"), "1 minutes"), col("s")) \
    .agg(F.max(F.struct(col("t"), col("close_price_num"))).alias("latest_struct")) \
    .select(
        col("s"),
        col("window").start.alias("window_start"),
        col("latest_struct").getField("close_price_num").alias("close_price")
    )

# foreachBatch để tính rolling % change
def process_batch(batch_df, batch_id):
    if batch_df.rdd.isEmpty():
        return
    w = Window.partitionBy("s").orderBy("window_start")
    result = batch_df.withColumn("prev_close", F.lag("close_price").over(w)) \
                     .withColumn("percent_change",
                                 ((col("close_price") - col("prev_close")) / col("prev_close") * 100))
    ranked = result.orderBy(F.desc("percent_change"))
    print(f"=== Batch {batch_id} ===")
    ranked.show(truncate=False)

# Query 1: console (bật mặc định)
console_query = agg_df.writeStream \
    .outputMode("complete") \
    .foreachBatch(process_batch) \
    .option("checkpointLocation", CHECKPOINT_PATH + "_console") \
    .trigger(processingTime='1 minute') \
    .start()



console_query.awaitTermination()


