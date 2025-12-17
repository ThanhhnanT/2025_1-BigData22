from datetime import datetime, timedelta

from airflow import DAG
from airflow.providers.cncf.kubernetes.operators.spark_kubernetes import (
    SparkKubernetesOperator,
)

DEFAULT_ARGS = {
    "owner": "crypto_team",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=1),
}

# Tất cả SparkApplication đều đang chạy trong namespace crypto-infra
NAMESPACE = "crypto-infra"

SPARK_APPS_BASE_PATH = "spark_apps"


with DAG(
    dag_id="test_spark_k8s_operator",
    default_args=DEFAULT_ARGS,
    description="Test SparkApplication via SparkKubernetesOperator",
    schedule=None,  # chỉ chạy thủ công để debug
    catchup=False,
    tags=["test", "spark", "k8s", "operator"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as test_dag:
    test_spark_simple = SparkKubernetesOperator(
        task_id="test_spark_simple",
        namespace=NAMESPACE,
        application_file=f"{SPARK_APPS_BASE_PATH}/test-spark-simple.yaml",
        do_xcom_push=True,
    )


with DAG(
    dag_id="ohlc_5m_spark_k8s_operator",
    default_args=DEFAULT_ARGS,
    description="Aggregate OHLC 5m using SparkApplication on Kubernetes",
    schedule="*/5 * * * *",
    catchup=False,
    tags=["crypto", "ohlc", "spark", "5m", "k8s"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_5m:
    ohlc_5m = SparkKubernetesOperator(
        task_id="ohlc_5m_aggregator",
        namespace=NAMESPACE,
        application_file=f"{SPARK_APPS_BASE_PATH}/ohlc-5m-aggregator.yaml",
        do_xcom_push=True,
    )


with DAG(
    dag_id="ohlc_1h_spark_k8s_operator",
    default_args=DEFAULT_ARGS,
    description="Aggregate OHLC 1h using SparkApplication on Kubernetes",
    schedule="0 * * * *",  # mỗi giờ
    catchup=False,
    tags=["crypto", "ohlc", "spark", "1h", "k8s"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_1h:
    ohlc_1h = SparkKubernetesOperator(
        task_id="ohlc_1h_aggregator",
        namespace=NAMESPACE,
        application_file=f"{SPARK_APPS_BASE_PATH}/ohlc-1h-aggregator.yaml",
        do_xcom_push=True,
    )


with DAG(
    dag_id="ohlc_5h_spark_k8s_operator",
    default_args=DEFAULT_ARGS,
    description="Aggregate OHLC 5h using SparkApplication on Kubernetes",
    schedule="0 */5 * * *",  # 5 giờ một lần
    catchup=False,
    tags=["crypto", "ohlc", "spark", "5h", "k8s"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_5h:
    ohlc_5h = SparkKubernetesOperator(
        task_id="ohlc_5h_aggregator",
        namespace=NAMESPACE,
        application_file=f"{SPARK_APPS_BASE_PATH}/ohlc-5h-aggregator.yaml",
        do_xcom_push=True,
    )


with DAG(
    dag_id="ohlc_1d_spark_k8s_operator",
    default_args=DEFAULT_ARGS,
    description="Aggregate OHLC 1d using SparkApplication on Kubernetes",
    schedule="0 0 * * *",  # hằng ngày lúc 00:00 UTC
    catchup=False,
    tags=["crypto", "ohlc", "spark", "1d", "k8s"],
    start_date=datetime(2024, 1, 1),
    max_active_runs=1,
) as dag_1d:
    ohlc_1d = SparkKubernetesOperator(
        task_id="ohlc_1d_aggregator",
        namespace=NAMESPACE,
        application_file=f"{SPARK_APPS_BASE_PATH}/ohlc-1d-aggregator.yaml",
        do_xcom_push=True,
    )


