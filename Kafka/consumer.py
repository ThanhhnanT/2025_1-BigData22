from quixstreams import Application
# from quixstreams.sinks.community.postgresql import PostgreSQLSink


def extract_coin_data(message):
    latest_quote = message["quote"]["USD"]
    return {
        "coin": message["name"],
        "price_usd": latest_quote["price"],
        "volume": latest_quote["volume_24h"],
        "updated": message["last_updated"],
    }

def main():

    app = Application(
        broker_address="192.168.49.2:30113",
        consumer_group="coin_group",
        auto_offset_reset="earliest",
    )

    coins_topic = app.topic(name="coins", value_deserializer="json")

    sdf = app.dataframe(topic=coins_topic)

    sdf = sdf.apply(extract_coin_data)

    sdf.update(lambda coin_data: print(coin_data))

    app.run()


if __name__ == "__main__":
    main()