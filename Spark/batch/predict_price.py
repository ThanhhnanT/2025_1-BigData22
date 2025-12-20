#!/usr/bin/env python3
"""
Real-time Price Prediction - Inference
Loads trained model and predicts next 5-minute price movement
"""

import os
import sys
import json
from datetime import datetime, timezone, timedelta
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lag, avg, stddev,
    when, lit, current_timestamp, greatest, least
)
from pyspark.sql.window import Window
from pyspark.ml import PipelineModel
from pymongo import MongoClient
import redis

# Configuration
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://vuongthanhsaovang:9KviWHBS85W7i4j6@ai-tutor.k6sjnzc.mongodb.net")
MONGO_DB = os.getenv("MONGO_DB", "CRYPTO")
MONGO_INPUT_COLLECTION = os.getenv("MONGO_INPUT_COLLECTION", "5m_kline")
MONGO_PREDICTION_COLLECTION = os.getenv("MONGO_PREDICTION_COLLECTION", "predictions")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
ENABLE_REDIS = os.getenv("ENABLE_REDIS", "1") == "1"

MODEL_PATH = os.getenv("MODEL_PATH", "/tmp/crypto_lr_model")
LOOKBACK_PERIODS = 30  # Need historical data for feature calculation

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
    "XRPUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT",
    "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "ETCUSDT"
]


def fetch_recent_data(mongo_uri, db_name, collection_name, symbols, periods=30):
    """Fetch recent OHLC data for prediction"""
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    
    # Get latest data
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(minutes=5 * periods)
    start_timestamp = int(start_time.timestamp() * 1000)
    
    query = {
        "symbol": {"$in": symbols},
        "interval": "5m",
        "openTime": {"$gte": start_timestamp}
    }
    
    cursor = collection.find(query).sort("openTime", 1)
    data = list(cursor)
    client.close()
    
    return data


def fetch_latest_k_per_symbol(mongo_uri, db_name, collection_name, symbols, k=40):
    """Fallback: fetch the latest K candles per symbol regardless of time"""
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    out = []
    for sym in symbols:
        cursor = (
            collection.find({"symbol": sym, "interval": "5m"})
            .sort("openTime", -1)
            .limit(k)
        )
        docs = list(cursor)
        if docs:
            docs.reverse()  # ascending by time
            out.extend(docs)
    client.close()
    return out


def normalize_mongo_docs(docs):
    """Normalize Mongo documents for Spark DataFrame creation.
    - Drop `_id` ObjectId and any non-required fields
    - Cast numeric types to native int/float
    - Keep only fields used downstream
    """
    required_keys = [
        "symbol", "interval", "openTime", "open", "high", "low", "close", "volume"
    ]
    normalized = []
    for d in docs:
        if not isinstance(d, dict):
            continue
        nd = dict(d)
        nd.pop("_id", None)
        # Keep only required keys
        nd = {k: nd.get(k) for k in required_keys}
        # Cast types
        if nd.get("symbol") is not None:
            nd["symbol"] = str(nd["symbol"])
        if nd.get("interval") is not None:
            nd["interval"] = str(nd["interval"])
        for tkey in ["openTime"]:
            if nd.get(tkey) is not None:
                try:
                    nd[tkey] = int(nd[tkey])
                except Exception:
                    pass
        for fkey in ["open", "high", "low", "close", "volume"]:
            if nd.get(fkey) is not None:
                try:
                    nd[fkey] = float(nd[fkey])
                except Exception:
                    pass
        normalized.append(nd)
    return normalized


def create_features(df):
    """Create same features as training"""
    window_spec = Window.partitionBy("symbol").orderBy("openTime")
    
    # Basic price features
    df = df.withColumn("price_range", col("high") - col("low"))
    df = df.withColumn("body_size", col("close") - col("open"))
    df = df.withColumn("upper_shadow", col("high") - greatest(col("open"), col("close")))
    df = df.withColumn("lower_shadow", least(col("open"), col("close")) - col("low"))
    
    # Price change features
    df = df.withColumn("close_lag1", lag("close", 1).over(window_spec))
    df = df.withColumn("close_lag2", lag("close", 2).over(window_spec))
    df = df.withColumn("close_lag3", lag("close", 3).over(window_spec))
    
    df = df.withColumn("return_1", 
                       when(col("close_lag1").isNotNull(), 
                            (col("close") - col("close_lag1")) / col("close_lag1") * 100)
                       .otherwise(0))
    
    df = df.withColumn("return_2", 
                       when(col("close_lag2").isNotNull(), 
                            (col("close") - col("close_lag2")) / col("close_lag2") * 100)
                       .otherwise(0))
    
    # Moving averages
    df = df.withColumn("ma5", avg("close").over(window_spec.rowsBetween(-4, 0)))
    df = df.withColumn("ma10", avg("close").over(window_spec.rowsBetween(-9, 0)))
    df = df.withColumn("ma20", avg("close").over(window_spec.rowsBetween(-19, 0)))
    
    # Volatility
    df = df.withColumn("volatility_5", stddev("close").over(window_spec.rowsBetween(-4, 0)))
    df = df.withColumn("volatility_10", stddev("close").over(window_spec.rowsBetween(-9, 0)))
    
    # Volume features
    df = df.withColumn("volume_ma5", avg("volume").over(window_spec.rowsBetween(-4, 0)))
    df = df.withColumn("volume_ratio", 
                       when(col("volume_ma5") > 0, col("volume") / col("volume_ma5"))
                       .otherwise(1.0))
    
    # Price position in MA
    df = df.withColumn("price_to_ma5", 
                       when(col("ma5") > 0, (col("close") - col("ma5")) / col("ma5") * 100)
                       .otherwise(0))
    df = df.withColumn("price_to_ma20", 
                       when(col("ma20") > 0, (col("close") - col("ma20")) / col("ma20") * 100)
                       .otherwise(0))
    
    # RSI-like momentum
    df = df.withColumn("gain", when(col("return_1") > 0, col("return_1")).otherwise(0))
    df = df.withColumn("loss", when(col("return_1") < 0, -col("return_1")).otherwise(0))
    
    df = df.withColumn("avg_gain", avg("gain").over(window_spec.rowsBetween(-13, 0)))
    df = df.withColumn("avg_loss", avg("loss").over(window_spec.rowsBetween(-13, 0)))
    
    df = df.withColumn("rsi", 
                       when(col("avg_loss") > 0, 
                            100 - (100 / (1 + col("avg_gain") / col("avg_loss"))))
                       .otherwise(50))
    
    return df


def main():
    """Main prediction pipeline"""
    print("=" * 80)
    print("Crypto Price Prediction - Real-time Inference")
    print("=" * 80)
    
    # Ensure Spark uses the current Python interpreter (Windows fix)
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    
    # Initialize Spark
    spark = SparkSession.builder \
        .appName("CryptoPricePredictor-Inference") \
        .config("spark.mongodb.read.connection.uri", MONGO_URI) \
        .config("spark.mongodb.write.connection.uri", MONGO_URI) \
        .config("spark.executorEnv.PYSPARK_PYTHON", sys.executable) \
        .config("spark.pyspark.python", sys.executable) \
        .config("spark.pyspark.driver.python", sys.executable) \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    # Load model parameters from JSON (robust on Windows)
    print(f"\n1: Loading model from {MODEL_PATH}...")
    params_path = os.path.join(MODEL_PATH, "model.json")
    if not os.path.exists(params_path):
        print(f"Model file not found: {params_path}")
        print("   Please train the model first using train_price_prediction.py")
        return
    with open(params_path, 'r') as f:
        model_params = json.load(f)
    print("Model parameters loaded!")
    
    # Fetch recent data
    print(f"\n2: Fetching recent data (last {LOOKBACK_PERIODS} periods)...")
    raw_data = fetch_recent_data(
        MONGO_URI, MONGO_DB, MONGO_INPUT_COLLECTION, 
        SYMBOLS, LOOKBACK_PERIODS
    )
    
    if len(raw_data) < LOOKBACK_PERIODS:
        print(f"Not enough recent data (got {len(raw_data)}). Falling back to latest per symbol...")
        # Fetch latest K per symbol to ensure sufficient window for features (MA20 needs 20)
        raw_data = fetch_latest_k_per_symbol(
            MONGO_URI, MONGO_DB, MONGO_INPUT_COLLECTION, SYMBOLS, k=max(LOOKBACK_PERIODS, 40)
        )
        if len(raw_data) == 0:
            print("Still no data. Please populate CRYPTO.5m_kline (run ohlc_5m_aggregator.py).")
            return
    
    print(f"Fetched {len(raw_data)} records")
    
    # Normalize and convert to Spark DataFrame (drop _id, fix types)
    raw_data = normalize_mongo_docs(raw_data)
    df = spark.createDataFrame(raw_data)
    
    # Create features
    print("\n3: Engineering features...")
    df_features = create_features(df)
    
    # Feature columns (must match training)
    feature_cols = [
        "return_1", "return_2",
        "price_to_ma5", "price_to_ma20",
        "volatility_5", "volatility_10",
        "volume_ratio",
        "rsi",
        "price_range", "body_size"
    ]
    
    # Get only the latest record per symbol for prediction
    window_latest = Window.partitionBy("symbol").orderBy(col("openTime").desc())
    from pyspark.sql.functions import row_number
    
    df_latest = df_features.withColumn("rn", row_number().over(window_latest)) \
        .filter(col("rn") == 1) \
        .drop("rn")
    
    # Select features
    df_predict = df_latest.select(["symbol", "openTime", "open", "high", "low", "close", "volume"] + feature_cols)
    
    # Filter out nulls
    for fcol in feature_cols:
        df_predict = df_predict.filter(col(fcol).isNotNull())
    
    print(f"Ready to predict for {df_predict.count()} symbols")
    
    # Make predictions (manual inference with scaler params)
    print("\n4: Making predictions...")
    feature_cols = [
        "return_1", "return_2",
        "price_to_ma5", "price_to_ma20",
        "volatility_5", "volatility_10",
        "volume_ratio",
        "rsi",
        "price_range", "body_size"
    ]

    # Build prediction expression: sum(((x - mean)/std) * coef) + intercept
    intercept = float(model_params.get("intercept", 0.0))
    pred_expr = lit(intercept)
    for f in feature_cols:
        mean_f = float(model_params.get("scaler_mean", {}).get(f, 0.0))
        std_f = float(model_params.get("scaler_std", {}).get(f, 1.0))
        coef_f = float(model_params.get("coefficients", {}).get(f, 0.0))
        standardized = when(lit(std_f) != 0.0, (col(f) - lit(mean_f)) / lit(std_f)).otherwise(lit(0.0))
        pred_expr = pred_expr + (standardized * lit(coef_f))

    predictions = df_predict.withColumn("prediction", pred_expr)
    
    # Calculate predicted price and direction
    predictions = predictions.withColumn(
        "predicted_change_pct", col("prediction")
    ).withColumn(
        "predicted_price", col("close") * (1 + col("prediction") / 100)
    ).withColumn(
        "direction", when(col("prediction") > 0, "UP").otherwise("DOWN")
    ).withColumn(
        "prediction_time", lit(datetime.now(timezone.utc).isoformat())
    ).withColumn(
        "target_time", lit((datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat())
    )
    
    # Select output columns
    output = predictions.select(
        "symbol",
        "openTime",
        "close",
        "predicted_price",
        "predicted_change_pct",
        "direction",
        "prediction_time",
        "target_time",
        "return_1",
        "rsi",
        "volatility_5",
        "volume_ratio"
    )
    
    # Show predictions
    print("\n📈 PREDICTIONS:")
    print("=" * 80)
    output.orderBy(col("predicted_change_pct").desc()).show(20, truncate=False)
    
    # Save to MongoDB
    print("\n5: Saving predictions to MongoDB...")
    predictions_list = output.toPandas().to_dict('records')
    
    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB]
    collection = db[MONGO_PREDICTION_COLLECTION]
    
    # Create index
    collection.create_index([("symbol", 1), ("prediction_time", -1)])
    
    # Insert predictions
    if predictions_list:
        collection.insert_many(predictions_list)
        print(f"Saved {len(predictions_list)} predictions to MongoDB")
    
    # Save to Redis for quick access
    print("\n6: Saving to Redis...")
    if ENABLE_REDIS:
        try:
            redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                decode_responses=True
            )
            for pred in predictions_list:
                key = f"crypto:prediction:{pred['symbol']}"
                redis_client.setex(
                    key,
                    300,  # 5 minutes TTL
                    json.dumps({
                        "symbol": pred["symbol"],
                        "current_price": float(pred["close"]),
                        "predicted_price": float(pred["predicted_price"]),
                        "predicted_change": float(pred["predicted_change_pct"]),
                        "direction": pred["direction"],
                        "prediction_time": pred["prediction_time"],
                        "target_time": pred["target_time"],
                        "confidence_score": float(abs(pred["predicted_change_pct"]))
                    })
                )
            redis_client.close()
            print("Saved to Redis")
        except Exception as e:
            print(f"Redis not available ({REDIS_HOST}:{REDIS_PORT}): {e}. Skipping Redis save.")
    else:
        print("Skipping Redis save (ENABLE_REDIS=0)")
    
    # Summary
    print("\n" + "=" * 80)
    print("PREDICTION SUMMARY")
    print("=" * 80)
    
    from pyspark.sql.functions import count
    summary = output.groupBy("direction").agg(count("*").alias("count"))
    summary.show()
    
    avg_change = output.agg({"predicted_change_pct": "avg"}).collect()[0][0]
    print(f"Average predicted change: {avg_change:.4f}%")
    
    print("\nPrediction completed successfully!")
    print("=" * 80)
    
    client.close()
    spark.stop()


if __name__ == "__main__":
    main()
