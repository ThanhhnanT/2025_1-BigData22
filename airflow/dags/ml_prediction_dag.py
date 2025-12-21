"""
Airflow DAG for Crypto Price Prediction ML Pipeline
- Trains model daily
- Runs predictions every 5 minutes
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.sensors.filesystem import FileSensor
import os

# Path to SparkApplication YAMLs inside Airflow container
SPARK_APPS_PATH = "/opt/airflow/dags/spark_apps"

default_args = {
    'owner': 'crypto_team',
    'depends_on_past': False,
    'start_date': datetime(2025, 12, 18),
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=1),
}


# Training DAG - runs daily at 2 AM UTC
with DAG(
    dag_id='crypto_ml_training',
    default_args=default_args,
    description='Train crypto price prediction model using Spark',
    schedule='0 2 * * *',  # Daily at 2 AM UTC
    catchup=False,
    tags=['ml', 'training', 'crypto', 'spark'],
    max_active_runs=1,
) as training_dag:
    
    train_model = BashOperator(
        task_id='train_linear_regression',
        bash_command=f"""
        cd {SPARK_APPS_PATH} && \
        echo "🧹 Cleaning up any existing training job..." && \
        kubectl delete sparkapplication train-price-prediction -n crypto-infra --ignore-not-found=true && \
        sleep 3 && \
        echo "📝 Applying training SparkApplication manifest..." && \
        kubectl apply -f train-price-prediction.yaml && \
        sleep 5 && \
        echo "🔍 Waiting for driver pod to be created..." && \
        timeout 90 bash -c 'until kubectl get pods -n crypto-infra | grep -q "train-price-prediction.*driver"; do sleep 3; done' || true && \
        echo "🔍 Driver pod found, waiting for completion..." && \
        DRIVER_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "train-price-prediction.*driver" | awk '{{print $1}}' | head -1) && \
        if [ -n "$DRIVER_POD" ]; then \
          echo "📝 Monitoring pod: $DRIVER_POD" && \
          kubectl wait --for=condition=Ready=false --timeout=1800s pod/$DRIVER_POD -n crypto-infra || true && \
          echo "✅ Training completed. Getting logs..." && \
          kubectl logs -n crypto-infra $DRIVER_POD --tail=200 && \
          echo "📊 Checking final status..." && \
          kubectl get sparkapplication train-price-prediction -n crypto-infra 2>/dev/null || echo "SparkApplication may have been deleted" && \
          exit 0; \
        else \
          echo "❌ Driver pod not found. Checking SparkApplication status..." && \
          kubectl get sparkapplication train-price-prediction -n crypto-infra -o yaml | grep -A 30 "status:" || echo "SparkApplication not found" && \
          exit 1; \
        fi
        """,
    )
    
    train_model


# Prediction DAG - runs every 1 minute
with DAG(
    dag_id='crypto_ml_prediction',
    default_args=default_args,
    description='Generate crypto price predictions every minute using trained model',
    schedule='*/1 * * * *',  # Every 1 minute
    catchup=False,
    tags=['ml', 'prediction', 'crypto', 'spark'],
    max_active_runs=1,
) as prediction_dag:
    
    # Note: In production, you might want to add a sensor to check if model exists
    # before running predictions. For now, we assume training has run at least once.
    
    generate_predictions = BashOperator(
        task_id='predict_prices',
        bash_command=f"""
        cd {SPARK_APPS_PATH} && \
        echo "🧹 Cleaning up any existing prediction job..." && \
        kubectl delete sparkapplication predict-price -n crypto-infra --ignore-not-found=true && \
        sleep 2 && \
        echo "📝 Applying prediction SparkApplication manifest..." && \
        kubectl apply -f predict-price.yaml && \
        sleep 5 && \
        echo "🔍 Waiting for driver pod to be created..." && \
        timeout 90 bash -c 'until kubectl get pods -n crypto-infra | grep -q "predict-price.*driver"; do sleep 3; done' || true && \
        echo "🔍 Driver pod found, waiting for completion..." && \
        DRIVER_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "predict-price.*driver" | awk '{{print $1}}' | head -1) && \
        if [ -n "$DRIVER_POD" ]; then \
          echo "📝 Monitoring pod: $DRIVER_POD" && \
          echo "⏳ Waiting for pod to complete (max 20 minutes)..." && \
          # Wait for pod phase to be Succeeded or Failed, or check SparkApplication status
          MAX_ITERATIONS=120 && \
          ITERATION=0 && \
          while [ $ITERATION -lt $MAX_ITERATIONS ]; do \
            PHASE=$(kubectl get pod $DRIVER_POD -n crypto-infra -o jsonpath="{{.status.phase}}" 2>/dev/null || echo "NotFound"); \
            SPARK_STATE=$(kubectl get sparkapplication predict-price -n crypto-infra -o jsonpath="{{.status.applicationState.state}}" 2>/dev/null || echo "Unknown"); \
            if [ "$PHASE" = "Succeeded" ] || [ "$PHASE" = "Failed" ]; then \
              echo "✅ Pod phase: $PHASE"; \
              break; \
            elif [ "$SPARK_STATE" = "COMPLETED" ] || [ "$SPARK_STATE" = "SUCCEEDING" ]; then \
              echo "✅ SparkApplication completed: $SPARK_STATE"; \
              break; \
            elif [ "$SPARK_STATE" = "FAILED" ] || [ "$SPARK_STATE" = "FAILING" ]; then \
              echo "❌ SparkApplication failed: $SPARK_STATE"; \
              break; \
            elif [ "$PHASE" = "NotFound" ]; then \
              echo "⚠️  Pod not found, checking SparkApplication status..."; \
              break; \
            else \
              echo "⏳ Pod still running (phase: $PHASE, state: $SPARK_STATE), waiting... ($ITERATION/$MAX_ITERATIONS)"; \
              sleep 10; \
              ITERATION=$((ITERATION + 1)); \
            fi; \
          done && \
          echo "📊 Final status check..." && \
          SPARK_STATUS=$(kubectl get sparkapplication predict-price -n crypto-infra -o jsonpath="{{.status.applicationState.state}}" 2>/dev/null || echo "Unknown") && \
          echo "   SparkApplication state: $SPARK_STATUS" && \
          echo "✅ Getting pod logs..." && \
          kubectl logs -n crypto-infra $DRIVER_POD --tail=200 2>/dev/null || echo "⚠️  Could not get logs" && \
          echo "📊 Final SparkApplication status:" && \
          kubectl get sparkapplication predict-price -n crypto-infra 2>/dev/null || echo "SparkApplication may have been deleted" && \
          # Check if job succeeded
          if [ "$SPARK_STATUS" = "COMPLETED" ] || [ "$SPARK_STATUS" = "SUCCEEDING" ]; then \
            echo "✅ Prediction job completed successfully"; \
            exit 0; \
          elif [ "$SPARK_STATUS" = "FAILED" ] || [ "$SPARK_STATUS" = "FAILING" ]; then \
            echo "❌ Prediction job failed"; \
            exit 1; \
          else \
            echo "⚠️  Unknown status, but continuing..."; \
            exit 0; \
          fi; \
        else \
          echo "❌ Driver pod not found. Checking SparkApplication status..." && \
          kubectl get sparkapplication predict-price -n crypto-infra -o yaml | grep -A 30 "status:" || echo "SparkApplication not found" && \
          exit 1; \
        fi
        """,
    )
    
    generate_predictions
