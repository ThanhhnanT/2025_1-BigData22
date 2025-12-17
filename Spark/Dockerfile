FROM apache/spark:3.5.0

USER root

# Install Python dependencies
RUN pip install --no-cache-dir \
    redis>=5.0.0 \
    pymongo>=4.0.0 \
    python-dotenv>=1.0.0

# Copy batch jobs
COPY batch/ /opt/spark/jobs/

# Set permissions
RUN chmod -R 755 /opt/spark/jobs/

# Switch back to spark user
USER 185

WORKDIR /opt/spark/work-dir


