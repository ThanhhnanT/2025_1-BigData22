# Local Crypto Price Prediction Testing Guide

## Prerequisites ✅

You have:
- ✅ MongoDB with **364 days** of 5m candle data
- ✅ PySpark 3.5.1, PyMongo 4.9.2, Redis 5.2.1
- ✅ 14 symbols: BTCUSDT, ETHUSDT, BNBUSDT, etc.

## Quick Test Steps

### 1. Train the ML Model (One-time)

```powershell
# Ensure services are running
docker ps  # Check MongoDB and Redis containers

# Train the model (takes 5-10 minutes)
C:/Users/ACER/anaconda3/envs/bigdata/python.exe Spark/batch/train_price_prediction.py
```

**Expected Output:**
```
🤖 Crypto Price Prediction - Linear Regression Training
================================================================================
📥 Step 1: Fetching training data...
📊 Fetching data from 2024-11-20 to 2025-12-20
✅ Fetched 12000+ records

🔧 Step 2: Engineering features...
✅ Clean data shape: 11500 rows

✂️  Step 3: Splitting data...
   Training set: 9200 rows
   Test set: 2300 rows

🎯 Step 5: Training model...

📊 MODEL PERFORMANCE
Training Set RMSE: 0.32% | Test Set RMSE: 0.34%

💾 Step 7: Saving model to /tmp/crypto_lr_model...
✅ Model saved successfully!
```

The model is saved to: **`/tmp/crypto_lr_model`**

### 2. Generate Predictions

```powershell
# Run predictions (takes 1-2 minutes)
C:/Users/ACER/anaconda3/envs/bigdata/python.exe Spark/batch/predict_price.py
```

**Expected Output:**
```
🔮 Crypto Price Prediction - Real-time Inference
================================================================================
📥 Step 1: Loading model from /tmp/crypto_lr_model...
✅ Model loaded successfully!

📊 Step 2: Fetching recent data (last 30 periods)...
✅ Fetched 450 records

🎯 Step 4: Making predictions...

📈 PREDICTIONS:
+----------+----------+---------------+------------------+----------+
|symbol    |close     |predicted_price|predicted_change_pct|direction|
+----------+----------+---------------+------------------+----------+
|BTCUSDT   |42150.50  |42230.75       |0.1903            |UP        |
|ETHUSDT   |2230.15   |2218.45        |-0.5246           |DOWN      |
|BNBUSDT   |315.80    |316.45         |0.2058            |UP        |
...

💾 Step 5: Saving predictions to MongoDB...
✅ Saved 14 predictions to MongoDB

💾 Step 6: Saving to Redis...
✅ Saved to Redis
```

### 3. Verify Predictions

```powershell
# Quick test script
C:/Users/ACER/anaconda3/envs/bigdata/python.exe Spark/batch/test_prediction_quick.py
```

**Or manually check:**

#### MongoDB (Compass)
- Connection: `mongodb://root:123456@localhost:27017/`
- Database: `CRYPTO`
- Collection: `predictions`
- Filter: `{}`
- Sort: `{ "prediction_time": -1 }`

#### Redis (RedisInsight or CLI)
```powershell
docker exec -it redis-local redis-cli -a 123456

# Check a specific prediction
GET crypto:prediction:BTCUSDT

# List all prediction keys
KEYS crypto:prediction:*
```

### 4. Run Predictions Periodically

For continuous predictions every 5 minutes:

```powershell
# Option 1: Manual re-run
C:/Users/ACER/anaconda3/envs/bigdata/python.exe Spark/batch/predict_price.py

# Option 2: Windows Task Scheduler
# Create a task that runs every 5 minutes:
# - Program: C:/Users/ACER/anaconda3/envs/bigdata/python.exe
# - Arguments: D:/TTH/BK/Bigdata/project/2025_1-BigData22/Spark/batch/predict_price.py
# - Start in: D:/TTH/BK/Bigdata/project/2025_1-BigData22
```

## Troubleshooting

### Error: "No module named 'pyspark'"
Make sure to use the full Python path with bigdata environment:
```powershell
C:/Users/ACER/anaconda3/envs/bigdata/python.exe
```

### Error: "No recent data"
Run the history fetcher to get fresh 5m data:
```powershell
$env:MONGO_URI = "mongodb://root:123456@localhost:27017/"
C:/Users/ACER/anaconda3/envs/bigdata/python.exe Kafka/binance_history_fetcher.py
```

### Error: MongoDB/Redis connection
Check services are running:
```powershell
docker ps
mongosh "mongodb://root:123456@localhost:27017/CRYPTO" --eval "db.serverStatus().ok"
docker exec -it redis-local redis-cli -a 123456 ping
```

### Retrain Model
Retrain when:
- After 7+ days (model gets stale)
- After significant market events
- When accuracy drops

Just re-run the training script:
```powershell
C:/Users/ACER/anaconda3/envs/bigdata/python.exe Spark/batch/train_price_prediction.py
```

## What's Next?

### Access via Backend API
Start the FastAPI backend to query predictions via REST:
```powershell
cd backend_fastapi
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints:
- `GET http://localhost:8000/predictions` - All latest predictions
- `GET http://localhost:8000/prediction/BTCUSDT` - Specific symbol
- `GET http://localhost:8000/prediction/BTCUSDT/history` - Historical accuracy

### View in Frontend
```powershell
cd frontend
npm install
npm run dev
```

Open: `http://localhost:3000/prediction`

## Model Details

- **Algorithm:** Linear Regression (PySpark ML)
- **Features:** 20+ technical indicators
  - Moving averages (5, 10, 20 periods)
  - RSI momentum
  - Volatility (standard deviation)
  - Volume changes
  - Price patterns (shadows, body size)
- **Training Data:** 30 days of 5m candles
- **Prediction:** Next 5-minute price movement
- **Performance:** ~0.3-0.4% RMSE on test set

## Files

- `train_price_prediction.py` - ML training pipeline
- `predict_price.py` - Real-time inference
- `test_prediction_quick.py` - Quick verification script
- `/tmp/crypto_lr_model` - Saved model
- `/tmp/crypto_lr_model_metadata.json` - Model metadata

## Environment Variables

Override defaults if needed:
```powershell
$env:MONGO_URI = "mongodb://root:123456@localhost:27017/"
$env:MONGO_DB = "CRYPTO"
$env:REDIS_HOST = "localhost"
$env:REDIS_PORT = "6379"
$env:REDIS_PASSWORD = "123456"
$env:MODEL_PATH = "/tmp/crypto_lr_model"
$env:TRAINING_DAYS = "30"
```
