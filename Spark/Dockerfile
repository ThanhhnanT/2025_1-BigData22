FROM apache/spark:3.3.3

USER root

# Install Python dependencies
RUN pip install --no-cache-dir \
    redis>=5.0.0 \
    pymongo>=4.0.0 \
    python-dotenv>=1.0.0 \
    numpy>=1.21.0 \
    pandas>=1.3.0 \
    scipy>=1.7.0

# Download Kafka connector JARs and all dependencies to avoid runtime download issues
# Using Spark 3.3.3 compatible versions
RUN mkdir -p /opt/spark/jars && \
    wget -q https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.3.3/spark-sql-kafka-0-10_2.12-3.3.3.jar \
    -O /opt/spark/jars/spark-sql-kafka-0-10_2.12-3.3.3.jar && \
    wget -q https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.3.1/kafka-clients-3.3.1.jar \
    -O /opt/spark/jars/kafka-clients-3.3.1.jar && \
    wget -q https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.3.3/spark-token-provider-kafka-0-10_2.12-3.3.3.jar \
    -O /opt/spark/jars/spark-token-provider-kafka-0-10_2.12-3.3.3.jar && \
    wget -q https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar \
    -O /opt/spark/jars/commons-pool2-2.11.1.jar && \
    chmod 644 /opt/spark/jars/*.jar

# Copy batch jobs
COPY batch/ /opt/spark/jobs/

# Copy ranking coins streaming jobs
COPY ranking_coins/ /opt/spark/jobs/ranking_coins/

# Set permissions
RUN chmod -R 755 /opt/spark/jobs/

# Switch back to spark user
USER 185

WORKDIR /opt/spark/work-dir


