#!/usr/bin/env python3
"""
Simple Spark Test Job
Tests Spark core functionality without external dependencies (Redis/MongoDB)
Can be run via Spark Kubernetes Operator for testing
"""

import sys
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum as spark_sum, avg, max as spark_max, min as spark_min

def main():
    try:
        # Initialize Spark Session
        # When running in K8s, Spark will automatically detect K8s mode
        spark = SparkSession.builder \
            .appName("Spark-Simple-Test") \
            .getOrCreate()
        
        print("=" * 60)
        print("🚀 Starting Spark Simple Test Job")
        print("=" * 60)
        
        # Test 1: Create DataFrame from sample data
        print("\n📊 Test 1: Creating sample DataFrame...")
        sample_data = [
            ("BTCUSDT", 50000.0, 100.5, 1609459200000),
            ("BTCUSDT", 50100.0, 150.2, 1609459260000),
            ("BTCUSDT", 50200.0, 200.3, 1609459320000),
            ("ETHUSDT", 3000.0, 500.1, 1609459200000),
            ("ETHUSDT", 3010.0, 600.5, 1609459260000),
            ("ETHUSDT", 3020.0, 700.8, 1609459320000),
            ("BNBUSDT", 400.0, 1000.0, 1609459200000),
            ("BNBUSDT", 405.0, 1200.0, 1609459260000),
            ("BNBUSDT", 410.0, 1500.0, 1609459320000),
        ]
        
        columns = ["symbol", "price", "volume", "timestamp"]
        df = spark.createDataFrame(sample_data, columns)
        
        print(f"✅ Created DataFrame with {df.count()} rows")
        print("\nSample data:")
        df.show(truncate=False)
        
        # Test 2: Filter operation
        print("\n📊 Test 2: Filtering data (BTCUSDT only)...")
        btc_df = df.filter(col("symbol") == "BTCUSDT")
        btc_count = btc_df.count()
        print(f"✅ Filtered to {btc_count} BTCUSDT rows")
        btc_df.show(truncate=False)
        
        # Test 3: GroupBy and Aggregation
        print("\n📊 Test 3: GroupBy and Aggregation...")
        aggregated_df = df.groupBy("symbol").agg(
            spark_sum("volume").alias("total_volume"),
            avg("price").alias("avg_price"),
            spark_max("price").alias("max_price"),
            spark_min("price").alias("min_price")
        )
        
        print("✅ Aggregated results:")
        aggregated_df.show(truncate=False)
        
        # Test 4: Collect results
        print("\n📊 Test 4: Collecting results...")
        results = aggregated_df.collect()
        print(f"✅ Collected {len(results)} aggregated rows")
        
        for row in results:
            print(f"  - {row['symbol']}: Volume={row['total_volume']:.2f}, "
                  f"AvgPrice={row['avg_price']:.2f}, "
                  f"MaxPrice={row['max_price']:.2f}, "
                  f"MinPrice={row['min_price']:.2f}")
        
        # Test 5: Spark context info
        print("\n📊 Test 5: Spark Context Information...")
        print(f"  - Spark Version: {spark.version}")
        print(f"  - App Name: {spark.sparkContext.appName}")
        print(f"  - Master: {spark.sparkContext.master}")
        print(f"  - Default Parallelism: {spark.sparkContext.defaultParallelism}")
        
        print("\n" + "=" * 60)
        print("✅ All tests passed successfully!")
        print("=" * 60)
        
        # Cleanup
        spark.stop()
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error occurred: {str(e)}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        if 'spark' in locals():
            spark.stop()
        sys.exit(1)

if __name__ == "__main__":
    main()

