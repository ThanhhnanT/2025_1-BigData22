from pyspark.sql import SparkSession
from pyspark.sql.functions import col, avg, to_timestamp, lit
from pyspark.sql.window import Window
from pyspark.sql.types import DoubleType, StructType, LongType, StructField
from pyspark.sql import DataFrame
import pandas as pd
from pyspark.sql.functions import pandas_udf

def calc_sma(df: DataFrame, price_col: str, timestamp_col: str, window_size: int, spark: SparkSession) -> DataFrame:
    sma_col = f"sma_{window_size}"
    df_tmp = df.withColumn(timestamp_col, col(timestamp_col).cast("long"))
    pdf = (
        df_tmp
        .orderBy("symbol", timestamp_col)
        .toPandas()
    )
    pdf[sma_col] = (
        pdf.groupby("symbol")[price_col]
           .transform(lambda s: s.rolling(window_size, min_periods=1).mean())
    )
    df_spark = spark.createDataFrame(pdf)
    df_spark = df_spark.withColumn(timestamp_col, col(timestamp_col).cast("timestamp"))

    return df_spark

def calc_ema(df: DataFrame, price_col: str, timestamp_col: str, window_size: int, spark: SparkSession) -> DataFrame:  
    alpha = 2 / (window_size + 1)
    ema_col = f"ema_{window_size}"
    df_tmp = df.withColumn(timestamp_col, col(timestamp_col).cast("long"))
    pdf = (
        df_tmp
        .orderBy("symbol", timestamp_col)
        .toPandas()
    )
    pdf[ema_col] = (
        pdf.groupby("symbol")[price_col]
           .transform(lambda s: s.ewm(alpha=alpha, adjust=False).mean())
           #.reset_index(level=0, drop=True)
    )

    df_spark = spark.createDataFrame(pdf)
    df_spark = df_spark.withColumn(timestamp_col, col(timestamp_col).cast("timestamp"))

    return df_spark

def calc_rsi(df: DataFrame, price_col: str, timestamp_col: str, window_size: int, spark: SparkSession) -> DataFrame:
    rsi_col = f"rsi_{window_size}"
    df_tmp = df.withColumn(timestamp_col, col(timestamp_col).cast("long"))
    pdf = (
        df_tmp
        .orderBy("symbol", timestamp_col)
        .toPandas()
    )
    def compute_rsi(prices: pd.Series) -> pd.Series:
        delta = prices.diff()
        avg_gain = (delta.where(delta > 0, 0)).rolling(window_size).mean()
        avg_loss = (-delta.where(delta < 0, 0)).rolling(window_size).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    pdf[rsi_col] = (
        pdf.groupby("symbol")[price_col]
           .transform(compute_rsi)
    )
    df_spark = spark.createDataFrame(pdf)
    df_spark = df_spark.withColumn(timestamp_col, col(timestamp_col).cast("timestamp"))

    return df_spark

def calc_bollinger_bands(df: DataFrame, price_col: str, timestamp_col: str, window_size: int, num_stddev: float, spark: SparkSession) -> DataFrame:
    upper_band_col = f"bollinger_upper_{window_size}"
    lower_band_col = f"bollinger_lower_{window_size}"
    df_tmp = df.withColumn(timestamp_col, col(timestamp_col).cast("long"))
    pdf = (
        df_tmp
        .orderBy("symbol", timestamp_col)
        .toPandas()
    )
    def compute_bollinger_bands(prices: pd.Series) -> pd.DataFrame:
        rolling_mean = prices.rolling(window_size).mean()
        rolling_std = prices.rolling(window_size).std()
        upper_band = rolling_mean + (rolling_std * num_stddev)
        lower_band = rolling_mean - (rolling_std * num_stddev)
        return pd.DataFrame({upper_band_col: upper_band, lower_band_col: lower_band})
    bb_df = (
        pdf.groupby("symbol")[price_col]
           .apply(compute_bollinger_bands)
           .reset_index(level=0, drop=True)
    )
    pdf[upper_band_col] = bb_df[upper_band_col]
    pdf[lower_band_col] = bb_df[lower_band_col]
    df_spark = spark.createDataFrame(pdf)
    df_spark = df_spark.withColumn(timestamp_col, col(timestamp_col).cast("timestamp"))
    
    return df_spark
    
def calc_macd(df: DataFrame, price_col: str, timestamp_col: str, short_window: int, long_window: int, signal_window: int, spark: SparkSession) -> DataFrame:
    short_ema_col = f"ema_{short_window}"
    long_ema_col = f"ema_{long_window}"
    macd_col = "macd"
    signal_col = "macd_signal"
    df_tmp = df.withColumn(timestamp_col, col(timestamp_col).cast("long"))
    pdf = (
        df_tmp
        .orderBy("symbol", timestamp_col)
        .toPandas()
    )
    def compute_macd(prices: pd.Series) -> pd.DataFrame:
        short_ema = prices.ewm(span=short_window, adjust=False).mean()
        long_ema = prices.ewm(span=long_window, adjust=False).mean()
        macd = short_ema - long_ema
        signal = macd.ewm(span=signal_window, adjust=False).mean()
        return pd.DataFrame({short_ema_col: short_ema, long_ema_col: long_ema, macd_col: macd, signal_col: signal})
    macd_df = (
        pdf.groupby("symbol")[price_col]
           .apply(compute_macd)
           .reset_index(level=0, drop=True)
    )
    pdf[long_ema_col] = macd_df[long_ema_col]
    pdf[short_ema_col] = macd_df[short_ema_col]
    pdf[macd_col] = macd_df[macd_col]
    pdf[signal_col] = macd_df[signal_col]
    df_spark = spark.createDataFrame(pdf)
    df_spark = df_spark.withColumn(timestamp_col, col(timestamp_col).cast("timestamp"))

    return df_spark

if __name__ == "__main__":
    MONGO_INPUT_URI = "mongodb://localhost:27017/crypto_history.candles"
    MONGO_OUTPUT_URI = "mongodb://localhost:27017/crypto_history.indicators_results"
    spark = SparkSession.builder \
        .appName("Crypto Indicators") \
        .config("spark.jars.packages", "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1") \
        .getOrCreate()
    
    print("Reading data from MongoDB...")

    df_history = spark.read \
        .format("mongo") \
        .option("uri", MONGO_INPUT_URI) \
        .load()
    
    # df_clean = df_history \
    #     .withColumn("close_price_num", col("close").cast(DoubleType())) \
    #     .withColumn("openTime_ts", (col("openTime") / 1000).cast("timestamp")) \
    #     .filter(col("close_price_num").isNotNull())
    
    df_clean = df_history \
        .withColumn("close_price_num", col("close").cast(DoubleType())) \
        .withColumn("openTime_ts", (col("openTime") / 1000).cast("timestamp")) \
        .filter(col("close_price_num").isNotNull())
        # .select(
        #     "symbol", 
        #     "openTime_ts", 
        #     "close_price_num",
        #     "open", 
        #     "high", 
        #     "low", 
        #     "volume", 
        #     "openTime" 
        # )

    print("Calculating indicators...")
    df_sma = calc_sma(df_clean,
                        price_col="close_price_num",
                        timestamp_col="openTime_ts",
                        window_size=14,
                        spark=spark)
    
    df_ema = calc_ema(df_sma, 
                        price_col="close_price_num", 
                        timestamp_col="openTime_ts", 
                        window_size=12,
                        spark=spark) 
    
    df_rsi = calc_rsi(df_ema, 
                        price_col="close_price_num", 
                        timestamp_col="openTime_ts", 
                        window_size=14,
                        spark=spark)
    
    df_bb = calc_bollinger_bands(
        df_rsi,
        price_col="close_price_num",
        timestamp_col="openTime_ts",
        window_size=20,
        num_stddev=2,
        spark=spark
    )

    df_macd = calc_macd(
        df_bb,
        price_col="close_price_num",
        timestamp_col="openTime_ts",
        short_window=12,
        long_window=26,
        signal_window=9,
        spark=spark
    )
    
    print("Writing results back to MongoDB...")
    df_macd.write \
        .format("mongo") \
        .mode("overwrite") \
        .option("uri", MONGO_OUTPUT_URI) \
        .option("collection", "indicators_results") \
        .save()
    
    print("Done.")
    spark.stop()

