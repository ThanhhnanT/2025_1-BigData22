from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Đường dẫn SparkApplication YAMLs bên trong container Airflow
# Đã được copy trong Dockerfile:
#   COPY --chown=airflow:root Spark/apps/batch/ /opt/airflow/dags/spark_apps/
SPARK_APPS_PATH = "/opt/airflow/dags/spark_apps"

default_args = {
    "owner": "crypto_team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

# DAG 5m - Run every 5 minutes
with DAG(
    dag_id="ohlc_5m_spark_aggregator",
    default_args=default_args,
    description="Aggregate OHLC 5m using Spark on Minikube",
    schedule="*/5 * * * *",
    catchup=False,
    tags=["crypto", "ohlc", "spark", "5m"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_5m:
    
    aggregate_5m_task = BashOperator(
        task_id="spark_aggregate_5m",
        bash_command=f"""
        cd {SPARK_APPS_PATH} && \
        echo "🧹 Cleaning up any existing SparkApplication..." && \
        kubectl delete sparkapplication ohlc-5m-aggregator -n crypto-infra --ignore-not-found=true && \
        sleep 3 && \
        echo "📝 Applying SparkApplication manifest..." && \
        kubectl apply -f ohlc-5m-aggregator.yaml && \
        sleep 5 && \
        echo "🔍 Waiting for driver pod to be created..." && \
        timeout 60 bash -c 'until kubectl get pods -n crypto-infra | grep -q "ohlc-5m-aggregator.*driver"; do sleep 2; done' || true && \
        echo "🔍 Driver pod found, waiting for completion..." && \
        DRIVER_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "ohlc-5m-aggregator.*driver" | awk '{{print $1}}' | head -1) && \
        if [ -n "$DRIVER_POD" ]; then \
          echo "📝 Waiting for pod: $DRIVER_POD" && \
          kubectl wait --for=condition=Ready=false --timeout=600s pod/$DRIVER_POD -n crypto-infra || true && \
          echo "✅ Pod completed. Getting logs..." && \
          kubectl logs -n crypto-infra $DRIVER_POD --tail=100 && \
          echo "📊 Checking final status..." && \
          kubectl get sparkapplication ohlc-5m-aggregator -n crypto-infra 2>/dev/null || echo "SparkApplication may have been deleted" && \
          exit 0; \
        else \
          echo "❌ Driver pod not found. Checking SparkApplication status..." && \
          kubectl get sparkapplication ohlc-5m-aggregator -n crypto-infra -o yaml | grep -A 20 "status:" || echo "SparkApplication not found" && \
          exit 1; \
        fi
        """,
    )
    
    aggregate_5m_task

with DAG(
    dag_id="ohlc_1h_spark_aggregator",
    default_args=default_args,
    description="Aggregate OHLC 1h using Spark on Minikube",
    schedule="0 * * * *",  # Every hour at minute 0
    catchup=False,
    tags=["crypto", "ohlc", "spark", "1h"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_1h:
    
    aggregate_1h_task = BashOperator(
        task_id="spark_aggregate_1h",
        bash_command=f"""
        cd {SPARK_APPS_PATH} && \
        echo "🧹 Cleaning up any existing SparkApplication..." && \
        kubectl delete sparkapplication ohlc-1h-aggregator -n crypto-infra --ignore-not-found=true && \
        sleep 3 && \
        echo "📝 Applying SparkApplication manifest..." && \
        kubectl apply -f ohlc-1h-aggregator.yaml && \
        sleep 5 && \
        echo "🔍 Waiting for driver pod to be created..." && \
        timeout 60 bash -c 'until kubectl get pods -n crypto-infra | grep -q "ohlc-1h-aggregator.*driver"; do sleep 2; done' || true && \
        echo "🔍 Driver pod found, waiting for completion..." && \
        DRIVER_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "ohlc-1h-aggregator.*driver" | awk '{{print $1}}' | head -1) && \
        if [ -n "$DRIVER_POD" ]; then \
          echo "📝 Waiting for pod: $DRIVER_POD" && \
          kubectl wait --for=condition=Ready=false --timeout=600s pod/$DRIVER_POD -n crypto-infra || true && \
          echo "✅ Pod completed. Getting logs..." && \
          kubectl logs -n crypto-infra $DRIVER_POD --tail=100 && \
          echo "📊 Checking final status..." && \
          kubectl get sparkapplication ohlc-1h-aggregator -n crypto-infra 2>/dev/null || echo "SparkApplication may have been deleted" && \
          exit 0; \
        else \
          echo "❌ Driver pod not found. Checking SparkApplication status..." && \
          kubectl get sparkapplication ohlc-1h-aggregator -n crypto-infra -o yaml | grep -A 20 "status:" || echo "SparkApplication not found" && \
          exit 1; \
        fi
        """,
    )
    
    aggregate_1h_task

# DAG 4h - Run every 4 hours
with DAG(
    dag_id="ohlc_4h_spark_aggregator",
    default_args=default_args,
    description="Aggregate OHLC 4h using Spark on Minikube",
    schedule="0 */4 * * *",  # Every 4 hours at minute 0
    catchup=False,
    tags=["crypto", "ohlc", "spark", "4h"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_4h:
    
    aggregate_4h_task = BashOperator(
        task_id="spark_aggregate_4h",
        bash_command=f"""
        cd {SPARK_APPS_PATH} && \
        echo "🧹 Cleaning up any existing SparkApplication..." && \
        kubectl delete sparkapplication ohlc-4h-aggregator -n crypto-infra --ignore-not-found=true && \
        sleep 3 && \
        echo "📝 Applying SparkApplication manifest..." && \
        kubectl apply -f ohlc-4h-aggregator.yaml && \
        sleep 5 && \
        echo "🔍 Waiting for driver pod to be created..." && \
        timeout 60 bash -c 'until kubectl get pods -n crypto-infra | grep -q "ohlc-4h-aggregator.*driver"; do sleep 2; done' || true && \
        echo "🔍 Driver pod found, waiting for completion..." && \
        DRIVER_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "ohlc-4h-aggregator.*driver" | awk '{{print $1}}' | head -1) && \
        if [ -n "$DRIVER_POD" ]; then \
          echo "📝 Waiting for pod: $DRIVER_POD" && \
          kubectl wait --for=condition=Ready=false --timeout=600s pod/$DRIVER_POD -n crypto-infra || true && \
          echo "✅ Pod completed. Getting logs..." && \
          kubectl logs -n crypto-infra $DRIVER_POD --tail=100 && \
          echo "📊 Checking final status..." && \
          kubectl get sparkapplication ohlc-4h-aggregator -n crypto-infra 2>/dev/null || echo "SparkApplication may have been deleted" && \
          exit 0; \
        else \
          echo "❌ Driver pod not found. Checking SparkApplication status..." && \
          kubectl get sparkapplication ohlc-4h-aggregator -n crypto-infra -o yaml | grep -A 20 "status:" || echo "SparkApplication not found" && \
          exit 1; \
        fi
        """,
    )
    
    aggregate_4h_task

# DAG 1d - Run daily at midnight UTC
with DAG(
    dag_id="ohlc_1d_spark_aggregator",
    default_args=default_args,
    description="Aggregate OHLC 1d using Spark on Minikube",
    schedule="0 0 * * *",  # Daily at 00:00 UTC
    catchup=False,
    tags=["crypto", "ohlc", "spark", "1d"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_1d:
    
    aggregate_1d_task = BashOperator(
        task_id="spark_aggregate_1d",
        bash_command=f"""
        cd {SPARK_APPS_PATH} && \
        echo "🧹 Cleaning up any existing SparkApplication..." && \
        kubectl delete sparkapplication ohlc-1d-aggregator -n crypto-infra --ignore-not-found=true && \
        sleep 3 && \
        echo "📝 Applying SparkApplication manifest..." && \
        kubectl apply -f ohlc-1d-aggregator.yaml && \
        sleep 5 && \
        echo "🔍 Waiting for driver pod to be created..." && \
        timeout 60 bash -c 'until kubectl get pods -n crypto-infra | grep -q "ohlc-1d-aggregator.*driver"; do sleep 2; done' || true && \
        echo "🔍 Driver pod found, waiting for completion..." && \
        DRIVER_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "ohlc-1d-aggregator.*driver" | awk '{{print $1}}' | head -1) && \
        if [ -n "$DRIVER_POD" ]; then \
          echo "📝 Waiting for pod: $DRIVER_POD" && \
          kubectl wait --for=condition=Ready=false --timeout=600s pod/$DRIVER_POD -n crypto-infra || true && \
          echo "✅ Pod completed. Getting logs..." && \
          kubectl logs -n crypto-infra $DRIVER_POD --tail=100 && \
          echo "📊 Checking final status..." && \
          kubectl get sparkapplication ohlc-1d-aggregator -n crypto-infra 2>/dev/null || echo "SparkApplication may have been deleted" && \
          exit 0; \
        else \
          echo "❌ Driver pod not found. Checking SparkApplication status..." && \
          kubectl get sparkapplication ohlc-1d-aggregator -n crypto-infra -o yaml | grep -A 20 "status:" || echo "SparkApplication not found" && \
          exit 1; \
        fi
        """,
    )
    
    aggregate_1d_task


