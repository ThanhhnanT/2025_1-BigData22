from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col
from pyspark.sql import functions as F
from pyspark.sql.types import StructType, StringType, DoubleType, BooleanType, LongType
from pprint import pprint

spark = SparkSession.builder \
    .appName("Crypto10mAggregator") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

schema = StructType() \
    .add("t", LongType()) \
    .add("T", LongType()) \
    .add("s", StringType()) \
    .add("i", StringType()) \
    .add("o", StringType()) \
    .add("c", StringType()) \
    .add("h", StringType()) \
    .add("l", StringType()) \
    .add("v", StringType()) \
    .add("x", BooleanType())

df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "192.168.49.2:30113") \
    .option("subscribe", "crypto_kline_1m") \
    .load() \
    .selectExpr("CAST(value AS STRING) as json_value")

print(df['json_value'])
exit(0)


kline_df = df.select(from_json(col("json_value"), schema).alias("data")) \
    .select(
        col("data.t").alias("event_start"),
        col("data.T").alias("event_end"),
        col("data.s").alias("symbol"),
        col("data.i").alias("interval"),
        col("data.o").alias("open"),
        col("data.c").alias("close"),
        col("data.h").alias("high"),
        col("data.l").alias("low"),
        col("data.v").alias("volume"),
        col("data.x").alias("closed")
    )

kline_df = kline_df.filter(F.col("closed") == True)

agg_df = kline_df \
    .withColumn("event_time", (F.col("event_start") / 1000).cast("timestamp")) \
    .groupBy(
        F.window(F.col("event_time"), "10 minutes"),
        F.col("symbol")
    ) \
    .agg(
        F.first("open").alias("open"),
        F.max("high").alias("high"),
        F.min("low").alias("low"),
        F.last("close").alias("close"),
        F.sum("volume").alias("volume")
    )

query = agg_df \
    .writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", False) \
    .start()

query.awaitTermination()
