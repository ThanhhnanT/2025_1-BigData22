# Dockerfile chung cho cả producer và consumer
FROM python:3.11-slim

WORKDIR /app

# Copy requirements và cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY binance_producer.py binance_consumer.py ./

# Default command (sẽ được override trong K8s deployment)
CMD ["python", "binance_producer.py"]

