# Schema Changes in Spark Operator 0.6.0

## 📋 Tóm tắt

Spark Kubernetes Operator 0.6.0 đã thay đổi hoàn toàn API schema cho `SparkApplication`. Schema mới đơn giản hơn và tập trung vào việc cấu hình thông qua `sparkConf` thay vì các fields riêng biệt.

## ⚠️ Breaking Changes

### Old Schema (< 0.6.0)

```yaml
apiVersion: spark.apache.org/v1
kind: SparkApplication
spec:
  type: Python
  mode: cluster
  image: "apache/spark:3.5.0"
  imagePullPolicy: IfNotPresent
  mainApplicationFile: "local:///app.py"
  sparkVersion: "3.5.0"
  
  restartPolicy:
    type: OnFailure
    onFailureRetries: 3
  
  driver:
    cores: 1
    memory: "1g"
    serviceAccount: spark
  
  executor:
    cores: 1
    instances: 2
    memory: "1g"
```

### New Schema (>= 0.6.0)

```yaml
apiVersion: spark.apache.org/v1
kind: SparkApplication
spec:
  # For Scala/Java apps
  mainClass: "org.apache.spark.examples.SparkPi"
  jars: "local:///opt/spark/examples/jars/spark-examples.jar"
  
  # For Python apps
  mainApplicationFile: "local:///opt/spark/work-dir/app.py"
  
  sparkConf:
    # Image and K8s configs
    spark.kubernetes.container.image: "apache/spark:3.5.0"
    spark.kubernetes.authenticate.driver.serviceAccountName: "spark"
    
    # Driver configuration
    spark.driver.cores: "1"
    spark.driver.memory: "1g"
    
    # Executor configuration
    spark.executor.cores: "1"
    spark.executor.memory: "1g"
    
    # Dynamic allocation
    spark.dynamicAllocation.enabled: "true"
    spark.dynamicAllocation.minExecutors: "1"
    spark.dynamicAllocation.maxExecutors: "3"
  
  applicationTolerations:
    resourceRetainPolicy: OnFailure
    restartConfig:
      restartPolicy: OnFailure
      maxRestartAttempts: 3
  
  runtimeVersions:
    scalaVersion: "2.12"
    sparkVersion: "3.5.0"
```

## 🔄 Field Mapping

| Old Field | New Field | Notes |
|-----------|-----------|-------|
| `spec.type` | Removed | Inferred from `mainClass` vs `mainApplicationFile` |
| `spec.mode` | Removed | Always cluster mode in K8s |
| `spec.image` | `sparkConf["spark.kubernetes.container.image"]` | Now in sparkConf |
| `spec.imagePullPolicy` | `sparkConf["spark.kubernetes.container.image.pullPolicy"]` | Now in sparkConf |
| `spec.sparkVersion` | `runtimeVersions.sparkVersion` | New section |
| `spec.driver.*` | `sparkConf["spark.driver.*"]` | All driver configs in sparkConf |
| `spec.executor.*` | `sparkConf["spark.executor.*"]` | All executor configs in sparkConf |
| `spec.restartPolicy` | `applicationTolerations.restartConfig` | New structure |

## 📝 Common Configurations

### Python Application

```yaml
spec:
  mainApplicationFile: "local:///opt/spark/work-dir/app.py"
  
  sparkConf:
    spark.kubernetes.container.image: "apache/spark-py:3.5.0"
    spark.kubernetes.authenticate.driver.serviceAccountName: "spark"
    spark.driver.cores: "1"
    spark.driver.memory: "1g"
    spark.executor.cores: "1"
    spark.executor.memory: "1g"
  
  runtimeVersions:
    scalaVersion: "2.12"
    sparkVersion: "3.5.0"
```

### Scala Application

```yaml
spec:
  mainClass: "com.example.MyApp"
  jars: "local:///opt/spark/jars/myapp.jar"
  
  sparkConf:
    spark.kubernetes.container.image: "apache/spark:3.5.0"
    spark.kubernetes.authenticate.driver.serviceAccountName: "spark"
    spark.driver.cores: "1"
    spark.driver.memory: "1g"
    spark.executor.cores: "1"
    spark.executor.memory: "1g"
  
  runtimeVersions:
    scalaVersion: "2.12"
    sparkVersion: "3.5.0"
```

### With Dependencies

```yaml
spec:
  mainApplicationFile: "local:///opt/spark/work-dir/app.py"
  
  sparkConf:
    spark.jars.packages: "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0"
    # ... other configs
```

### Environment Variables

```yaml
sparkConf:
  # For driver
  spark.kubernetes.driverEnv.MY_VAR: "value"
  spark.kubernetes.driverEnv.KAFKA_SERVERS: "kafka:9092"
  
  # For executor
  spark.executorEnv.MY_VAR: "value"
  spark.executorEnv.KAFKA_SERVERS: "kafka:9092"
```

### Pod Labels and Annotations

```yaml
sparkConf:
  # Driver labels
  spark.kubernetes.driver.label.app: "myapp"
  spark.kubernetes.driver.label.env: "prod"
  
  # Executor labels
  spark.kubernetes.executor.label.app: "myapp"
  spark.kubernetes.executor.label.env: "prod"
  
  # Driver annotations (for Prometheus)
  spark.kubernetes.driver.annotation.prometheus.io/scrape: "true"
  spark.kubernetes.driver.annotation.prometheus.io/port: "4040"
```

### Dynamic Allocation

```yaml
sparkConf:
  spark.dynamicAllocation.enabled: "true"
  spark.dynamicAllocation.shuffleTracking.enabled: "true"
  spark.dynamicAllocation.minExecutors: "2"
  spark.dynamicAllocation.maxExecutors: "10"
  spark.dynamicAllocation.initialExecutors: "3"

applicationTolerations:
  instanceConfig:
    initExecutors: 3
    minExecutors: 2
    maxExecutors: 10
```

### Restart Policy

```yaml
applicationTolerations:
  resourceRetainPolicy: OnFailure  # Always, Never, OnFailure
  restartConfig:
    restartPolicy: OnFailure       # Always, Never, OnFailure, OnInfrastructureFailure
    maxRestartAttempts: 5
    restartBackoffMillis: 30000
```

## 🔍 Key Differences

### 1. Everything in sparkConf
- Driver/executor specs now use standard Spark configs
- No separate YAML fields for driver/executor
- More aligned with spark-submit syntax

### 2. Runtime Versions Section
```yaml
runtimeVersions:
  scalaVersion: "2.12"  # or "2.13"
  sparkVersion: "3.5.0"
```

### 3. Application Tolerations
Replaces multiple old fields:
- `restartPolicy` → `applicationTolerations.restartConfig`
- `timeToLiveSeconds` → `applicationTolerations.ttlAfterStopMillis`
- Resource retention → `applicationTolerations.resourceRetainPolicy`

### 4. No More Monitoring Section
Old `monitoring` section removed. Use sparkConf instead:
```yaml
sparkConf:
  spark.metrics.conf.*.sink.prometheusServlet.class: "org.apache.spark.metrics.sink.PrometheusServlet"
  spark.metrics.conf.*.sink.prometheusServlet.path: "/metrics"
```

### 5. Volumes
Now configured via sparkConf:
```yaml
sparkConf:
  spark.kubernetes.driver.volumes.persistentVolumeClaim.data.mount.path: "/data"
  spark.kubernetes.driver.volumes.persistentVolumeClaim.data.options.claimName: "my-pvc"
```

## ✅ Migration Checklist

- [ ] Update `apiVersion` to `spark.apache.org/v1`
- [ ] Remove `spec.type` and `spec.mode` fields
- [ ] Move `spec.image` to `sparkConf["spark.kubernetes.container.image"]`
- [ ] Move all `spec.driver.*` to `sparkConf["spark.driver.*"]`
- [ ] Move all `spec.executor.*` to `sparkConf["spark.executor.*"]`
- [ ] Move `spec.sparkVersion` to `runtimeVersions.sparkVersion`
- [ ] Add `runtimeVersions.scalaVersion`
- [ ] Update `spec.restartPolicy` to `applicationTolerations.restartConfig`
- [ ] Update environment variables to use `spark.kubernetes.driverEnv.*`
- [ ] Update labels to use `spark.kubernetes.driver.label.*`
- [ ] Update annotations to use `spark.kubernetes.driver.annotation.*`
- [ ] Remove `monitoring` section if present
- [ ] Update volume mounts to use sparkConf syntax

## 📚 References

- [Official Examples](https://apache.github.io/spark-kubernetes-operator/)
- [Spark Configuration](https://spark.apache.org/docs/latest/configuration.html)
- [Spark on Kubernetes](https://spark.apache.org/docs/latest/running-on-kubernetes.html)

## 💡 Tips

1. **Use official examples as reference**: Check https://apache.github.io/spark-kubernetes-operator/ for latest examples
2. **Test with simple apps first**: Start with spark-pi before complex applications
3. **Check CRD version**: `kubectl get crd sparkapplications.spark.apache.org -o yaml`
4. **Validate before applying**: Use `kubectl apply --dry-run=client`
5. **Monitor operator logs**: `kubectl logs -n crypto-infra -l app.kubernetes.io/name=spark-kubernetes-operator`

## 🐛 Common Issues

### Issue: "unknown field spec.driver"
**Solution**: You're using old schema. Update to new schema using this guide.

### Issue: Application stuck in "Submitted"
**Solution**: Check operator logs and ensure service account has proper permissions.

### Issue: Driver pod not starting
**Solution**: 
- Check image pull policy and availability
- Verify service account exists
- Check resource quotas

### Issue: "configmap not found"
**Solution**: This is temporary during pod creation. If it persists, check operator logs.

