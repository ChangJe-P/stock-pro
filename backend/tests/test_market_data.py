"""T-002 시장 데이터 테스트. pykrx 호출과 DB 접근을 모두 mock해 실제 네트워크·DB를 쓰지 않는다."""

from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app import main, market_data


def _client() -> TestClient:
    return TestClient(main.app)


class _Settings:
    def __init__(self, configured: bool):
        self.market_data_configured = configured
        self.database_url = "postgresql://unused"


def _good_df() -> pd.DataFrame:
    return pd.DataFrame(
        {"시가": [100], "고가": [110], "저가": [90], "종가": [105], "거래량": [1000]},
        index=pd.to_datetime(["2024-01-02"]),
    )


# --- 검증 로직 (순수 함수) ---------------------------------------------------

def test_validate_and_transform_splits_valid_and_excluded():
    df = pd.DataFrame(
        {
            "시가": [100, 100, 0, 55, 100, 100],
            "고가": [110, 110, 110, 60, 110, 110],
            "저가": [90, 90, 90, 70, 90, 90],
            "종가": [105, 105, 105, 58, 105, 105],
            "거래량": [1000, 1000, 1000, 1000, -5, 1000],
        },
        index=pd.to_datetime(
            ["2024-01-01", "2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-10"]
        ),
    )
    valid, excluded = market_data.validate_and_transform(df, "005930", date(2024, 1, 1), date(2024, 1, 5))

    assert len(valid) == 1
    assert valid[0]["trade_date"] == date(2024, 1, 1)
    reasons = {e["reason"] for e in excluded}
    assert reasons == {"duplicate_date", "non_positive_price", "invalid_ohlc", "negative_volume", "out_of_range"}


def test_non_trading_empty_is_not_error():
    empty = pd.DataFrame({"시가": [], "고가": [], "저가": [], "종가": [], "거래량": []}, index=pd.to_datetime([]))
    valid, excluded = market_data.validate_and_transform(empty, "005930", date(2024, 1, 1), date(2024, 1, 5))
    assert valid == [] and excluded == []
    assert market_data._decide_status(0, 0, 0) == ("partial", "no_data_in_range")


# --- 설정 게이트 -------------------------------------------------------------

def test_collect_blocked_when_not_pykrx(monkeypatch):
    monkeypatch.setattr(market_data, "get_settings", lambda: _Settings(configured=False))

    def _no_fetch(*a, **k):
        raise AssertionError("설정되지 않았는데 외부 요청을 보냈다")

    monkeypatch.setattr(market_data, "fetch_ohlcv", _no_fetch)

    res = _client().post(
        "/market-data/daily-prices/collect",
        json={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 503
    assert "pykrx" in res.json()["detail"]


# --- 수집 오케스트레이션 -----------------------------------------------------

def test_collect_success_flow(monkeypatch):
    monkeypatch.setattr(market_data, "get_settings", lambda: _Settings(configured=True))
    monkeypatch.setattr(market_data, "fetch_ohlcv", lambda *a, **k: _good_df())

    captured = {}

    def _fake_store(ticker, from_date, to_date, df, valid_rows, excluded_rows):
        captured["valid"] = valid_rows
        captured["excluded"] = excluded_rows
        return {"status": "success", "inserted_rows": len(valid_rows), "run_id": "test"}

    monkeypatch.setattr(market_data, "store_collection", _fake_store)

    res = _client().post(
        "/market-data/daily-prices/collect",
        json={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"
    assert len(captured["valid"]) == 1 and captured["excluded"] == []


def test_collect_external_failure_is_safe(monkeypatch):
    monkeypatch.setattr(market_data, "get_settings", lambda: _Settings(configured=True))

    def _boom(*a, **k):
        raise RuntimeError("provider secret detail should not leak")

    monkeypatch.setattr(market_data, "fetch_ohlcv", _boom)
    res = _client().post(
        "/market-data/daily-prices/collect",
        json={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 502
    assert "secret" not in res.json()["detail"]


# --- 입력 검증 ---------------------------------------------------------------

def test_collect_rejects_bad_ticker():
    res = _client().post(
        "/market-data/daily-prices/collect",
        json={"ticker": "12ab", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 422


def test_collect_rejects_reversed_range():
    res = _client().post(
        "/market-data/daily-prices/collect",
        json={"ticker": "005930", "from_date": "2024-01-05", "to_date": "2024-01-01"},
    )
    assert res.status_code == 422


# --- 조회 API는 외부 수집을 하지 않는다 --------------------------------------

def test_get_does_not_trigger_fetch(monkeypatch):
    def _no_fetch(*a, **k):
        raise AssertionError("GET이 외부 수집을 시작했다")

    monkeypatch.setattr(market_data, "fetch_ohlcv", _no_fetch)
    monkeypatch.setattr(
        market_data,
        "query_daily_prices",
        lambda t, f, to: [
            {"ticker": t, "trade_date": date(2024, 1, 3), "close_price": 105},
            {"ticker": t, "trade_date": date(2024, 1, 2), "close_price": 100},
        ],
    )
    res = _client().get(
        "/market-data/daily-prices",
        params={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 200
    assert len(res.json()["rows"]) == 2


def test_get_rejects_bad_ticker():
    res = _client().get(
        "/market-data/daily-prices",
        params={"ticker": "abc", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 422
