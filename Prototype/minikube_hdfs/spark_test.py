from pyspark.sql import SparkSession

HDFS_URI = "hdfs://hadoop-hadoop-hdfs-nn:9000"
OUTPUT_DIR = f"{HDFS_URI}/spark_output/test_write"
print(f"Sử dụng HDFS URI: {HDFS_URI}")

try:
    spark = SparkSession.builder.appName("HDFSKubeTestWrite").getOrCreate()
    print("Spark Session đã được tạo thành công.")
    
    data = [
        ("Apple", 100), 
        ("Banana", 200), 
        ("Cherry", 300)
    ]
    columns = ["Fruit", "Quantity"]
    df = spark.createDataFrame(data, columns)
    
    print(f"\n*** Bắt đầu ghi dữ liệu vào HDFS tại {OUTPUT_DIR} ***")
    
    df.write.mode("overwrite").parquet(OUTPUT_DIR)
    
    print("*** Ghi dữ liệu thành công! ***")

except Exception as e:
    print(f"\nLỖI XẢY RA KHI KẾT NỐI HDFS/SPARK: {e}")

finally:
    if 'spark' in locals():
        spark.stop()
        print("Spark Session đã dừng.")