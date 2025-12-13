from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, max
from pyspark.sql.types import (StructType, StructField, StringType, 
                               DoubleType, TimestampType, LongType)
import os

os.environ['HADOOP_HOME'] = 'C:\\hadoop'

KAFKA_TOPIC = 'crypto-topic'
KAFKA_SERVER = 'localhost:9092'
SPARK_KAFKA_PACKAGE = 'org.apache.spark:spark-sql-kafka-0-10_2.12:3.3.0'
CHECKPOINT_LOCATION = "C:\\tmp\\spark_checkpoint"

print("Starting Spark session with Kafka package...")
spark = SparkSession.builder \
    .appName("KafkaStreamConsumer") \
    .config("spark.jars.packages", SPARK_KAFKA_PACKAGE) \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

schema = StructType([
    StructField("symbol", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("quantity", DoubleType(), True),
    StructField("event_time", LongType(), True)
])

raw_kafka_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_SERVER) \
    .option("subscribe", KAFKA_TOPIC) \
    .load()

df = raw_kafka_df.selectExpr("CAST(value AS STRING)") \
    .withColumn("data", from_json(col("value"), schema)) \
    .select("data.*")

processed_df = df.withColumn(
    "event_time_ts", 
    (col("event_time") / 1000).cast(TimestampType())
)

ranking_df = processed_df \
    .groupBy("symbol") \
    .agg(max("price").alias("latest_price")) \
    .orderBy(col("latest_price").desc())

query = ranking_df.writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", "false") \
    .start()

print(f"Spark is now listening to Kafka topic '{KAFKA_TOPIC}'...")
query.awaitTermination()