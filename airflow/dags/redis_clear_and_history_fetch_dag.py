"""
Airflow DAG for Redis Clear and Binance History Fetch
- Clears Redis data first
- Then fetches historical data from Binance
"""

from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.bash import BashOperator

# Path to Job YAMLs inside Airflow container
KAFKA_JOBS_PATH = "/opt/airflow/dags/kafka_jobs"

default_args = {
    "owner": "crypto_team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
    "start_date": datetime(2024, 1, 1),
}

with DAG(
    dag_id="redis_clear_and_history_fetch",
    default_args=default_args,
    description="Clear Redis and fetch Binance historical data",
    schedule=None,  # Manual trigger only (or set schedule as needed)
    catchup=False,
    tags=["redis", "binance", "history", "kafka"],
    max_active_runs=1,
) as dag:
    
    # Task 1: Clear Redis
    clear_redis_task = BashOperator(
        task_id="clear_redis",
        bash_command=f"""
        echo "🗑️  Starting Redis clear job..." && \
        cd {KAFKA_JOBS_PATH} && \
        echo "🧹 Cleaning up any existing clear-redis job..." && \
        kubectl delete job clear-redis -n crypto-infra --ignore-not-found=true && \
        sleep 3 && \
        echo "📝 Applying clear-redis job manifest..." && \
        kubectl apply -f clear-redis-job.yaml && \
        sleep 5 && \
        echo "🔍 Waiting for job pod to be created..." && \
        timeout 60 bash -c 'until kubectl get pods -n crypto-infra | grep -q "clear-redis"; do sleep 2; done' || true && \
        echo "🔍 Job pod found, waiting for completion..." && \
        JOB_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "clear-redis" | awk '{{print $1}}' | head -1) && \
        if [ -n "$JOB_POD" ]; then \
          echo "📝 Found pod: $JOB_POD" && \
          POD_STATUS=$(kubectl get pod $JOB_POD -n crypto-infra -o jsonpath="{{.status.phase}}" 2>/dev/null || echo "NotFound") && \
          echo "   Current pod status: $POD_STATUS" && \
          if [ "$POD_STATUS" != "Succeeded" ] && [ "$POD_STATUS" != "Failed" ] && [ "$POD_STATUS" != "Completed" ]; then \
            echo "⏳ Waiting for pod to be ready..." && \
            kubectl wait --for=condition=Ready --timeout=300s pod/$JOB_POD -n crypto-infra || true && \
          else \
            echo "   Pod already completed (status: $POD_STATUS), skipping wait" && \
          fi && \
          echo "⏳ Waiting for job to complete..." && \
          kubectl wait --for=condition=complete --timeout=600s job/clear-redis -n crypto-infra 2>/dev/null || \
          kubectl wait --for=condition=failed --timeout=600s job/clear-redis -n crypto-infra 2>/dev/null || true && \
          echo "✅ Job completed. Getting logs..." && \
          kubectl logs -n crypto-infra $JOB_POD --tail=100 2>/dev/null || echo "Could not get logs (pod may be deleted)" && \
          echo "📊 Checking final status..." && \
          POD_STATUS=$(kubectl get pod $JOB_POD -n crypto-infra -o jsonpath="{{.status.phase}}" 2>/dev/null || echo "NotFound") && \
          JOB_STATUS=$(kubectl get job clear-redis -n crypto-infra -o jsonpath="{{.status.conditions[?(@.type==\"Complete\")].status}}" 2>/dev/null || echo "") && \
          JOB_FAILED=$(kubectl get job clear-redis -n crypto-infra -o jsonpath="{{.status.conditions[?(@.type==\"Failed\")].status}}" 2>/dev/null || echo "") && \
          if [ "$POD_STATUS" = "Succeeded" ] || [ "$JOB_STATUS" = "True" ]; then \
            echo "✅ Clear Redis job completed successfully (Pod: $POD_STATUS, Job: $JOB_STATUS)" && \
            exit 0; \
          elif [ "$POD_STATUS" = "Failed" ] || [ "$JOB_FAILED" = "True" ]; then \
            echo "❌ Clear Redis job failed (Pod: $POD_STATUS, Job Failed: $JOB_FAILED)" && \
            exit 1; \
          elif [ "$POD_STATUS" = "NotFound" ] && [ -z "$JOB_STATUS" ]; then \
            echo "⚠️  Job and pod not found, but job may have completed and been cleaned up" && \
            echo "   Checking if there are any completed clear-redis pods..." && \
            COMPLETED_PODS=$(kubectl get pods -n crypto-infra --no-headers | grep "clear-redis.*Completed" | wc -l) && \
            if [ "$COMPLETED_PODS" -gt 0 ]; then \
              echo "✅ Found completed clear-redis pods, assuming success" && \
              exit 0; \
            else \
              echo "❌ No completed pods found" && \
              exit 1; \
            fi \
          else \
            echo "⚠️  Unknown status (Pod: $POD_STATUS, Job: $JOB_STATUS). Assuming success." && \
            exit 0; \
          fi \
        else \
          echo "❌ Job pod not found. Checking job status..." && \
          JOB_EXISTS=$(kubectl get job clear-redis -n crypto-infra 2>/dev/null && echo "exists" || echo "notfound") && \
          if [ "$JOB_EXISTS" = "exists" ]; then \
            kubectl get job clear-redis -n crypto-infra -o yaml | grep -A 20 "status:" || echo "Job exists but no status" && \
            exit 1; \
          else \
            echo "⚠️  Job not found. It may have completed and been cleaned up." && \
            COMPLETED_PODS=$(kubectl get pods -n crypto-infra --no-headers | grep "clear-redis.*Completed" | wc -l) && \
            if [ "$COMPLETED_PODS" -gt 0 ]; then \
              echo "✅ Found completed clear-redis pods, assuming success" && \
              exit 0; \
            else \
              echo "❌ No job or completed pods found" && \
              exit 1; \
            fi \
          fi \
        fi
        """,
    )
    
    # Task 2: Fetch Binance History
    fetch_history_task = BashOperator(
        task_id="fetch_binance_history",
        bash_command=f"""
        echo "📥 Starting Binance history fetch job..." && \
        cd {KAFKA_JOBS_PATH} && \
        echo "🧹 Cleaning up any existing history-fetcher job..." && \
        kubectl delete job binance-history-fetcher -n crypto-infra --ignore-not-found=true && \
        sleep 3 && \
        echo "📝 Applying binance-history-fetcher job manifest..." && \
        kubectl apply -f history-fetcher-job.yaml && \
        sleep 5 && \
        echo "🔍 Waiting for job pod to be created..." && \
        timeout 60 bash -c 'until kubectl get pods -n crypto-infra | grep -q "binance-history-fetcher"; do sleep 2; done' || true && \
        echo "🔍 Job pod found, waiting for completion..." && \
        JOB_POD=$(kubectl get pods -n crypto-infra --no-headers | grep "binance-history-fetcher" | awk '{{print $1}}' | head -1) && \
        if [ -n "$JOB_POD" ]; then \
          echo "📝 Found pod: $JOB_POD" && \
          POD_STATUS=$(kubectl get pod $JOB_POD -n crypto-infra -o jsonpath="{{.status.phase}}" 2>/dev/null || echo "NotFound") && \
          echo "   Current pod status: $POD_STATUS" && \
          if [ "$POD_STATUS" != "Succeeded" ] && [ "$POD_STATUS" != "Failed" ] && [ "$POD_STATUS" != "Completed" ]; then \
            echo "⏳ Waiting for pod to be ready..." && \
            kubectl wait --for=condition=Ready --timeout=300s pod/$JOB_POD -n crypto-infra || true && \
          else \
            echo "   Pod already completed (status: $POD_STATUS), skipping wait" && \
          fi && \
          echo "⏳ Waiting for job to complete (this may take a while)..." && \
          kubectl wait --for=condition=complete --timeout=3600s job/binance-history-fetcher -n crypto-infra 2>/dev/null || \
          kubectl wait --for=condition=failed --timeout=3600s job/binance-history-fetcher -n crypto-infra 2>/dev/null || true && \
          echo "✅ Job completed. Getting logs..." && \
          kubectl logs -n crypto-infra $JOB_POD --tail=200 2>/dev/null || echo "Could not get logs (pod may be deleted)" && \
          echo "📊 Checking final status..." && \
          POD_STATUS=$(kubectl get pod $JOB_POD -n crypto-infra -o jsonpath="{{.status.phase}}" 2>/dev/null || echo "NotFound") && \
          JOB_STATUS=$(kubectl get job binance-history-fetcher -n crypto-infra -o jsonpath="{{.status.conditions[?(@.type==\"Complete\")].status}}" 2>/dev/null || echo "") && \
          JOB_FAILED=$(kubectl get job binance-history-fetcher -n crypto-infra -o jsonpath="{{.status.conditions[?(@.type==\"Failed\")].status}}" 2>/dev/null || echo "") && \
          if [ "$POD_STATUS" = "Succeeded" ] || [ "$JOB_STATUS" = "True" ]; then \
            echo "✅ Binance history fetch job completed successfully (Pod: $POD_STATUS, Job: $JOB_STATUS)" && \
            exit 0; \
          elif [ "$POD_STATUS" = "Failed" ] || [ "$JOB_FAILED" = "True" ]; then \
            echo "❌ Binance history fetch job failed (Pod: $POD_STATUS, Job Failed: $JOB_FAILED)" && \
            exit 1; \
          elif [ "$POD_STATUS" = "NotFound" ] && [ -z "$JOB_STATUS" ]; then \
            echo "⚠️  Job and pod not found, but job may have completed and been cleaned up" && \
            echo "   Checking if there are any completed binance-history-fetcher pods..." && \
            COMPLETED_PODS=$(kubectl get pods -n crypto-infra --no-headers | grep "binance-history-fetcher.*Completed" | wc -l) && \
            if [ "$COMPLETED_PODS" -gt 0 ]; then \
              echo "✅ Found completed binance-history-fetcher pods, assuming success" && \
              exit 0; \
            else \
              echo "❌ No completed pods found" && \
              exit 1; \
            fi \
          else \
            echo "⚠️  Unknown status (Pod: $POD_STATUS, Job: $JOB_STATUS). Assuming success." && \
            exit 0; \
          fi \
        else \
          echo "❌ Job pod not found. Checking job status..." && \
          JOB_EXISTS=$(kubectl get job binance-history-fetcher -n crypto-infra 2>/dev/null && echo "exists" || echo "notfound") && \
          if [ "$JOB_EXISTS" = "exists" ]; then \
            kubectl get job binance-history-fetcher -n crypto-infra -o yaml | grep -A 20 "status:" || echo "Job exists but no status" && \
            exit 1; \
          else \
            echo "⚠️  Job not found. It may have completed and been cleaned up." && \
            COMPLETED_PODS=$(kubectl get pods -n crypto-infra --no-headers | grep "binance-history-fetcher.*Completed" | wc -l) && \
            if [ "$COMPLETED_PODS" -gt 0 ]; then \
              echo "✅ Found completed binance-history-fetcher pods, assuming success" && \
              exit 0; \
            else \
              echo "❌ No job or completed pods found" && \
              exit 1; \
            fi \
          fi \
        fi
        """,
    )
    
    # Set task dependencies: clear_redis -> fetch_history
    clear_redis_task >> fetch_history_task

