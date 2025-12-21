# Hệ Thống Xử Lý Dữ Liệu Cryptocurrency - Real-time Trading Platform

## 👥 Thành Viên Nhóm

| Họ và Tên | MSSV |
|-----------|------|
| Vương Văn Thành | 20225094 |
| Phạm Huy Sơn | 20225080 |
| Trần Tuấn Hùng | 20225000 |
| Vũ Anh Huy | 20220029 |
| Trần Tuấn Hải | 20224976 |

---

## 📖 Giới Thiệu

Hệ thống xử lý dữ liệu cryptocurrency toàn diện với khả năng xử lý real-time và batch processing, tích hợp Machine Learning để dự đoán giá và phân tích thị trường. Dự án được xây dựng trên nền tảng Kubernetes với các công nghệ Big Data hiện đại như Apache Kafka, Apache Spark, và Apache Airflow.

## 🎯 Mục Tiêu Dự Án

Dự án này là một hệ thống end-to-end để thu thập, xử lý, lưu trữ và hiển thị dữ liệu cryptocurrency từ Binance Exchange. Hệ thống hỗ trợ:

- **Real-time Data Streaming**: Thu thập dữ liệu kline, orderbook, và trades từ Binance WebSocket API
- **Batch Processing**: Xử lý và tổng hợp dữ liệu OHLC theo nhiều khung thời gian (5m, 1h, 4h, 1d)
- **Machine Learning**: Dự đoán giá cryptocurrency sử dụng Spark ML Linear Regression
- **Real-time Dashboard**: Giao diện web hiển thị biểu đồ trading, orderbook, và ranking
- **Monitoring & Observability**: Giám sát hệ thống với Prometheus và Grafana

## 🏗️ Kiến Trúc Hệ Thống

### Workflow Tổng Quan

![Workflow](images/WorkFlow.png)

### Các Thành Phần Chính

#### 1. **Data Ingestion Layer**
- **Kafka Producers**: Thu thập dữ liệu real-time từ Binance WebSocket API
  - Kline data (1m interval) cho 15+ cryptocurrency pairs
  - Orderbook updates với depth 20 levels
  - Market trades real-time
- **Kafka Topics**: 
  - `crypto_kline_1m`: Dữ liệu kline 1 phút
  - `crypto_orderbook`: Dữ liệu orderbook
  - `crypto_trades`: Dữ liệu giao dịch

#### 2. **Data Processing Layer**
- **Apache Spark**: 
  - **Batch Processing**: Tổng hợp OHLC data (5m, 1h, 4h, 1d) từ dữ liệu 1m
  - **Streaming Processing**: Xử lý real-time để tính toán ranking và metrics
  - **ML Pipeline**: Training và prediction model cho giá cryptocurrency
- **Apache Airflow**: Orchestration và scheduling cho các Spark jobs
  - Scheduled DAGs cho batch aggregation
  - ML model training pipeline
  - Data cleanup và maintenance tasks

#### 3. **Data Storage Layer**
- **MongoDB**: Lưu trữ dữ liệu lịch sử OHLC đã được tổng hợp
  - Collections: `5m_kline`, `1h_kline`, `4h_kline`, `1d_kline`, `predictions`
- **Redis**: Cache dữ liệu real-time cho frontend
  - Latest kline data
  - Orderbook snapshots
  - Market trades
  - Ranking data (top gainers/losers)
  - ML predictions

#### 4. **API & Backend Layer**
- **FastAPI**: RESTful API và WebSocket server
  - REST endpoints cho historical data từ MongoDB
  - WebSocket streams cho real-time updates từ Redis
  - ML prediction endpoints
  - Coin ranking endpoints

#### 5. **Frontend Layer**
- **Next.js**: Trading dashboard với các tính năng:
  - Real-time candlestick charts với TradingView integration
  - Orderbook visualization với depth chart
  - Market trades feed với color coding
  - Coin ranking table (top gainers/losers)
  - ML predictions display với confidence scores

#### 6. **Monitoring Layer**
- **Prometheus**: Metrics collection và storage
  - Kafka producer/consumer metrics
  - Spark job execution metrics
  - API latency metrics
  - System resource metrics
- **Grafana**: Visualization và alerting
  - System health dashboards
  - Application performance monitoring
  - Data pipeline health checks

### System Dashboard

![Grafana Dashboard](images/Grafana.png)

## 📁 Cấu Trúc Thư Mục

```
CRYPTO/
├── airflow/                    # Apache Airflow orchestration
│   ├── dags/                   # DAG definitions
│   │   ├── ohlc_spark_aggregator.py    # OHLC aggregation DAGs
│   │   ├── ml_prediction_dag.py        # ML training DAG
│   │   └── redis_clear_and_history_fetch_dag.py
│   ├── Dockerfile
│   └── requirements.txt
│
├── backend_fastapi/            # FastAPI backend
│   ├── app/
│   │   ├── main.py             # API endpoints & WebSocket handlers
│   │   ├── config.py           # Configuration settings
│   │   ├── schemas.py          # Pydantic models
│   │   └── kafka_manager.py    # Shared Kafka consumer manager
│   ├── Dockerfile
│   └── requirements.txt
│
├── frontend/                   # Next.js frontend
│   ├── app/                    # Next.js app directory
│   │   ├── page.tsx            # Main dashboard page
│   │   └── orderbook/          # Orderbook page
│   ├── components/
│   │   ├── charts/             # Trading charts components
│   │   │   ├── TradingDashboard.tsx
│   │   │   └── ChartEmbedded.tsx
│   │   └── ui/                 # UI components
│   ├── Dockerfile
│   └── package.json
│
├── Kafka/                      # Kafka producers
│   ├── binance_producer.py     # Kline data producer
│   ├── binance_orderbook_trades_producer.py
│   ├── redis_consumer.py       # Consumer to Redis
│   └── requirements.txt
│
├── Spark/                      # Apache Spark jobs
│   ├── batch/                  # Batch processing scripts
│   │   ├── ohlc_5m_aggregator.py
│   │   ├── ohlc_1h_aggregator.py
│   │   ├── ohlc_4h_aggregator.py
│   │   ├── ohlc_1d_aggregator.py
│   │   └── train_price_prediction.py
│   ├── ranking_coins/          # Ranking calculation
│   ├── apps/                   # SparkApplication YAMLs for K8s
│   └── Dockerfile
│
├── mongodb/                    # MongoDB Helm chart
├── redis/                      # Redis Helm chart
├── Prometheus/                 # Prometheus Helm chart
│
├── deploy/                     # Deployment configurations
│   ├── k8s_web/                # Kubernetes manifests
│   │   ├── frontend-deployment.yaml
│   │   ├── backend-deployment.yaml
│   │   ├── ingress.yaml
│   │   └── namespace.yaml
│   └── helm/                   # Helm deployment scripts
│
└── images/                     # Documentation images
    ├── WorkFlow.png
    ├── Chart.png
    ├── rank.png
    ├── Grafana.png
    └── SysTemDashBoard.png
```

## 🚀 Tính Năng Chính

### 1. Real-time Data Streaming

Hệ thống thu thập dữ liệu real-time từ Binance WebSocket API:
- **Kline Data**: Dữ liệu nến 1 phút cho 15+ cryptocurrency pairs (BTC, ETH, BNB, SOL, ADA, XRP, DOGE, DOT, MATIC, AVAX, LINK, UNI, LTC, ATOM, ETC)
- **Orderbook**: Order book depth với updates real-time (20 levels bids/asks)
- **Market Trades**: Lịch sử giao dịch real-time với thông tin price, quantity, và buyer/seller

### 2. Batch Processing & Aggregation

Spark batch jobs tổng hợp dữ liệu từ 1m interval thành các khung thời gian lớn hơn:
- **5 phút (5m)**: Cho phân tích ngắn hạn
- **1 giờ (1h)**: Cho phân tích trung bình
- **4 giờ (4h)**: Cho phân tích dài hạn
- **1 ngày (1d)**: Cho phân tích xu hướng

Mỗi aggregation job được schedule tự động bởi Airflow.

### 3. Machine Learning Predictions

![Chart](images/Chart.png)

Hệ thống ML sử dụng Spark ML Linear Regression để dự đoán:
- **Giá cryptocurrency** trong 5 phút tiếp theo
- **Hướng biến động** (tăng/giảm) với confidence score
- **Technical indicators** được tính toán tự động (RSI, MACD, Moving Averages)

Model được training định kỳ với dữ liệu lịch sử 30 ngày.

### 4. Coin Ranking System

![Ranking](images/rank.png)

Tính toán và hiển thị ranking các coin real-time:
- **Top Gainers**: Coin tăng giá nhiều nhất (percent change)
- **Top Losers**: Coin giảm giá nhiều nhất
- **Metrics**: Percent change, volume, market cap, price change

Ranking được cập nhật real-time thông qua Spark streaming job.

### 5. Real-time Trading Dashboard

Giao diện web với các tính năng:
- **Interactive candlestick charts**: TradingView charting library với zoom, pan, và technical indicators
- **Real-time orderbook visualization**: Depth chart với color coding
- **Market trades feed**: Real-time trades với buy/sell indicators
- **Coin ranking table**: Sortable table với pagination
- **ML predictions display**: Hiển thị predictions với confidence scores và direction indicators

## 🛠️ Công Nghệ Sử Dụng

### Data Processing
- **Apache Kafka**: Message streaming platform cho real-time data ingestion
- **Apache Spark**: Distributed data processing
  - Spark SQL cho data transformation
  - Spark MLlib cho machine learning
  - Spark Structured Streaming cho real-time processing
- **Apache Airflow**: Workflow orchestration và scheduling

### Storage
- **MongoDB**: Document database cho historical OHLC data
- **Redis**: In-memory cache cho real-time data và session management

### Backend
- **FastAPI**: High-performance Python web framework
- **WebSocket**: Real-time bidirectional communication
- **Pydantic**: Data validation và serialization
- **Motor**: Async MongoDB driver
- **Redis Async**: Async Redis client

### Frontend
- **Next.js 14**: React framework với App Router và SSR
- **TypeScript**: Type-safe JavaScript
- **TradingView Charting Library**: Professional charting
- **Tailwind CSS**: Utility-first CSS framework
- **shadcn/ui**: Component library

### Infrastructure
- **Kubernetes**: Container orchestration
- **Docker**: Containerization
- **Helm**: Kubernetes package manager
- **Prometheus**: Metrics monitoring và alerting
- **Grafana**: Visualization và dashboards
- **Strimzi**: Kafka operator cho Kubernetes

## 📦 Cài Đặt & Triển Khai

### Prerequisites

- **Kubernetes cluster** (Minikube, Kind, hoặc cloud K8s như GKE, EKS, AKS)
- **kubectl** configured và có quyền truy cập cluster
- **Helm 3.x** installed
- **Docker** (cho local development)
- **Python 3.9+** (cho local development)

### 1. Deploy Infrastructure Components

```bash
# Deploy Kafka (Strimzi Operator)
cd Kafka/strimzi-kafka-operator
kubectl apply -f install/cluster-operator/

# Đợi operator ready
kubectl wait --for=condition=ready pod -l name=strimzi-cluster-operator -n strimzi-system --timeout=300s

# Deploy Kafka cluster
kubectl apply -f kafka-helm.yaml

# Deploy MongoDB
cd mongodb
helm install mongodb . -n crypto-infra --create-namespace

# Deploy Redis
cd redis
helm install redis . -n crypto-infra

# Deploy Prometheus & Grafana
cd deploy/helm
./deploy-monitoring.sh
```

### 2. Deploy Application Components

```bash
# Tạo namespace
cd deploy/k8s_web
kubectl apply -f namespace.yaml

# Deploy ConfigMap và Secrets
kubectl apply -f configmap.yaml
kubectl apply -f secret.yaml

# Deploy Backend API
kubectl apply -f backend-deployment.yaml
kubectl apply -f backend-service.yaml

# Deploy Frontend
kubectl apply -f frontend-deployment.yaml
kubectl apply -f frontend-service.yaml

# Deploy Ingress
kubectl apply -f ingress.yaml
```

### 3. Start Data Producers

```bash
# Start Kafka producers (có thể chạy trong pods hoặc local)
cd Kafka

# Producer cho kline data
python binance_producer.py &

# Producer cho orderbook và trades
python binance_orderbook_trades_producer.py &

# Consumer từ Kafka vào Redis
python redis_consumer.py &
```

### 4. Start Airflow DAGs

Truy cập Airflow UI (thường tại `http://localhost:8080`) và enable các DAGs:
- `ohlc_5m_spark_aggregator` - Chạy mỗi 5 phút
- `ohlc_1h_spark_aggregator` - Chạy mỗi giờ
- `ohlc_4h_spark_aggregator` - Chạy mỗi 4 giờ
- `ohlc_1d_spark_aggregator` - Chạy mỗi ngày
- `ml_prediction_dag` - Training model định kỳ

## 🔧 Cấu Hình

### Environment Variables

**Backend (FastAPI)**:
```bash
MONGO_URI=mongodb://mongodb:27017
MONGO_DB=CRYPTO
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_PASSWORD=
KAFKA_BOOTSTRAP=my-cluster-kafka-bootstrap:9092
KAFKA_TOPIC=crypto_kline_1m
CORS_ORIGINS=["http://localhost:3000"]
```

**Kafka Producers**:
```bash
KAFKA_BROKER=my-cluster-kafka-bootstrap.crypto-infra:9092
KAFKA_TOPIC=crypto_kline_1m
```

**Frontend**:
```bash
NEXT_PUBLIC_API_URL=http://backend-service:8000
NEXT_PUBLIC_WS_URL=ws://backend-service:8000
```

### MongoDB Collections

- `5m_kline`: OHLC data 5 phút
- `1h_kline`: OHLC data 1 giờ
- `4h_kline`: OHLC data 4 giờ
- `1d_kline`: OHLC data 1 ngày
- `predictions`: ML prediction results với metadata

### Redis Keys Structure

- `crypto:{symbol}:1m:latest`: Latest kline data
- `crypto:{symbol}:1m:{timestamp}`: Historical kline data (sorted set index)
- `crypto:{symbol}:1m:index`: Sorted set chứa timestamps
- `orderbook:{symbol}:latest`: Orderbook snapshot với bids/asks
- `trades:{symbol}:list`: Market trades list (sorted set)
- `ranking:top_gainers`: Coin ranking data (JSON array)
- `crypto:prediction:{symbol}`: ML predictions với confidence scores

## 📊 API Endpoints

### REST API

#### Historical Data
- `GET /ohlc?symbol=BTCUSDT&interval=5m&limit=200`: Lấy dữ liệu OHLC historical từ MongoDB
- `GET /ohlc?collection=5m_kline&symbol=BTCUSDT&limit=200`: Lấy từ collection cụ thể

#### Real-time Data
- `GET /ohlc/realtime?symbol=BTCUSDT&limit=200`: Lấy dữ liệu OHLC real-time từ Redis
- `GET /latest?symbol=BTCUSDT`: Lấy latest kline data
- `GET /orderbook?symbol=BTCUSDT&limit=20`: Lấy orderbook snapshot
- `GET /trades?symbol=BTCUSDT&limit=50`: Lấy market trades

#### Ranking & Predictions
- `GET /ranking/top-gainers?limit=100&type=gainers`: Lấy coin ranking (gainers)
- `GET /ranking/top-gainers?limit=100&type=losers`: Lấy coin ranking (losers)
- `GET /prediction/BTCUSDT`: Lấy ML prediction cho symbol

### WebSocket Endpoints

- `WS /ws/kline?symbol=BTCUSDT&limit=100`: Real-time kline stream
  - Message types: `initial`, `latest`, `update`
- `WS /ws/orderbook?symbol=BTCUSDT`: Real-time orderbook stream
  - Message types: `initial`, `update`
- `WS /ws/trades?symbol=BTCUSDT&limit=50`: Real-time trades stream
  - Message types: `initial`, `update`

## 🧪 Testing

### Test Backend API

```bash
cd backend_fastapi
python test_api.py

# Hoặc test với curl
curl http://localhost:8000/health
curl http://localhost:8000/ohlc?symbol=BTCUSDT&limit=10
```

### Test Kafka Producer

```bash
cd Kafka
python binance_producer.py

# Kiểm tra messages trong Kafka
kubectl exec -it my-cluster-kafka-0 -n crypto-infra -- kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic crypto_kline_1m \
  --from-beginning
```

### Test Spark Jobs Locally

```bash
cd Spark/batch
python ohlc_5m_aggregator.py

# Hoặc submit qua Spark on K8s
kubectl apply -f Spark/apps/batch/ohlc-5m-aggregator.yaml
```

## 📈 Monitoring

### Prometheus Metrics

Hệ thống expose các metrics sau:
- **Kafka**: Producer/consumer lag, throughput, error rate
- **Spark**: Job execution time, task completion rate, resource usage
- **API**: Request latency, error rate, throughput
- **Redis**: Memory usage, hit/miss ratio, connection count
- **MongoDB**: Connection pool, query latency, operation count

### Grafana Dashboards

Truy cập Grafana tại `http://localhost:3000` (default: admin/admin) để xem:
- **System Overview**: CPU, memory, network usage
- **Application Performance**: API latency, error rates
- **Data Pipeline Health**: Kafka lag, Spark job status
- **Business Metrics**: Trading volume, prediction accuracy

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Check pods status
kubectl get pods -n crypto-infra

# Check services
kubectl get svc -n crypto-infra
```

## 🔍 Troubleshooting

### Kafka không nhận được dữ liệu
1. Kiểm tra Kafka broker connectivity: `kubectl get pods -n crypto-infra | grep kafka`
2. Verify WebSocket connection to Binance: Check producer logs
3. Check topic exists: `kubectl exec -it kafka-pod -- kafka-topics.sh --list`
4. Review producer logs: `kubectl logs -f <producer-pod>`

### Spark jobs fail
1. Kiểm tra Spark operator logs: `kubectl logs -f spark-operator`
2. Verify MongoDB connection từ Spark driver pod
3. Check resource limits: `kubectl describe sparkapplication <app-name>`
4. Review Spark driver logs: `kubectl logs <driver-pod>`

### Frontend không hiển thị data
1. Kiểm tra WebSocket connection: Open browser DevTools → Network → WS
2. Verify Redis có dữ liệu: `kubectl exec -it redis-pod -- redis-cli KEYS "*"`
3. Check backend API health: `curl http://backend-service:8000/health`
4. Review browser console errors

### MongoDB connection issues
1. Verify MongoDB pod running: `kubectl get pods -n crypto-infra | grep mongodb`
2. Check connection string trong ConfigMap
3. Test connection: `kubectl exec -it mongodb-pod -- mongosh`

## 📝 License

MIT License

## 👥 Contributors

- **Vương Văn Thành** (20225094)
- **Phạm Huy Sơn** (20225080)
- **Trần Tuấn Hùng** (20225000)
- **Vũ Anh Huy** (20220029)
- **Trần Tuấn Hải** (20224976)

## 🙏 Acknowledgments

- **Binance API** for providing real-time cryptocurrency market data
- **Apache Foundation** for open-source Big Data tools (Kafka, Spark, Airflow)
- **TradingView** for charting library inspiration
- **Kubernetes Community** for excellent container orchestration platform

---

## ⚠️ Lưu Ý

**Đây là dự án học tập và nghiên cứu**. Hệ thống được xây dựng cho mục đích giáo dục và không nên được sử dụng cho mục đích trading thực tế mà không có proper risk management và testing kỹ lưỡng.

**Disclaimer**: Dự đoán giá từ ML model chỉ mang tính chất tham khảo và không đảm bảo độ chính xác. Luôn thực hiện nghiên cứu riêng (DYOR) trước khi đưa ra quyết định đầu tư.

---

[**⬆️ Back to top**](#hệ-thống-xử-lý-dữ-liệu-cryptocurrency---real-time-trading-platform)
