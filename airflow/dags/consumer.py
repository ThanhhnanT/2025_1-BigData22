import sys
import os
sys.path.append(os.path.expanduser("~/D/anaconda3/envs/bigdata/lib/python3.10/site-packages"))

from airflow import DAG
from airflow.providers.standard.operators.python import PythonOperator
from datetime import datetime, timedelta
from quixstreams import Application



def extract_coin_data(message):
    latest_quote = message["quote"]["USD"]
    return {
        "coin": message["name"],
        "price_usd": latest_quote["price"],
        "volume": latest_quote["volume_24h"],
        "updated": message["last_updated"],
    }


def consume_kafka_messages(**context):
    app = Application(
        broker_address="localhost:9092",
        consumer_group="coin_group",
        auto_offset_reset="earliest",
    )

    coins_topic = app.topic(name="coins", value_deserializer="json")
    sdf = app.dataframe(topic=coins_topic)
    sdf = sdf.apply(extract_coin_data)

    collected = []

    def collect_data(coin_data):
        collected.append(coin_data)
        print("📥 Received:", coin_data)

    sdf.update(collect_data)

    with app.run():
        pass

    print(f"✅ Collected {len(collected)} messages")




default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(seconds=10),
}

with DAG(
    dag_id="kafka_consumer_dag",
    default_args=default_args,
    catchup=False,
    tags=["kafka", "crypto"],
) as dag:

    consume_task = PythonOperator(
        task_id="consume_kafka_messages",
        python_callable=consume_kafka_messages,
    )

    consume_task