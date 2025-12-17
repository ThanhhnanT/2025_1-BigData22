from fastapi.testclient import TestClient

from backend_fastapi.app.main import app, get_mongo, get_redis


class _FakeCursor:
    def __init__(self, docs):
        self.docs = docs

    def sort(self, *_args, **_kwargs):
        return self

    def limit(self, *_args, **_kwargs):
        return self

    async def to_list(self, length=None):
        return self.docs[:length]


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs

    def find(self, _query):
        return _FakeCursor(self.docs)


class _FakeMongo:
    def __init__(self, docs):
        self.docs = docs

    def __getitem__(self, _name):
        return _FakeCollection(self.docs)


class _FakeRedis:
    def __init__(self, value):
        self.value = value

    async def get(self, _key):
        return self.value


fake_candle = {
    "openTime": 1,
    "closeTime": 2,
    "open": 1.0,
    "high": 2.0,
    "low": 0.5,
    "close": 1.5,
    "volume": 10,
    "trades": 5,
    "interval": "5m",
    "symbol": "BTCUSDT",
}

fake_latest = {
    "s": "BTCUSDT",
    "i": "1m",
    "t": 1,
    "T": 2,
    "o": "1.0",
    "h": "2.0",
    "l": "0.5",
    "c": "1.5",
    "v": "10",
    "q": "100",
    "n": 5,
    "x": True,
    "openTime": 1,
    "closeTime": 2,
    "open": 1.0,
    "high": 2.0,
    "low": 0.5,
    "close": 1.5,
    "volume": 10.0,
    "quoteVolume": 100.0,
    "trades": 5,
}


async def override_mongo():
    return _FakeMongo([fake_candle])


async def override_redis():
    return _FakeRedis(value=json_dump(fake_latest))


def json_dump(obj):
    import json
    return json.dumps(obj)


app.dependency_overrides[get_mongo] = override_mongo
app.dependency_overrides[get_redis] = override_redis

client = TestClient(app)


def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["status"] == "ok"


def test_ohlc():
    res = client.get("/ohlc", params={"symbol": "BTCUSDT", "interval": "5m", "limit": 10})
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["count"] == 1
    assert len(data["candles"]) == 1


def test_latest():
    res = client.get("/latest", params={"symbol": "BTCUSDT"})
    assert res.status_code == 200
    data = res.json()
    assert data["symbol"] == "BTCUSDT"
    assert data["interval"] == "1m"

