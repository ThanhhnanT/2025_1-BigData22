"""
Airflow DAG: Trigger PySpark jobs cho crypto data pipeline
- Spark Redis Writer (streaming - chạy liên tục)
- Spark OHLC 5m Aggregator (streaming - chạy liên tục)
- Spark Batch MongoDB Writer (batch - chạy mỗi ngày)
"""
from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.bash import BashOperator
import os

# Config
SPARK_MASTER = os.getenv("SPARK_MASTER", "local[*]")
SPARK_APP_PATH = os.getenv("SPARK_APP_PATH", "/path/to/spark/jobs")
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "192.168.49.2:30113")
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")

default_args = {
    "owner": "crypto_team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}

# DAG cho Spark Streaming Jobs (chạy liên tục)
with DAG(
    dag_id="spark_crypto_streaming",
    default_args=default_args,
    description="PySpark Streaming Jobs - Redis Writer và OHLC Aggregator",
    schedule=None,  # Manual trigger hoặc schedule riêng
    catchup=False,
    tags=["crypto", "spark", "streaming"],
    start_date=datetime(2024, 1, 1),
) as streaming_dag:
    
    # Spark Redis Writer
    spark_redis_writer = SparkSubmitOperator(
        task_id="spark_redis_writer",
        application=f"{SPARK_APP_PATH}/spark_redis_writer.py",
        name="CryptoRedisWriter",
        conn_id="spark_default",
        conf={
            "spark.jars.packages": "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0",
            "spark.sql.streaming.checkpointLocation": "/tmp/spark_redis_checkpoint",
        },
        env_vars={
            "KAFKA_BROKER": KAFKA_BROKER,
            "KAFKA_TOPIC": "crypto_kline_1m",
            "REDIS_HOST": REDIS_HOST,
            "REDIS_PORT": "6379",
        },
        driver_memory="1g",
        executor_memory="2g",
    )
    
    # Spark OHLC 5m Aggregator
    spark_ohlc_5m = SparkSubmitOperator(
        task_id="spark_ohlc_5m_aggregator",
        application=f"{SPARK_APP_PATH}/spark_ohlc_5m_aggregator.py",
        name="CryptoOHLC5mAggregator",
        conn_id="spark_default",
        conf={
            "spark.jars.packages": "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.mongodb.spark:mongo-spark-connector_2.12:3.0.1",
            "spark.sql.streaming.checkpointLocation": "/tmp/spark_ohlc_5m_checkpoint",
        },
        env_vars={
            "KAFKA_BROKER": KAFKA_BROKER,
            "KAFKA_TOPIC": "crypto_kline_1m",
            "REDIS_HOST": REDIS_HOST,
            "REDIS_PORT": "6379",
            "MONGO_URI": MONGO_URI,
            "MONGO_DB": "crypto_history",
            "MONGO_COLLECTION": "candles",
        },
        driver_memory="1g",
        executor_memory="2g",
    )
    
    # Chạy song song
    [spark_redis_writer, spark_ohlc_5m]

# DAG cho Spark Batch Job (chạy mỗi ngày)
with DAG(
    dag_id="spark_crypto_batch",
    default_args=default_args,
    description="PySpark Batch Job - MongoDB Writer",
    schedule="0 1 * * *",  # 00:00 VN time
    catchup=False,
    tags=["crypto", "spark", "batch"],
    start_date=datetime(2024, 1, 1),
) as batch_dag:
    
    # Spark Batch MongoDB Writer
    spark_batch_mongo = SparkSubmitOperator(
        task_id="spark_batch_mongodb_writer",
        application=f"{SPARK_APP_PATH}/spark_batch_mongodb_writer.py",
        name="CryptoBatchMongoWriter",
        conn_id="spark_default",
        conf={
            "spark.jars.packages": "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0,org.mongodb.spark:mongo-spark-connector_2.12:3.0.1",
        },
        env_vars={
            "KAFKA_BROKER": KAFKA_BROKER,
            "KAFKA_TOPIC": "crypto_kline_1m",
            "MONGO_URI": MONGO_URI,
            "MONGO_DB": "crypto_history",
            "MONGO_COLLECTION": "candles",
        },
        driver_memory="1g",
        executor_memory="2g",
    )
    
    spark_batch_mongo

