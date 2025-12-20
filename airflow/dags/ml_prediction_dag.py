"""
Airflow DAG for Crypto Price Prediction ML Pipeline
- Trains model daily
- Runs predictions every 5 minutes
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import SparkKubernetesOperator
from airflow.operators.python import PythonOperator

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'start_date': datetime(2025, 12, 18),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}


# Training DAG - runs daily
with DAG(
    'crypto_ml_training',
    default_args=default_args,
    description='Train crypto price prediction model',
    schedule_interval='0 2 * * *',  # Daily at 2 AM UTC
    catchup=False,
    tags=['ml', 'training', 'crypto'],
) as training_dag:
    
    train_model = SparkKubernetesOperator(
        task_id='train_linear_regression',
        namespace='default',
        application_file='train_price_prediction.py',
        kubernetes_conn_id='kubernetes_default',
        do_xcom_push=True,
        env_vars={
            'MONGO_URI': '{{ var.value.MONGO_URI }}',
            'MONGO_DB': 'CRYPTO',
            'MONGO_COLLECTION': '5m_kline',
            'MODEL_PATH': '/mnt/models/crypto_lr_model',
            'TRAINING_DAYS': '30',
        },
    )


# Prediction DAG - runs every 5 minutes
with DAG(
    'crypto_ml_prediction',
    default_args=default_args,
    description='Generate crypto price predictions',
    schedule_interval='*/5 * * * *',  # Every 5 minutes
    catchup=False,
    tags=['ml', 'prediction', 'crypto'],
) as prediction_dag:
    
    generate_predictions = SparkKubernetesOperator(
        task_id='predict_prices',
        namespace='default',
        application_file='predict_price.py',
        kubernetes_conn_id='kubernetes_default',
        do_xcom_push=True,
        env_vars={
            'MONGO_URI': '{{ var.value.MONGO_URI }}',
            'MONGO_DB': 'CRYPTO',
            'MONGO_INPUT_COLLECTION': '5m_kline',
            'MONGO_PREDICTION_COLLECTION': 'predictions',
            'REDIS_HOST': '{{ var.value.REDIS_HOST }}',
            'REDIS_PORT': '6379',
            'MODEL_PATH': '/mnt/models/crypto_lr_model',
        },
    )
