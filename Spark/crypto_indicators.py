from pyspark.sql import SparkSession
from pyspark.sql.functions import col, lit
from pyspark.sql import DataFrame
from pyspark.sql.types import DoubleType, StructField
import pandas as pd

def calc_sma(df: DataFrame, price_col: str, timestamp_col: str, window_size: int) -> DataFrame:
    sma_col = f"sma_{window_size}"
    df_with = df.withColumn(sma_col, lit(None).cast(DoubleType()))
    output_schema = df_with.schema
    def sma_per_symbol(pdf: pd.DataFrame) -> pd.DataFrame:
        pdf = pdf.sort_values(by=timestamp_col)
        pdf[sma_col] = (
            pdf[price_col]
               .rolling(window_size, min_periods=1)
               .mean()
        )
        return pdf
    df_sma = df_with.groupBy("symbol").applyInPandas(sma_per_symbol, schema=output_schema)
    return df_sma

def calc_ema(df: DataFrame, price_col: str, timestamp_col: str, window_size: int) -> DataFrame:
    ema_col = f"ema_{window_size}"
    alpha = 2 / (window_size + 1)
    df_with = df.withColumn(ema_col, lit(None).cast(DoubleType()))
    output_schema = df_with.schema
    def ema_per_symbol(pdf: pd.DataFrame) -> pd.DataFrame:
        pdf = pdf.sort_values(by=timestamp_col)
        pdf[ema_col] = (
            pdf[price_col]
               .ewm(alpha=alpha, adjust=False)
               .mean()
        )
        return pdf
    df_ema = df_with.groupBy("symbol").applyInPandas(ema_per_symbol, schema=output_schema)
    return df_ema

def calc_rsi(df: DataFrame, price_col: str, timestamp_col: str, window_size: int) -> DataFrame:
    rsi_col = f"rsi_{window_size}"
    df_with = df.withColumn(rsi_col, lit(None).cast(DoubleType()))
    output_schema = df_with.schema
    def compute_rsi(prices: pd.Series) -> pd.Series:
        delta = prices.diff()
        avg_gain = (delta.where(delta > 0, 0)).rolling(window_size).mean()
        avg_loss = (-delta.where(delta < 0, 0)).rolling(window_size).mean()
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    def rsi_per_symbol(pdf: pd.DataFrame) -> pd.DataFrame:
        pdf = pdf.sort_values(by=timestamp_col)
        pdf[rsi_col] = compute_rsi(pdf[price_col])
        return pdf
    df_rsi = df_with.groupBy("symbol").applyInPandas(rsi_per_symbol, schema=output_schema)
    return df_rsi

def calc_macd(df: DataFrame, price_col: str, timestamp_col: str, short_window: int = 12, long_window: int = 26, signal_window: int = 9) -> DataFrame:
    short_ema_col = f"ema_{short_window}"
    long_ema_col = f"ema_{long_window}"
    macd_col = "macd"
    signal_col = "macd_signal"
    df_with = (
        df.withColumn(short_ema_col, lit(None).cast(DoubleType()))
          .withColumn(long_ema_col, lit(None).cast(DoubleType()))
          .withColumn(macd_col, lit(None).cast(DoubleType()))
          .withColumn(signal_col, lit(None).cast(DoubleType()))
    )
    output_schema = df_with.schema
    def macd_per_symbol(pdf: pd.DataFrame) -> pd.DataFrame:
        pdf = pdf.sort_values(by=timestamp_col)
        alpha_short = 2 / (short_window + 1)
        alpha_long = 2 / (long_window + 1)
        pdf[short_ema_col] = pdf[price_col].ewm(alpha=alpha_short, adjust=False).mean()
        pdf[long_ema_col] = pdf[price_col].ewm(alpha=alpha_long, adjust=False).mean()
        pdf[macd_col] = pdf[short_ema_col] - pdf[long_ema_col]
        pdf[signal_col] = pdf[macd_col].ewm(alpha=2 / (signal_window + 1), adjust=False).mean()
        return pdf
    df_macd = df_with.groupBy("symbol").applyInPandas(macd_per_symbol, schema=output_schema)
    return df_macd

def calc_bollinger_bands(df: DataFrame, price_col: str, timestamp_col: str, window_size: int, num_std_dev: float = 2.0) -> DataFrame:
    upper_band_col = f"bb_upper_{window_size}"
    lower_band_col = f"bb_lower_{window_size}"
    df_with = (
        df.withColumn(upper_band_col, lit(None).cast(DoubleType()))
          .withColumn(lower_band_col, lit(None).cast(DoubleType()))
    )
    output_schema = df_with.schema
    def bollinger_per_symbol(pdf: pd.DataFrame) -> pd.DataFrame:
        pdf = pdf.sort_values(by=timestamp_col)
        rolling_mean = pdf[price_col].rolling(window=window_size, min_periods=1).mean()
        rolling_std = pdf[price_col].rolling(window=window_size, min_periods=1).std()
        pdf[upper_band_col] = rolling_mean + (rolling_std * num_std_dev)
        pdf[lower_band_col] = rolling_mean - (rolling_std * num_std_dev)
        return pdf
    df_bollinger = df_with.groupBy("symbol").applyInPandas(bollinger_per_symbol, schema=output_schema)
    return df_bollinger

if __name__ == "__main__":
    MONGO_INPUT_URI = "mongodb://localhost:27017/crypto_history.candles"
    MONGO_OUTPUT_URI = "mongodb://localhost:27017/crypto_history.indicators_results"
    spark = (
        SparkSession.builder
        .appName("CryptoIndicatorsComputation")
        .config("spark.jars.packages", "org.mongodb.spark:mongo-spark-connector_2.12:3.0.1")
        .getOrCreate()
    )

    print("Reading data from MongoDB...")
    df_history = (
        spark.read.format("mongo")
        .option("uri", MONGO_INPUT_URI)
        .load()
    )
    df_clean = (
        df_history
        .withColumn("_id", col("_id.oid"))
        .withColumn("close_price_num", col("close").cast(DoubleType()))
        .withColumn("openTime_ts", (col("openTime") / 1000).cast("timestamp"))
        .filter(col("close_price_num").isNotNull())
    )
    print("Calculating indicator...")

    df_sma = calc_sma(
        df_clean,
        price_col="close_price_num",
        timestamp_col="openTime_ts",
        window_size=14
    )

    df_ema = calc_ema(
        df_sma,
        price_col="close_price_num",
        timestamp_col="openTime_ts",
        window_size=14
    )

    df_rsi = calc_rsi(
        df_ema,
        price_col="close_price_num",
        timestamp_col="openTime_ts",
        window_size=14
    )

    df_bb = calc_bollinger_bands(
        df_rsi,
        price_col="close_price_num",
        timestamp_col="openTime_ts",
        window_size=14
    )

    df_macd = calc_macd(
        df_bb,
        price_col="close_price_num",
        timestamp_col="openTime_ts"
    )

    print("Writing results back to MongoDB...")
    (
        df_macd.write
        .format("mongo")
        .mode("overwrite")
        .option("uri", MONGO_OUTPUT_URI)
        .option("collection", "indicators_results")
        .save()
    )
    print("Done.")
    spark.stop()

