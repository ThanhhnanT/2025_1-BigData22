from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, TimestampType
from pyspark.sql.functions import col

spark = SparkSession.builder \
    .appName("RankStreamConsumer") \
    .getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

schema = StructType([
    StructField("timestamp", StringType(), True),
    StructField("ticker", StringType(), True),
    StructField("price", DoubleType(), True),
    StructField("volume", DoubleType(), True)
])

raw_df = spark.readStream \
    .option("header", "true") \
    .schema(schema) \
    .csv("streaming_test_data")

processed_df = raw_df.withColumn("timestamp", col("timestamp").cast(TimestampType())) 
price_ranking_df = processed_df \
    .select("ticker", "price") \
    .orderBy(col("price").desc())
query = price_ranking_df.writeStream \
    .outputMode("complete") \
    .format("console") \
    .option("truncate", "false") \
    .start()
query.awaitTermination()