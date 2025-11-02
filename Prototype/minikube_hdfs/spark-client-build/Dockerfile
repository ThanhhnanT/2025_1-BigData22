FROM openjdk:17-jdk-slim

RUN apt-get update && \
    apt-get install -y python3.9 python3-pip && \
    pip install pyspark==4.0.1 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV SPARK_HOME="/usr/local/lib/python3.9/dist-packages/pyspark"
ENV PATH="$PATH:$SPARK_HOME/bin"

WORKDIR /app
CMD ["sleep", "infinity"]