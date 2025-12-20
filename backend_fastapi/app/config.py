from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import List
import os


class Settings(BaseSettings):
    app_name: str = "crypto-fastapi"

    kafka_bootstrap: str = os.getenv("KAFKA_BOOTSTRAP", "192.168.49.2:30995")
    kafka_topic: str = "crypto_kline_1m"

    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "123456")

    mongo_uri: str = "mongodb://localhost:27017"
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