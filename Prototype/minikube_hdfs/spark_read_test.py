from pyspark.sql import SparkSession

# URI Service NameName
HDFS_URI_SERVICE = "hdfs://hadoop-hadoop-hdfs-nn:9000" 
# Sửa đường dẫn để trỏ đúng vào thư mục chứa file parquet
OUTPUT_DIR = f"{HDFS_URI_SERVICE}/spark_output/test_write" 

spark = SparkSession.builder \
    .appName("HDFSReadTest") \
    .config("spark.hadoop.fs.defaultFS", HDFS_URI_SERVICE) \
    .getOrCreate()

print("\n*** Đang kiểm tra ĐỌC dữ liệu từ HDFS ***")

try:
    # Dùng .read.parquet() vì file có đuôi .parquet
    df_read = spark.read.parquet(OUTPUT_DIR)
    
    print("Cấu trúc dữ liệu đọc được:")
    df_read.printSchema()
    
    print("\nDữ liệu mẫu:")
    df_read.show(10, truncate=False) 
    
    print(f"\n*** ĐỌC dữ liệu thành công từ: {OUTPUT_DIR} ***")

except Exception as e:
    print(f"LỖI ĐỌC HDFS: {e}")

finally:
    spark.stop()
