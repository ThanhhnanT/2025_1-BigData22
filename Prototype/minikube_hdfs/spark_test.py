from pyspark.sql import SparkSession

# 1. Cấu hình NameNode URI
# Service Name trong Minikube: hadoop-hadoop-hdfs-nn
# Cổng HDFS mặc định: 9000
HDFS_URI = "hdfs://hadoop-hadoop-hdfs-nn:9000"
OUTPUT_DIR = f"{HDFS_URI}/spark_output/test_write"
print(f"Sử dụng HDFS URI: {HDFS_URI}")

# 2. Tạo Spark Session
# Đảm bảo bạn chạy lệnh này với Java 17 đã được set JAVA_HOME
try:
    spark = SparkSession.builder.appName("HDFSKubeTestWrite").getOrCreate()
    print("Spark Session đã được tạo thành công.")
    
    # 3. Tạo một DataFrame đơn giản
    data = [
        ("Apple", 100), 
        ("Banana", 200), 
        ("Cherry", 300)
    ]
    columns = ["Fruit", "Quantity"]
    df = spark.createDataFrame(data, columns)
    
    # 4. Ghi DataFrame vào HDFS (dưới dạng Parquet)
    print(f"\n*** Bắt đầu ghi dữ liệu vào HDFS tại {OUTPUT_DIR} ***")
    
    # Dùng .mode("overwrite") để ghi đè nếu file tồn tại
    df.write.mode("overwrite").parquet(OUTPUT_DIR)
    
    print("*** Ghi dữ liệu thành công! ***")

except Exception as e:
    print(f"\nLỖI XẢY RA KHI KẾT NỐI HDFS/SPARK: {e}")

finally:
    if 'spark' in locals():
        spark.stop()
        print("Spark Session đã dừng.")