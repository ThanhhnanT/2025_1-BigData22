kubectl create namespace kafka

# cai helm
helm repo add strimzi https://strimzi.io/charts/
helm repo update
helm install strimzi-kafka strimzi/strimzi-kafka-operator -n kafka
kubectl apply -f kafka-cluster.yaml -n kafka
