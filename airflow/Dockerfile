FROM apache/airflow:3.0.2

# Cần quyền root để cài thêm kubectl
USER root

# Cài kubectl để các BashOperator trong DAG có thể gọi kubectl bên trong pod Airflow
RUN curl -LO "https://dl.k8s.io/release/$(curl -Ls https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" \
    && install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl \
    && rm kubectl

# Chuyển về user airflow để cài Python packages theo khuyến nghị của Airflow
USER airflow

# Cài thêm Python packages cho Airflow (chạy bằng user airflow)
COPY airflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Copy DAGs
COPY airflow/dags/ /opt/airflow/dags/

# Copy SparkApplication YAMLs vào dưới dags để Jinja tìm được
COPY Spark/apps/batch/ /opt/airflow/dags/spark_apps/

# Debug: liệt kê nội dung DAGs và spark_apps khi build
RUN ls -la /opt/airflow/dags/ && ls -la /opt/airflow/dags/spark_apps/ || true