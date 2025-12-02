# Spark on Kubernetes Setup

This directory contains configuration for running Apache Spark on Kubernetes using the official Spark Kubernetes Operator.

## 📁 Directory Structure

```
Spark/
├── config/                                    # Operator configurations
│   ├── operator-values-minikube.yaml         # Dev/Minikube settings
│   └── operator-values-production.yaml       # Production settings
├── apps/                                      # Spark applications
│   ├── streaming/
│   │   ├── crypto-streaming-minikube.yaml    # Dev streaming app
│   │   └── crypto-streaming-production.yaml  # Production streaming app
│   └── spark-pi-test.yaml                    # Test application
├── deploy-spark-operator.sh                   # Operator deployment script
├── deploy-spark-app.sh                        # Application deployment script
├── spark_streaming_10m.py                     # Python streaming code
└── README.md                                  # This file
```

## 🚀 Quick Start

### 1. Deploy Spark Operator

For Minikube/Development:
```bash
cd Spark
./deploy-spark-operator.sh minikube
```

For Production:
```bash
./deploy-spark-operator.sh production
```

### 2. Verify Installation

```bash
# Check operator pods
kubectl get pods -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator

# Check CRDs
kubectl get crd | grep spark

# View operator logs
kubectl logs -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator
```

### 3. Deploy Test Application

```bash
# Deploy Spark Pi test
./deploy-spark-app.sh test minikube

# Check status
kubectl get sparkapplication -n crypto-infra

# View logs
kubectl logs -n crypto-infra spark-pi-test-driver
```

### 4. Deploy Streaming Application

```bash
# For minikube
./deploy-spark-app.sh streaming minikube

# For production
./deploy-spark-app.sh streaming production

# Monitor status
kubectl get sparkapplication crypto-streaming-10m -n crypto-infra -w
```

## 📊 Monitoring

### Access Spark UI

```bash
# Port-forward to Spark UI
APP_NAME=crypto-streaming-10m
kubectl port-forward -n crypto-infra ${APP_NAME}-driver 4040:4040

# Open in browser: http://localhost:4040
```

### Prometheus Metrics

Operator exposes metrics on port 19090:
```bash
# Port-forward to metrics endpoint
kubectl port-forward -n crypto-infra svc/crypto-spark-operator-metrics 19090:19090

# View metrics: http://localhost:19090/metrics
```

Production applications expose metrics on port 8090 (configured in production manifest).

## 🔧 Configuration Details

### Minikube Configuration
- **Replicas**: 1 (single operator instance)
- **Resources**: Low (512Mi memory, 250m CPU)
- **Reconciliation**: Fast (10 seconds)
- **Dynamic Allocation**: Disabled
- **Persistence**: Disabled

### Production Configuration
- **Replicas**: 3 (HA with leader election)
- **Resources**: High (4Gi memory, 2 CPU)
- **Reconciliation**: Optimized (30 seconds, batch size 10)
- **Dynamic Allocation**: Enabled (2-10 executors)
- **Persistence**: Enabled with PVCs
- **Anti-affinity**: Enabled for pod distribution
- **Monitoring**: Full metrics and JMX export
- **Security**: Hardened security contexts

## 📝 Application Specifications

### Test Application (Spark Pi)
Simple Scala application to verify operator functionality.
- **Type**: Scala
- **Mode**: Cluster
- **Resources**: Minimal (1 driver, 2 executors)
- **Duration**: Short-lived (~1 minute)

### Streaming Application (Crypto Aggregator)
PySpark streaming application that:
- Reads from Kafka topic `crypto_kline_1m`
- Aggregates 1-minute klines to 10-minute intervals
- Outputs results (configurable sink)

**Minikube Version:**
- 2 executors, static allocation
- No persistence
- Basic monitoring

**Production Version:**
- Dynamic allocation (2-10 executors)
- Persistent checkpoints and event logs
- Full monitoring and metrics
- Fault tolerance with retries
- Resource limits and requests
- Pod anti-affinity

## 🔄 Upgrading

### Upgrade Operator

```bash
# Minikube
./deploy-spark-operator.sh minikube

# Production
./deploy-spark-operator.sh production
```

The script automatically detects existing releases and performs `helm upgrade`.

### Upgrade Application

```bash
# Update manifest file, then:
kubectl apply -f apps/streaming/crypto-streaming-minikube.yaml

# Or use the script:
./deploy-spark-app.sh streaming minikube
```

## 🐛 Troubleshooting

### Operator Issues

```bash
# Check operator status
kubectl get deployment -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator

# View logs
kubectl logs -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator --tail=100

# Describe deployment
kubectl describe deployment -n crypto-infra crypto-spark-operator
```

### Application Issues

```bash
# Check application status
kubectl get sparkapplication -n crypto-infra

# Describe application
kubectl describe sparkapplication crypto-streaming-10m -n crypto-infra

# View driver logs
kubectl logs -n crypto-infra crypto-streaming-10m-driver

# View executor logs
kubectl logs -n crypto-infra -l spark-role=executor

# Check events
kubectl get events -n crypto-infra --sort-by='.lastTimestamp'
```

### Common Issues

1. **Operator not ready**
   - Check pod status: `kubectl get pods -n crypto-infra`
   - Review logs for errors
   - Verify RBAC permissions

2. **Application fails to submit**
   - Ensure operator is running and ready
   - Check service account permissions
   - Verify image pull policy and availability

3. **Executors not starting**
   - Check resource quotas
   - Verify node resources available
   - Review executor pod events

4. **Kafka connection issues**
   - Verify Kafka service name and port
   - Check network policies
   - Test connectivity from Spark pods

## 🔗 Useful Commands

```bash
# List all Spark applications
kubectl get sparkapplication -n crypto-infra

# Watch application status
kubectl get sparkapplication -n crypto-infra -w

# Delete application
kubectl delete sparkapplication <app-name> -n crypto-infra

# List all Spark pods
kubectl get pods -n crypto-infra -l spark-role

# Port-forward to Spark UI
kubectl port-forward -n crypto-infra <driver-pod> 4040:4040

# View application YAML
kubectl get sparkapplication <app-name> -n crypto-infra -o yaml

# Delete completed applications
kubectl delete sparkapplication -n crypto-infra --field-selector status.applicationState.state=COMPLETED
```

## 📚 References

- [Spark Kubernetes Operator Documentation](https://apache.github.io/spark-kubernetes-operator/)
- [Spark on Kubernetes Guide](https://spark.apache.org/docs/latest/running-on-kubernetes.html)
- [Official Helm Chart](https://artifacthub.io/packages/helm/spark-kubernetes-operator/spark-kubernetes-operator)

## 🔐 Production Checklist

Before deploying to production:

- [ ] Use official Helm repository (not local chart)
- [ ] Pin specific chart version
- [ ] Enable high availability (3+ replicas)
- [ ] Configure resource limits and requests
- [ ] Enable persistent storage (HDFS/S3)
- [ ] Set up monitoring and alerting
- [ ] Configure security contexts
- [ ] Enable RBAC with proper permissions
- [ ] Test disaster recovery procedures
- [ ] Document runbooks for operations team

## 💡 Best Practices

1. **Resource Management**
   - Always set resource limits and requests
   - Use dynamic allocation in production
   - Monitor resource utilization

2. **Monitoring**
   - Enable metrics export to Prometheus
   - Set up alerting for failures
   - Use Spark UI for debugging

3. **Fault Tolerance**
   - Configure restart policies
   - Enable checkpointing for streaming
   - Use speculation for long-running tasks

4. **Security**
   - Use service accounts with minimal permissions
   - Enable network policies
   - Scan images for vulnerabilities

5. **Operations**
   - Use infrastructure as code (Helm/Terraform)
   - Version all configurations
   - Automate deployments via CI/CD
   - Keep comprehensive logs
