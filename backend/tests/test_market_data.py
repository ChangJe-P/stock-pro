"""T-002 시장 데이터 테스트. pykrx 호출과 DB 접근을 모두 mock해 실제 네트워크·DB를 쓰지 않는다."""

from datetime import date

import pandas as pd
from fastapi.testclient import TestClient
from psycopg.types.json import Json

from app import main, market_data


class _FakeCursor:
    """store_collection·record_failed_fetch의 SQL을 실제 DB 없이 잡아내는 가짜 커서."""

    def __init__(self, store):
        self._store = store
        self._last = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params=None):
        if "INSERT INTO daily_prices" in sql:
            self._last = {"inserted": True}  # 신규 삽입으로 간주
        elif "INSERT INTO market_data_collection_runs" in sql:
            self._store["run_params"] = params
        else:
            self._last = None

    def fetchone(self):
        return self._last


class _FakeConn:
    def __init__(self, store):
        self._store = store

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _FakeCursor(self._store)

    def commit(self):
        pass


def _fake_connect(store):
    return lambda: _FakeConn(store)


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


def test_duplicate_date_recorded_even_when_first_row_invalid():
    # 경계 사례: 같은 거래일의 첫 행이 0가격(제외)이고 두 번째 행이 정상이어도
    # 두 번째 행은 duplicate_date로 남아야 한다(원본 중복을 숨기지 않는다).
    df = pd.DataFrame(
        {
            "시가": [0, 100],
            "고가": [110, 110],
            "저가": [90, 90],
            "종가": [105, 105],
            "거래량": [1000, 1000],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-02"]),
    )
    valid, excluded = market_data.validate_and_transform(df, "005930", date(2024, 1, 1), date(2024, 1, 5))

    assert valid == []
    reasons = sorted(e["reason"] for e in excluded)
    assert reasons == ["duplicate_date", "non_positive_price"]
    assert market_data.summarize_excluded(excluded) == {"non_positive_price": 1, "duplicate_date": 1}


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

def test_get_returns_ascending_and_does_not_trigger_fetch(monkeypatch):
    def _no_fetch(*a, **k):
        raise AssertionError("GET이 외부 수집을 시작했다")

    monkeypatch.setattr(market_data, "fetch_ohlcv", _no_fetch)
    # 저장소는 거래일 오름차순으로 반환한다(SQL ORDER BY). 엔드포인트가 순서를 유지하는지 단언한다.
    monkeypatch.setattr(
        market_data,
        "query_daily_prices",
        lambda t, f, to: [
            {"ticker": t, "trade_date": date(2024, 1, 2), "close_price": 100},
            {"ticker": t, "trade_date": date(2024, 1, 3), "close_price": 105},
        ],
    )
    res = _client().get(
        "/market-data/daily-prices",
        params={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 200
    dates = [r["trade_date"] for r in res.json()["rows"]]
    assert dates == ["2024-01-02", "2024-01-03"]
    assert dates == sorted(dates)


# --- 실행 기록: 제외 사유와 실패 실행 (P1) -----------------------------------

def test_collect_records_excluded_reasons(monkeypatch):
    """제외 행의 이유별 건수가 실행 기록(INSERT)에 저장되는지 확인한다."""
    monkeypatch.setattr(market_data, "get_settings", lambda: _Settings(configured=True))
    df = pd.DataFrame(
        {
            "시가": [100, 0, 200],
            "고가": [110, 110, 210],
            "저가": [90, 90, 190],
            "종가": [105, 105, 205],
            "거래량": [1000, 1000, 2000],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-10"]),
    )
    monkeypatch.setattr(market_data, "fetch_ohlcv", lambda *a, **k: df)
    store: dict = {}
    monkeypatch.setattr(market_data, "_connect", _fake_connect(store))

    res = _client().post(
        "/market-data/daily-prices/collect",
        json={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "partial"
    assert body["excluded_reasons"] == {"non_positive_price": 1, "out_of_range": 1}

    # 실행 기록 INSERT의 JSONB 파라미터에 이유별 건수가 담겼는지 확인한다.
    params = store["run_params"]
    json_arg = next(p for p in params if isinstance(p, Json))
    assert json_arg.obj == {"non_positive_price": 1, "out_of_range": 1}
    assert "partial" in params


def test_external_failure_records_failed_run(monkeypatch):
    """외부 조회 실패도 DB가 정상이면 failed 실행으로 남는지 확인한다."""
    monkeypatch.setattr(market_data, "get_settings", lambda: _Settings(configured=True))
    monkeypatch.setattr(market_data, "fetch_ohlcv", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    store: dict = {}
    monkeypatch.setattr(market_data, "_connect", _fake_connect(store))

    res = _client().post(
        "/market-data/daily-prices/collect",
        json={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 502
    params = store["run_params"]
    assert "failed" in params
    assert "external_fetch_failed" in params


def test_get_rejects_bad_ticker():
    res = _client().get(
        "/market-data/daily-prices",
        params={"ticker": "abc", "from_date": "2024-01-01", "to_date": "2024-01-05"},
    )
    assert res.status_code == 422
