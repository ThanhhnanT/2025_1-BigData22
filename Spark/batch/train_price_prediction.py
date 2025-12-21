#!/usr/bin/env python3
"""
ML Training Pipeline - Linear Regression Price Prediction
Trains a linear regression model to predict next 5-minute price movement
"""

import os
import sys
import json
from datetime import datetime, timedelta, timezone
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, lag, avg, stddev, max as spark_max, min as spark_min,
    when, lit, unix_timestamp, from_unixtime
)
from pyspark.sql.window import Window
from pyspark.ml.feature import VectorAssembler, StandardScaler
from pyspark.ml.regression import LinearRegression
from pyspark.ml.evaluation import RegressionEvaluator
from pyspark.ml import Pipeline
from pymongo import MongoClient

# Configuration
# MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://vuongthanhsaovang:9KviWHBS85W7i4j6@ai-tutor.k6sjnzc.mongodb.net")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://root:123456@localhost:27017/")
MONGO_DB = os.getenv("MONGO_DB", "CRYPTO")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION", "5m_kline")

MODEL_PATH = os.getenv("MODEL_PATH", "/tmp/crypto_lr_model")
TRAINING_DAYS = int(os.getenv("TRAINING_DAYS", 30))

SYMBOLS = [
    "BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "ADAUSDT",
    "XRPUSDT", "DOGEUSDT", "DOTUSDT", "MATICUSDT", "AVAXUSDT",
    "LINKUSDT", "UNIUSDT", "LTCUSDT", "ATOMUSDT", "ETCUSDT"
]


def fetch_training_data(mongo_uri, db_name, collection_name, symbols, days=30):
    """Fetch historical OHLC data from MongoDB"""
    client = MongoClient(mongo_uri)
    db = client[db_name]
    collection = db[collection_name]
    
    # Calculate date range
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(days=days)
    start_timestamp = int(start_time.timestamp() * 1000)
    end_timestamp = int(end_time.timestamp() * 1000)
    
    print(f"📊 Fetching data from {start_time} to {end_time}")
    print(f"   Symbols: {symbols}")
    
    # Query MongoDB
    query = {
        "symbol": {"$in": symbols},
        "interval": "5m",
        "openTime": {"$gte": start_timestamp, "$lte": end_timestamp}
    }
    
    cursor = collection.find(query).sort("openTime", 1)
    data = list(cursor)
    client.close()
    
    print(f"✅ Fetched {len(data)} records")
    return data


def create_features(df):
    """
    Create technical indicator features for ML model
    Features:
    - Price changes and returns
    - Moving averages (5, 10, 20 periods)
    - Volatility (standard deviation)
    - Volume features
    - RSI-like momentum
    - Price position in range
    """
    
    # Define window specifications per symbol
    window_spec = Window.partitionBy("symbol").orderBy("openTime")
    
    # Basic price features
    df = df.withColumn("price_range", col("high") - col("low"))
    df = df.withColumn("body_size", col("close") - col("open"))
    # Use greatest/least for shadows
    from pyspark.sql.functions import greatest, least
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
    df = df.withColumn("ma5", 
                       avg("close").over(window_spec.rowsBetween(-4, 0)))
    df = df.withColumn("ma10", 
                       avg("close").over(window_spec.rowsBetween(-9, 0)))
    df = df.withColumn("ma20", 
                       avg("close").over(window_spec.rowsBetween(-19, 0)))
    
    # Volatility
    df = df.withColumn("volatility_5", 
                       stddev("close").over(window_spec.rowsBetween(-4, 0)))
    df = df.withColumn("volatility_10", 
                       stddev("close").over(window_spec.rowsBetween(-9, 0)))
    
    # Volume features
    df = df.withColumn("volume_ma5", 
                       avg("volume").over(window_spec.rowsBetween(-4, 0)))
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
    
    # RSI-like momentum (simplified)
    df = df.withColumn("gain", 
                       when(col("return_1") > 0, col("return_1")).otherwise(0))
    df = df.withColumn("loss", 
                       when(col("return_1") < 0, -col("return_1")).otherwise(0))
    
    df = df.withColumn("avg_gain", 
                       avg("gain").over(window_spec.rowsBetween(-13, 0)))
    df = df.withColumn("avg_loss", 
                       avg("loss").over(window_spec.rowsBetween(-13, 0)))
    
    df = df.withColumn("rsi", 
                       when(col("avg_loss") > 0, 
                            100 - (100 / (1 + col("avg_gain") / col("avg_loss"))))
                       .when(col("avg_gain") > 0, 100)  # All gains, no losses
                       .otherwise(50))
    
    # Target: Next 5-minute price change (%)
    df = df.withColumn("next_close", 
                       lag("close", -1).over(window_spec))
    df = df.withColumn("target", 
                       when(col("next_close").isNotNull(), 
                            (col("next_close") - col("close")) / col("close") * 100)
                       .otherwise(None))
    
    return df


def main():
    """Main training pipeline"""
    import sys
    sys.stdout.flush()  # Ensure immediate output
    
    start_time = datetime.now(timezone.utc)
    print("=" * 80)
    print("🤖 Crypto Price Prediction - Linear Regression Training")
    print(f"⏰ Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("=" * 80)
    sys.stdout.flush()

    # Ensure Spark uses current Python interpreter (avoids missing python.exe issue on Windows)
    os.environ["PYSPARK_PYTHON"] = sys.executable
    os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
    
    # Initialize Spark
    print("\n[1/7] 🔧 Initializing Spark Session...")
    sys.stdout.flush()
    spark = SparkSession.builder \
        .appName("CryptoPricePredictor-Training") \
        .config("spark.mongodb.read.connection.uri", MONGO_URI) \
        .config("spark.mongodb.write.connection.uri", MONGO_URI) \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    print("✅ Spark Session initialized")
    sys.stdout.flush()
    
    # Fetch data from MongoDB
    print("\n[2/7] 📥 Fetching training data from MongoDB...")
    print(f"   Training days: {TRAINING_DAYS}")
    print(f"   Symbols: {len(SYMBOLS)} symbols")
    sys.stdout.flush()
    fetch_start = datetime.now(timezone.utc)
    raw_data = fetch_training_data(MONGO_URI, MONGO_DB, MONGO_COLLECTION, SYMBOLS, TRAINING_DAYS)
    fetch_duration = (datetime.now(timezone.utc) - fetch_start).total_seconds()
    print(f"✅ Fetched {len(raw_data)} records in {fetch_duration:.1f}s")
    sys.stdout.flush()
    
    if len(raw_data) < 100:
        print("❌ Not enough training data!")
        return

    # Normalize docs: drop MongoDB ObjectId and convert pandas/numpy types to native python
    print("\n[3/7] 🔄 Normalizing and converting data...")
    sys.stdout.flush()
    normalize_start = datetime.now(timezone.utc)
    numeric_fields = [
        "openTime", "closeTime", "open", "high", "low", "close",
        "volume", "quoteVolume", "trades"
    ]

    total_docs = len(raw_data)
    for idx, doc in enumerate(raw_data):
        if (idx + 1) % 10000 == 0:
            print(f"   Processing: {idx + 1}/{total_docs} documents ({100*(idx+1)/total_docs:.1f}%)", flush=True)
        doc.pop("_id", None)

        # Convert nullable integer/float types to native python types Spark can infer
        for field in numeric_fields:
            val = doc.get(field)
            if val is None:
                continue
            try:
                # Handle numpy/pandas scalars with .item()
                if hasattr(val, "item"):
                    val = val.item()
                # Cast to float for price/volume, int for time/trades
                if field in ("openTime", "closeTime", "trades"):
                    val = int(val)
                else:
                    val = float(val)
                doc[field] = val
            except Exception:
                # If conversion fails, drop the field to avoid schema errors
                doc.pop(field, None)
    
    normalize_duration = (datetime.now(timezone.utc) - normalize_start).total_seconds()
    print(f"✅ Normalized {total_docs} documents in {normalize_duration:.1f}s")
    sys.stdout.flush()
    
    # Convert to Spark DataFrame
    print("   Creating Spark DataFrame...")
    sys.stdout.flush()
    df = spark.createDataFrame(raw_data)
    
    row_count = df.count()
    col_count = len(df.columns)
    symbol_count = df.select('symbol').distinct().count()
    print(f"✅ DataFrame created: {row_count:,} rows, {col_count} columns")
    print(f"   Symbols: {symbol_count}")
    sys.stdout.flush()
    
    # Create features
    print("\n[4/7] 🔧 Engineering features...")
    print("   This may take a few minutes (computing moving averages, RSI, volatility)...")
    sys.stdout.flush()
    feature_start = datetime.now(timezone.utc)
    df_features = create_features(df)
    feature_duration = (datetime.now(timezone.utc) - feature_start).total_seconds()
    print(f"✅ Features created in {feature_duration:.1f}s")
    sys.stdout.flush()
    
    # Select feature columns and target
    feature_cols = [
        "return_1", "return_2",
        "price_to_ma5", "price_to_ma20",
        "volatility_5", "volatility_10",
        "volume_ratio",
        "rsi",
        "price_range", "body_size"
    ]
    
    # Filter out rows with nulls
    df_clean = df_features.select(["symbol", "openTime", "close", "target"] + feature_cols) \
        .filter(col("target").isNotNull())
    
    for fcol in feature_cols:
        df_clean = df_clean.filter(col(fcol).isNotNull())
    
    clean_count = df_clean.count()
    print(f"✅ Clean data: {clean_count:,} rows (removed nulls)")
    sys.stdout.flush()
    
    # Split train/test (80/20)
    print("\n[5/7] ✂️  Splitting data (80% train, 20% test)...")
    sys.stdout.flush()
    train_df, test_df = df_clean.randomSplit([0.8, 0.2], seed=42)
    
    train_count = train_df.count()
    test_count = test_df.count()
    print(f"✅ Split complete:")
    print(f"   Training set: {train_count:,} rows ({100*train_count/clean_count:.1f}%)")
    print(f"   Test set: {test_count:,} rows ({100*test_count/clean_count:.1f}%)")
    sys.stdout.flush()
    
    # Build ML Pipeline
    print("\n[6/7] 🏗️  Building ML pipeline...")
    print(f"   Features: {len(feature_cols)} features")
    print(f"   Model: LinearRegression (maxIter=100)")
    sys.stdout.flush()
    
    # Assemble features
    assembler = VectorAssembler(
        inputCols=feature_cols,
        outputCol="features_raw"
    )
    
    # Scale features
    scaler = StandardScaler(
        inputCol="features_raw",
        outputCol="features",
        withStd=True,
        withMean=True
    )
    
    # Linear Regression model
    lr = LinearRegression(
        featuresCol="features",
        labelCol="target",
        predictionCol="prediction",
        maxIter=100,
        regParam=0.1,
        elasticNetParam=0.0
    )
    
    # Create pipeline
    pipeline = Pipeline(stages=[assembler, scaler, lr])
    print("✅ Pipeline built")
    sys.stdout.flush()
    
    # Train model
    print("\n[7/7] 🎯 Training model (this is the longest step, ~5-15 minutes)...")
    print("   Training LinearRegression with 100 iterations...")
    sys.stdout.flush()
    train_start = datetime.now(timezone.utc)
    model = pipeline.fit(train_df)
    train_duration = (datetime.now(timezone.utc) - train_start).total_seconds()
    print(f"✅ Model trained in {train_duration:.1f}s ({train_duration/60:.1f} minutes)")
    sys.stdout.flush()
    
    # Evaluate on training set
    print("\n📈 Evaluating model...")
    sys.stdout.flush()
    eval_start = datetime.now(timezone.utc)
    train_predictions = model.transform(train_df)
    test_predictions = model.transform(test_df)
    eval_duration = (datetime.now(timezone.utc) - eval_start).total_seconds()
    print(f"✅ Predictions generated in {eval_duration:.1f}s")
    sys.stdout.flush()
    
    evaluator_rmse = RegressionEvaluator(
        labelCol="target",
        predictionCol="prediction",
        metricName="rmse"
    )
    
    evaluator_r2 = RegressionEvaluator(
        labelCol="target",
        predictionCol="prediction",
        metricName="r2"
    )
    
    evaluator_mae = RegressionEvaluator(
        labelCol="target",
        predictionCol="prediction",
        metricName="mae"
    )
    
    train_rmse = evaluator_rmse.evaluate(train_predictions)
    train_r2 = evaluator_r2.evaluate(train_predictions)
    train_mae = evaluator_mae.evaluate(train_predictions)
    
    test_rmse = evaluator_rmse.evaluate(test_predictions)
    test_r2 = evaluator_r2.evaluate(test_predictions)
    test_mae = evaluator_mae.evaluate(test_predictions)
    
    print("\n" + "=" * 80)
    print("📊 MODEL PERFORMANCE")
    print("=" * 80)
    print(f"Training Set:")
    print(f"  RMSE: {train_rmse:.4f}%")
    print(f"  MAE:  {train_mae:.4f}%")
    print(f"  R²:   {train_r2:.4f}")
    print(f"\nTest Set:")
    print(f"  RMSE: {test_rmse:.4f}%")
    print(f"  MAE:  {test_mae:.4f}%")
    print(f"  R²:   {test_r2:.4f}")
    
    # Get model coefficients
    lr_model = model.stages[-1]
    print(f"\n📐 Model Coefficients:")
    for i, feature_name in enumerate(feature_cols):
        coef = lr_model.coefficients[i]
        print(f"  {feature_name:20s}: {coef:10.6f}")
    print(f"  Intercept: {lr_model.intercept:.6f}")
    
    # Save model
    print(f"\n💾 Saving model to {MODEL_PATH}...")
    sys.stdout.flush()
    save_start = datetime.now(timezone.utc)
    os.makedirs(MODEL_PATH, exist_ok=True)
    # Try Spark pipeline save (may fail on Windows without winutils)
    try:
        model.write().overwrite().save(MODEL_PATH)
        print("✅ Spark pipeline saved")
    except Exception as e:
        print(f"⚠️  Skipping Spark pipeline save: {e}")
    sys.stdout.flush()

    # Extract scaler params for manual inference
    scaler_model = model.stages[1]
    try:
        mean_vec = list(map(float, scaler_model.mean)) if scaler_model.getWithMean() else [0.0] * len(feature_cols)
    except Exception:
        mean_vec = [0.0] * len(feature_cols)
    try:
        std_vec = list(map(float, scaler_model.std)) if scaler_model.getWithStd() else [1.0] * len(feature_cols)
    except Exception:
        std_vec = [1.0] * len(feature_cols)

    # Save metadata + parameters for JSON-based inference
    metadata = {
        "model_type": "LinearRegression",
        "features": feature_cols,
        "training_date": datetime.now(timezone.utc).isoformat(),
        "training_days": TRAINING_DAYS,
        "train_samples": train_df.count(),
        "test_samples": test_df.count(),
        "metrics": {
            "train_rmse": float(train_rmse),
            "train_mae": float(train_mae),
            "train_r2": float(train_r2),
            "test_rmse": float(test_rmse),
            "test_mae": float(test_mae),
            "test_r2": float(test_r2)
        },
        "coefficients": {feature_cols[i]: float(lr_model.coefficients[i]) for i in range(len(feature_cols))},
        "intercept": float(lr_model.intercept),
        "scaler_mean": {feature_cols[i]: float(mean_vec[i]) for i in range(len(feature_cols))},
        "scaler_std": {feature_cols[i]: float(std_vec[i]) for i in range(len(feature_cols))}
    }

    metadata_path = os.path.join(MODEL_PATH, "model.json")
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    save_duration = (datetime.now(timezone.utc) - save_start).total_seconds()
    print(f"✅ Model params saved to {metadata_path} (took {save_duration:.1f}s)")
    sys.stdout.flush()
    
    # Show sample predictions
    print("\n🔍 Sample Predictions:")
    sample_preds = test_predictions.select(
        "symbol", "close", "target", "prediction"
    ).limit(10)
    
    sample_preds.show(truncate=False)
    
    total_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
    print("\n" + "=" * 80)
    print("✅ Training completed successfully!")
    print(f"⏰ Total time: {total_duration:.1f}s ({total_duration/60:.1f} minutes)")
    print("=" * 80)
    sys.stdout.flush()
    
    spark.stop()


if __name__ == "__main__":
    main()
