from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    app_name: str = "crypto-fastapi"

    kafka_bootstrap: str = "192.168.49.2:30995"
    kafka_topic: str = "crypto_kline_1m"

    redis_host: str = "192.168.49.2"
    redis_port: int = 31001
    redis_db: int = 0
    redis_password: str = "123456"

    mongo_uri: str = "mongodb://root:8WcVPD9QHx@192.168.49.2:30376/"
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
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()