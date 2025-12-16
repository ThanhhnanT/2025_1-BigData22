from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, max, desc, current_timestamp
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StringType, DoubleType, LongType, BooleanType, StructField

KAFKA_BROKER = "192.168.49.2:30113" 
#KAFKA_BROKER = "localhost:9092"
KAFKA_TOPIC = "crypto_kline_1m"
SPARK_KAFKA_PACKAGE = 'org.apache.spark:spark-sql-kafka-0-10_2.12:3.2.0' 
CHECKPOINT_PATH = "/tmp/spark/realtime_ranking_cp"
KLINE_SCHEMA = StructType([
    StructField("s", StringType()),
    StructField("c", StringType()),
    StructField("t", LongType()),
])


spark = SparkSession.builder \
    .appName("RealtimeCoinRanking") \
    .config("spark.jars.packages", SPARK_KAFKA_PACKAGE) \
    .getOrCreate()
spark.sparkContext.setLogLevel("WARN")

raw_kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .load()

kline_df = raw_kafka_df.selectExpr("CAST(value AS STRING) as json_value") \
    .select(F.from_json(col("json_value"), KLINE_SCHEMA).alias("data")) \
    .select("data.*")
processed_df = kline_df \
    .withColumn("close_price_num", col("c").cast(DoubleType())) \
    #.filter(col("close_price_num").isNotNull())

ranking_df = processed_df \
    .groupBy("s") \
    .agg(
        F.max("close_price_num").alias("latest_price"), 
        F.count("s").alias("trade_count"),
        F.lit(current_timestamp()).alias("updated_at")
    ) \
    .orderBy(desc("latest_price")) 

# query = ranking_df.writeStream \
#     .outputMode("complete") \
#     .format("console") \
#     .option("truncate", "false") \
#     .option("checkpointLocation", CHECKPOINT_PATH) \
#     .trigger(processingTime='5 seconds') \
#     .start()

query = ranking_df.writeStream \
    .outputMode("update") \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("topic", "crypto_ranking") \
    .option("checkpointLocation", CHECKPOINT_PATH) \
    .start()

query.awaitTermination()