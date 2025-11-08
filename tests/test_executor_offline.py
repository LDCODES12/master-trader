import os
import pytest
from fastapi.testclient import TestClient
from apps.executor.app import app
from tests.conftest import my_vcr


client = TestClient(app)


def test_status_ok():
    r = client.get("/status")
    assert r.status_code == 200
    assert r.json().get("ok") is True


@my_vcr.use_cassette("price_btcusdt_1m.yaml")
def test_price_public_klines():
    r = client.get("/price", params={"symbol": "BTCUSDT"})
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "BTCUSDT"
    assert float(body["price"]) > 0


@my_vcr.use_cassette("price_btcusdt_1m.yaml")
def test_orders_dry_run_simulated():
    os.environ["EXEC_MODE"] = "dry_run"
    body = {"symbol": "BTCUSDT", "side": "buy", "quote_qty": 20, "venue": "binance", "idempotency_key": "t-1"}
    r = client.post("/orders", json=body)
    assert r.status_code == 200
    data = r.json()["body"]
    assert data["status"] == "simulated"
    assert float(data["avg_price"]) > 0

