from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    app_name: str = "crypto-fastapi"

    kafka_bootstrap: str = "192.168.49.2:30995"
    kafka_topic: str = "crypto_kline_1m"

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    mongo_uri: str = "mongodb+srv://vuongthanhsaovang:9KviWHBS85W7i4j6@ai-tutor.k6sjnzc.mongodb.net"
    mongo_db: str = "CRYPTO"
    mongo_collection_ohlc: str = "5m_kline"

    cors_origins: List[str] = ["*"]

    symbols: List[str] = [
        "BTCUSDT",
        "ETHUSDT",
        "BNBUSDT",
        "SOLUSDT",
        "ADAUSDT",
        "XRPUSDT",
        "DOGEUSDT",
        "DOTUSDT",
        "MATICUSDT",
        "AVAXUSDT",
        "LINKUSDT",
        "UNIUSDT",
        "LTCUSDT",
        "ATOMUSDT",
        "ETCUSDT",
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"  # Bỏ qua các biến môi trường không được định nghĩa


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()