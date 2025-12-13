from kafka import KafkaAdminClient
from kafka.admin import NewTopic
from kafka.errors import TopicAlreadyExistsError

KAFKA_BROKER = "192.168.49.2:30113"
TOPIC = "crypto_kline_1m"
NUM_PARTITIONS = 5
REPLICATION_FACTOR = 3

def create_topic():
    admin_client = KafkaAdminClient(
        bootstrap_servers=KAFKA_BROKER,
        client_id='topic_creator'
    )
    
    topic = NewTopic(
        name=TOPIC,
        num_partitions=NUM_PARTITIONS,
        replication_factor=REPLICATION_FACTOR
    )
    
    try:
        admin_client.create_topics(new_topics=[topic], validate_only=False)
        print(f"✅ Topic '{TOPIC}' đã được tạo thành công!")
        print(f"   - Số partition: {NUM_PARTITIONS}")
        print(f"   - Replication factor: {REPLICATION_FACTOR}")
        print(f"   - Có thể chạy tối đa {NUM_PARTITIONS} consumer song song trong cùng consumer group")
    except TopicAlreadyExistsError:
        print(f"⚠️  Topic '{TOPIC}' đã tồn tại!")
        print(f"   Nếu muốn thay đổi số partition, cần xóa topic cũ trước:")
        print(f"   kubectl delete kafkatopic {TOPIC} -n kafka")
    except Exception as e:
        print(f"❌ Lỗi khi tạo topic: {e}")
        print(f"   Kiểm tra kết nối đến Kafka broker: {KAFKA_BROKER}")
    finally:
        admin_client.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Tạo Kafka Topic với Partition")
    print("=" * 60)
    create_topic()

