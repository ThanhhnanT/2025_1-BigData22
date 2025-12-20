# Crypto Price Prediction - ML System

## Overview
This system uses **Spark ML Linear Regression** to predict 5-minute crypto price movements based on technical indicators and historical OHLC data.

## 🚀 Quick Start from Scratch

### Prerequisites
- Python 3.8+
- PySpark installed
- MongoDB (with historical 5m_kline data)
- Redis running
- Backend FastAPI server

### Step-by-Step Setup

#### 1. Install Dependencies
```bash
# Install PySpark and ML libraries
pip install pyspark pymongo redis pandas

# Or use project requirements
cd backend_fastapi
pip install -r requirements.txt
```

#### 2. Verify Data Availability
```bash
# Check if you have historical 5m data in MongoDB
# You need at least 30 days of data for training

# Option A: Use existing data from ohlc_5m_aggregator.py
cd Spark/batch
python ohlc_5m_aggregator.py  # Run this daily to populate data

# Option B: Verify data exists
# Connect to MongoDB and check:
# Database: CRYPTO
# Collection: 5m_kline
# Should have documents with interval="5m"
```

#### 3. Start Required Services
```bash
# Terminal 1: Start Redis (if not running)
redis-server

# Terminal 2: Start Backend API
cd backend_fastapi
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 4. Train the ML Model
```bash
# Terminal 3: Train the model (one-time or daily)
cd Spark/batch
python train_price_prediction.py
```

**Expected Output:**
```
🤖 Crypto Price Prediction - Linear Regression Training
================================================================================
📥 Step 1: Fetching training data...
📊 Fetching data from 2025-11-18 to 2025-12-18
   Symbols: ['BTCUSDT', 'ETHUSDT', ...]
✅ Fetched 12000 records

🔧 Step 2: Engineering features...
✅ Clean data shape: 11500 rows

✂️  Step 3: Splitting data...
   Training set: 9200 rows
   Test set: 2300 rows

🎯 Step 5: Training model...

📊 MODEL PERFORMANCE
================================================================================
Training Set:
  RMSE: 0.3234%
  MAE:  0.2456%
  R²:   0.6789

Test Set:
  RMSE: 0.3456%
  MAE:  0.2634%
  R²:   0.6234

💾 Step 7: Saving model to /tmp/crypto_lr_model...
✅ Model saved successfully!
   Model: /tmp/crypto_lr_model
   Metadata: /tmp/crypto_lr_model_metadata.json
```

#### 5. Generate Predictions
```bash
# Terminal 4: Run predictions
python predict_price.py
```

**Expected Output:**
```
🔮 Crypto Price Prediction - Real-time Inference
================================================================================
📥 Step 1: Loading model from /tmp/crypto_lr_model...
✅ Model loaded successfully!
   Trained: 2025-12-18T10:00:00Z
   Test RMSE: 0.3456%
   Test R²: 0.6234

📊 Step 2: Fetching recent data (last 30 periods)...
✅ Fetched 450 records

🔧 Step 3: Engineering features...
✅ Ready to predict for 15 symbols

🎯 Step 4: Making predictions...

📈 PREDICTIONS:
================================================================================
+----------+----------+---------------+------------------+----------+
|symbol    |close     |predicted_price|predicted_change_pct|direction|
+----------+----------+---------------+------------------+----------+
|BTCUSDT   |42150.50  |42230.75       |0.1903            |UP        |
|ETHUSDT   |2230.15   |2218.45        |-0.5246           |DOWN      |
|BNBUSDT   |315.80    |316.45         |0.2058            |UP        |
|SOLUSDT   |95.42     |96.12          |0.7334            |UP        |
|ADAUSDT   |0.5234    |0.5198         |-0.6878           |DOWN      |
+----------+----------+---------------+------------------+----------+

💾 Step 5: Saving predictions to MongoDB...
✅ Saved 15 predictions to MongoDB

💾 Step 6: Saving to Redis...
✅ Saved to Redis

📊 PREDICTION SUMMARY
================================================================================
+---------+-----+
|direction|count|
+---------+-----+
|UP       |8    |
|DOWN     |7    |
+---------+-----+
Average predicted change: 0.0234%

✅ Prediction completed successfully!
```

#### 6. Access Predictions via API
```bash
# Get all predictions
curl http://localhost:8000/predictions

# Get specific symbol prediction
curl http://localhost:8000/prediction/BTCUSDT

# Get prediction history with accuracy
curl http://localhost:8000/prediction/BTCUSDT/history?limit=20
```

**API Response Example:**
```json
{
  "symbol": "BTCUSDT",
  "prediction": {
    "symbol": "BTCUSDT",
    "current_price": 42150.50,
    "predicted_price": 42230.75,
    "predicted_change": 0.19,
    "direction": "UP",
    "prediction_time": "2025-12-18T10:30:00Z",
    "target_time": "2025-12-18T10:35:00Z",
    "confidence_score": 0.19
  }
}
```

#### 7. Schedule Automated Runs (Optional)
```bash
# Option A: Using Airflow
cp airflow/dags/ml_prediction_dag.py /path/to/airflow/dags/
airflow dags trigger crypto_ml_training
airflow dags trigger crypto_ml_prediction

# Option B: Using cron (Linux/Mac)
# Add to crontab:
0 2 * * * cd /path/to/project/Spark/batch && python train_price_prediction.py
*/5 * * * * cd /path/to/project/Spark/batch && python predict_price.py

# Option C: Using Task Scheduler (Windows)
# Create scheduled tasks for both scripts
```

### Workflow Summary
```
1. Historical Data Collection → MongoDB (5m_kline)
2. Model Training → /tmp/crypto_lr_model
3. Prediction Generation → MongoDB (predictions) + Redis (cache)
4. API Access → GET /predictions, /prediction/{symbol}
5. Frontend Display → Real-time prediction dashboard
```

## Architecture

```
MongoDB (5m_kline) → Feature Engineering → Linear Regression Model → Predictions → Redis/MongoDB
                                    ↓
                            Technical Indicators:
                            - Moving Averages (MA5, MA10, MA20)
                            - RSI (Relative Strength Index)
                            - Volatility (5 & 10 periods)
                            - Volume Ratios
                            - Price Returns
```

## Components

### 1. Training Script
**File:** `Spark/batch/train_price_prediction.py`

Trains a Linear Regression model to predict the next 5-minute price change percentage.

**Features:**
- `return_1`, `return_2` - Recent price changes
- `price_to_ma5`, `price_to_ma20` - Price position relative to moving averages
- `volatility_5`, `volatility_10` - Price volatility
- `volume_ratio` - Volume vs average volume
- `rsi` - Momentum indicator
- `price_range`, `body_size` - Candle characteristics

**Usage:**
```bash
# Local execution
python Spark/batch/train_price_prediction.py

# With custom settings
MONGO_URI="mongodb://..." \
TRAINING_DAYS=60 \
MODEL_PATH="/tmp/crypto_lr_model" \
python Spark/batch/train_price_prediction.py
```

**Output:**
- Model saved to `/tmp/crypto_lr_model`
- Metadata JSON with performance metrics
- Training/Test RMSE, MAE, R² scores

### 2. Prediction Script
**File:** `Spark/batch/predict_price.py`

Generates real-time predictions using the trained model.

**Usage:**
```bash
# Local execution
python Spark/batch/predict_price.py

# With custom settings
REDIS_HOST="localhost" \
REDIS_PORT=6379 \
MODEL_PATH="/tmp/crypto_lr_model" \
python Spark/batch/predict_price.py
```

**Output:**
- Predictions stored in MongoDB `predictions` collection
- Latest predictions cached in Redis with 5-minute TTL
- Format: `crypto:prediction:{SYMBOL}`

### 3. Airflow DAGs
**File:** `airflow/dags/ml_prediction_dag.py`

**Training DAG:**
- Schedule: Daily at 2 AM UTC
- Retrains model with last 30 days of data

**Prediction DAG:**
- Schedule: Every 5 minutes
- Generates predictions for all symbols

### 4. Backend API Endpoints

#### Get Latest Prediction
```bash
GET /prediction/{symbol}

# Example
curl http://localhost:8000/prediction/BTCUSDT
```

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "prediction": {
    "symbol": "BTCUSDT",
    "current_price": 42150.50,
    "predicted_price": 42230.75,
    "predicted_change": 0.19,
    "direction": "UP",
    "prediction_time": "2025-12-18T10:30:00Z",
    "target_time": "2025-12-18T10:35:00Z",
    "confidence_score": 0.19
  }
}
```

#### Get All Predictions
```bash
GET /predictions

# Returns predictions for all symbols, sorted by confidence
```

#### Get Prediction History
```bash
GET /prediction/{symbol}/history?limit=50

# Example
curl http://localhost:8000/prediction/BTCUSDT/history?limit=20
```

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "count": 20,
  "history": [
    {
      "symbol": "BTCUSDT",
      "prediction_time": "2025-12-18T10:30:00Z",
      "predicted_price": 42230.75,
      "predicted_change": 0.19,
      "actual_price": 42245.20,
      "actual_change": 0.22,
      "accuracy": 84.3
    }
  ]
}
```

## Step-by-Step Usage

### Step 1: Train the Model
```bash
# Ensure you have historical data in MongoDB (5m_kline collection)
# Run the training script
cd Spark/batch
python train_price_prediction.py
```

Expected output:
```
🤖 Crypto Price Prediction - Linear Regression Training
📥 Step 1: Fetching training data...
✅ Fetched 12000 records
🔧 Step 2: Engineering features...
📊 MODEL PERFORMANCE
  Test RMSE: 0.3456%
  Test R²: 0.6234
💾 Model saved successfully!
```

### Step 2: Generate Predictions
```bash
# Run prediction script
python predict_price.py
```

Expected output:
```
🔮 Crypto Price Prediction - Real-time Inference
📥 Step 1: Loading model...
🎯 Step 4: Making predictions...

📈 PREDICTIONS:
+----------+----------+--------------+---------+
|symbol    |close     |predicted_price|direction|
+----------+----------+--------------+---------+
|BTCUSDT   |42150.50  |42230.75      |UP       |
|ETHUSDT   |2230.15   |2218.45       |DOWN     |
+----------+----------+--------------+---------+

✅ Prediction completed successfully!
```

### Step 3: Access via API
```bash
# Start backend server (if not running)
cd backend_fastapi
uvicorn app.main:app --reload

# Get predictions
curl http://localhost:8000/predictions

# Get specific symbol
curl http://localhost:8000/prediction/BTCUSDT

# Get history with accuracy
curl http://localhost:8000/prediction/BTCUSDT/history?limit=50
```

### Step 4: Schedule with Airflow
```bash
# Copy DAG to Airflow
cp airflow/dags/ml_prediction_dag.py /path/to/airflow/dags/

# Trigger manually
airflow dags trigger crypto_ml_training
airflow dags trigger crypto_ml_prediction
```

## Model Performance Metrics

**Interpretation:**
- **RMSE (Root Mean Square Error):** Average prediction error in percentage
  - `< 0.5%` - Excellent
  - `0.5-1.0%` - Good
  - `> 1.0%` - Needs improvement

- **R² (Coefficient of Determination):** How well model explains variance
  - `> 0.6` - Good predictive power
  - `0.3-0.6` - Moderate
  - `< 0.3` - Weak

- **MAE (Mean Absolute Error):** Average absolute prediction error

## Environment Variables

```bash
# MongoDB
MONGO_URI="mongodb+srv://..."
MONGO_DB="CRYPTO"
MONGO_COLLECTION="5m_kline"
MONGO_PREDICTION_COLLECTION="predictions"

# Redis
REDIS_HOST="localhost"
REDIS_PORT=6379
REDIS_DB=0

# Model
MODEL_PATH="/tmp/crypto_lr_model"
TRAINING_DAYS=30
```

## Troubleshooting

### "Not enough training data"
- Ensure you have at least 30 days of 5m_kline data in MongoDB
- Run `ohlc_5m_aggregator.py` to populate historical data

### "Model not found"
- Train the model first: `python train_price_prediction.py`
- Check MODEL_PATH is correct

### "No prediction available"
- Run prediction script: `python predict_price.py`
- Check Redis connection and TTL (predictions expire after 5 minutes)

### Poor accuracy
- Increase TRAINING_DAYS (more historical data)
- Add more features in the feature engineering step
- Try different model parameters (regParam, elasticNetParam)
- Consider using more advanced models (Random Forest, LSTM)

## Next Steps

### Improve Model Performance
1. **Add more features:**
   - Bollinger Bands
   - MACD (Moving Average Convergence Divergence)
   - Order book features (from orderbook data)
   - Market sentiment indicators

2. **Try advanced models:**
   - Random Forest (better for non-linear relationships)
   - Gradient Boosting (XGBoost)
   - LSTM (for time series patterns)
   - Ensemble methods

3. **Feature selection:**
   - Use feature importance analysis
   - Remove correlated features
   - Add interaction terms

4. **Hyperparameter tuning:**
   - Grid search or random search
   - Cross-validation

### Frontend Integration
Create a predictions dashboard showing:
- Real-time predictions vs actual prices
- Prediction accuracy metrics
- Model confidence visualization
- Historical performance charts

### Monitoring
- Track model drift
- Monitor prediction accuracy over time
- Alert when accuracy drops below threshold
- A/B test different model versions

## Files Created

1. `Spark/batch/train_price_prediction.py` - Training pipeline
2. `Spark/batch/predict_price.py` - Inference pipeline
3. `airflow/dags/ml_prediction_dag.py` - Airflow scheduling
4. Backend API endpoints in `backend_fastapi/app/main.py`
5. Prediction schemas in `backend_fastapi/app/schemas.py`

## License
MIT
