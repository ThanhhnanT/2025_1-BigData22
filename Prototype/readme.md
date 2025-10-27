# **Cài đặt Cluster HDFS Giả Lập Bằng Minikube**

Tài liệu này hướng dẫn cách tạo một cluster Hadoop HDFS nhỏ (1 NameNode, 2 DataNode) chạy trên Kubernetes (sử dụng Minikube) để phục vụ cho việc phát triển và thử nghiệm. Chúng ta sẽ sử dụng Helm và chart pfisterer-hadoop/hadoop.

## **Các Bước Cài Đặt (Chạy trong WSL) 🚀**

**Quan trọng:** Tất cả các lệnh sau đều phải được thực hiện từ terminal WSL 2 (Ubuntu).

### **1\. Khởi động Minikube**

Khởi động cluster Minikube với 3 node (1 control plane, 2 worker) và cấp đủ tài nguyên:

minikube start \--driver=docker \--nodes=3 \--memory=4096 \--cpus=2

Kiểm tra trạng thái cluster:

minikube status  
kubectl get nodes

### **2\. Thêm Kho Helm Chart**

Thêm kho chứa chart pfisterer-hadoop:

helm repo add pfisterer-hadoop \[https://pfisterer.github.io/apache-hadoop-helm/\](https://pfisterer.github.io/apache-hadoop-helm/)  
helm repo update

### **3\. Cài đặt HDFS (với 1 DataNode)**

Cài đặt chart HDFS. Lần đầu nó sẽ chỉ có 1 DataNode:

\# Đặt tên release là 'hadoop'  
helm install hadoop pfisterer-hadoop/hadoop

### **4\. Nâng cấp lên 2 DataNode**

Sử dụng helm upgrade để yêu cầu 2 DataNode:

helm upgrade hadoop pfisterer-hadoop/hadoop \--set hdfs.dataNode.replicas=2

### **5\. Kiểm tra Trạng thái Pods**

Theo dõi các pod HDFS khởi động. Chờ đến khi tất cả đều 1/1 Running:

kubectl get pods \-w

Bạn sẽ thấy các pod như:

* hadoop-hadoop-hdfs-nn-0 (NameNode)  
* hadoop-hadoop-hdfs-dn-0 (DataNode 1\)  
* hadoop-hadoop-hdfs-dn-1 (DataNode 2\)  
* hadoop-hadoop-yarn-rm-0 (ResourceManager \- đi kèm chart)  
* hadoop-hadoop-yarn-nm-0 (NodeManager \- đi kèm chart)

## **Cách Sử dụng/Test HDFS 🧪**

### **1\. Truy cập Giao diện Web (UI)**

Mở một **terminal WSL mới** và chạy lệnh port-forward:

kubectl port-forward hadoop-hadoop-hdfs-nn-0 9870:9870

Mở trình duyệt trên Windows và truy cập http://localhost:9870. Vào tab "Datanodes" để xem 2 DataNode đang "Live".

### **2\. Sử dụng Dòng lệnh (CLI)**

Vào bên trong pod NameNode:

kubectl exec \-it hadoop-hadoop-hdfs-nn-0 \-- bash

Bên trong pod, bạn có thể chạy các lệnh HDFS:

hdfs dfs \-ls /  
echo "Hello from Minikube HDFS\!" \> test.txt  
hdfs dfs \-put test.txt /  
hdfs dfs \-cat /test.txt  
exit

## **Quản lý Cluster Minikube ⏯️⏹️**

* **Tạm dừng cluster (giữ lại HDFS):**  
  minikube stop

* **Khởi động lại cluster (HDFS vẫn còn):**  
  minikube start

Chúc các bạn thành công\! 🎉