FROM apache/airflow:3.0.2

# Switch to root to install packages if needed
USER root

# RUN apt-get update && \
#     apt-get install -y --no-install-recommends \
#     <package-name> \
#     && rm -rf /var/lib/apt/lists/*

USER airflow

COPY --chown=airflow:root requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt && \
    rm /tmp/requirements.txt

COPY --chown=airflow:root dags/ /opt/airflow/dags/

USER root
RUN chmod -R 755 /opt/airflow/dags
USER airflow

RUN ls -la /opt/airflow/dags/

