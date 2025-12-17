FROM apache/airflow:3.0.2

USER root
USER airflow

COPY --chown=airflow:root airflow/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

# Copy DAGs
COPY --chown=airflow:root airflow/dags/ /opt/airflow/dags/

# Copy SparkApplication YAMLs vào dưới dags để Jinja tìm được
COPY --chown=airflow:root Spark/apps/batch/ /opt/airflow/dags/spark_apps/

USER root
RUN chmod -R 755 /opt/airflow/dags
USER airflow

RUN ls -la /opt/airflow/dags/ && ls -la /opt/airflow/dags/spark_apps/ || true