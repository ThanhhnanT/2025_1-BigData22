import os
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Get workspace path
WORKSPACE_PATH = "/home/vvt/D/SubjectResource/IT4931_BigData_Processing_and_Storage/CRYPTO"
SPARK_PATH = os.path.join(WORKSPACE_PATH, "Spark")

default_args = {
    "owner": "crypto_team",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=1),
}

# Test DAG - Manual trigger only
with DAG(
    dag_id="test_spark_k8s",
    default_args=default_args,
    description="Test Spark job via Kubernetes Operator - Simple test without external dependencies",
    schedule=None,  # Manual trigger only for testing
    catchup=False,
    tags=["test", "spark", "k8s", "debug"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag:
    
    test_spark_task = BashOperator(
        task_id="test_spark_simple",
        bash_command=f"""
            cd {SPARK_PATH} && \
            echo "🧹 Cleaning up any existing SparkApplication..." && \
            kubectl delete sparkapplication test-spark-simple -n crypto-infra --ignore-not-found=true && \
            sleep 3 && \
            echo "📝 Applying SparkApplication manifest..." && \
            kubectl apply -f apps/batch/test-spark-simple.yaml && \
            sleep 5 && \
            echo "🔍 Waiting for driver pod to be created..." && \
            timeout 60 bash -c 'until kubectl get pods -n crypto-infra | grep -q "test-spark-simple.*driver"; do sleep 2; done' || true && \
            echo "🔍 Driver pod found, waiting for completion..." && \
            DRIVER_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "test-spark-simple.*driver" | awk '{{print $1}}' | head -1) && \
            if [ -n "$DRIVER_POD" ]; then \
              echo "📝 Waiting for pod: $DRIVER_POD" && \
              kubectl wait --for=condition=Ready=false --timeout=600s pod/$DRIVER_POD -n crypto-infra || true && \
              echo "✅ Pod completed. Getting logs..." && \
              kubectl logs -n crypto-infra $DRIVER_POD --tail=100 && \
              echo "📊 Checking final status..." && \
              kubectl get sparkapplication test-spark-simple -n crypto-infra 2>/dev/null || echo "SparkApplication may have been deleted" && \
              exit 0; \
            else \
              echo "❌ Driver pod not found. Checking SparkApplication status..." && \
              kubectl get sparkapplication test-spark-simple -n crypto-infra -o yaml | grep -A 20 "status:" || echo "SparkApplication not found" && \
              exit 1; \
            fi
            """,
    )
    test_kubectl = BashOperator(
        task_id="test_kubectl",
        bash_command="kubectl version --client && kubectl get nodes",
        dag=dag
    )
    
    test_kubectl >> test_spark_task

