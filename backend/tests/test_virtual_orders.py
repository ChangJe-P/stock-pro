"""T-004 가상 매수 주문 테스트. 실제 DB·pykrx·네트워크에 요청하지 않는다.

금액 계산은 순수 함수로, 엔드포인트는 저장소/가격 조회 함수와 커넥션을 mock해 확인한다.
실제 SQL(원자적 원장 기록, trade_date>decision 선택, 유일 제약)은 실DB 통합에서 별도 확인한다.
"""

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app import main, market_data, virtual_account, virtual_orders


def _client() -> TestClient:
    return TestClient(main.app)


class _FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeConn:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def cursor(self):
        return _FakeCursor()

    def commit(self):
        pass

    def rollback(self):
        pass


def _fake_connect():
    return _FakeConn()


def _account():
    return {"id": 1, "buy_fee_rate": 0.00015, "slippage_bps": 0}


def _pending_order():
    return {
        "id": 5, "account_id": 1, "ticker": "005930", "quantity": 3,
        "decision_trade_date": date(2024, 1, 2), "created_at": datetime(2024, 1, 2, tzinfo=timezone.utc),
        "status": "pending", "executed_at": None, "execution_trade_date": None,
        "base_open_price_krw": None, "execution_price_krw": None, "gross_amount_krw": None,
        "fee_krw": None, "price_data_source": None, "price_adjusted": None,
        "price_collection_run_id": None, "termination_reason": None,
    }


def _price():
    return {
        "trade_date": date(2024, 1, 3), "open_price": 1001, "data_source": "pykrx",
        "adjusted": False, "collection_run_id": "run-1",
    }


# --- 금액 계산(순수, 결정적 정수/Decimal) -----------------------------------

def test_compute_slippage_and_fee_are_ceiled():
    # open 1001 * (10000+50)/10000 = 1006.005 -> ceil 1007; gross 3021; fee ceil(0.45315)=1
    calc = virtual_orders.compute_execution(open_price=1001, quantity=3, slippage_bps=50, buy_fee_rate=0.00015)
    assert calc == {
        "execution_price_krw": 1007,
        "gross_amount_krw": 3021,
        "fee_krw": 1,
        "cash_delta_krw": -3022,
    }


def test_compute_zero_slippage_and_fee():
    calc = virtual_orders.compute_execution(open_price=1000, quantity=2, slippage_bps=0, buy_fee_rate=0)
    assert calc == {"execution_price_krw": 1000, "gross_amount_krw": 2000, "fee_krw": 0, "cash_delta_krw": -2000}


def test_compute_fee_exact_is_integer():
    calc = virtual_orders.compute_execution(open_price=10000, quantity=1, slippage_bps=0, buy_fee_rate=0.0001)
    assert calc["fee_krw"] == 1 and calc["cash_delta_krw"] == -10001


# --- 주문 생성 입력 검증 -----------------------------------------------------

@pytest.mark.parametrize(
    "body",
    [
        {"ticker": "12", "quantity": 1, "decision_trade_date": "2024-01-02"},   # 6자리 아님
        {"ticker": "005930", "quantity": 0, "decision_trade_date": "2024-01-02"},  # 양수 아님
        {"ticker": "005930", "quantity": -5, "decision_trade_date": "2024-01-02"},  # 음수
    ],
)
def test_create_order_rejects_bad_input(body):
    assert _client().post("/virtual-orders", json=body).status_code == 422


# --- 계좌 없음 ---------------------------------------------------------------

def test_create_order_account_not_found(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: None)
    res = _client().post("/virtual-orders", json={"ticker": "005930", "quantity": 1, "decision_trade_date": "2024-01-02"})
    assert res.status_code == 404


def test_execute_account_not_found(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_orders, "_lock_account", lambda cur: None)
    res = _client().post("/virtual-orders/5/execute")
    assert res.status_code == 404


# --- 결정일 가격 없음 → 409, 외부 수집 없음, 주문 미생성 ----------------------

def test_create_order_requires_decision_day_price(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: _account())
    monkeypatch.setattr(market_data, "stored_unadjusted_price_exists", lambda cur, t, d: False)

    def _must_not_insert(*a, **k):
        raise AssertionError("결정일 가격이 없는데 주문을 생성했다")

    monkeypatch.setattr(virtual_orders, "_insert_pending_order", _must_not_insert)
    # 외부 수집 함수를 부르면 실패로 간주
    monkeypatch.setattr(market_data, "collect_daily_prices", lambda *a, **k: (_ for _ in ()).throw(AssertionError("외부 수집 호출")))

    res = _client().post("/virtual-orders", json={"ticker": "005930", "quantity": 1, "decision_trade_date": "2024-01-02"})
    assert res.status_code == 409


def test_create_order_creates_pending_without_cash_change(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: _account())
    monkeypatch.setattr(market_data, "stored_unadjusted_price_exists", lambda cur, t, d: True)
    monkeypatch.setattr(virtual_orders, "_insert_pending_order", lambda cur, aid, t, q, d: _pending_order())

    res = _client().post("/virtual-orders", json={"ticker": "005930", "quantity": 3, "decision_trade_date": "2024-01-02"})
    assert res.status_code == 200
    body = res.json()
    assert body["status"] == "pending"
    assert body["side"] == "buy"
    assert body["gross_amount_krw"] is None  # 현금 계산·차감 없음


# --- 체결: 다음 거래일 가격 부재 → pending 유지 409 --------------------------

def test_execute_pending_kept_when_no_next_day_price(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_orders, "_lock_account", lambda cur: _account())
    monkeypatch.setattr(virtual_orders, "_select_order", lambda cur, oid, lock=False: _pending_order())
    monkeypatch.setattr(market_data, "earliest_unadjusted_open_after", lambda cur, t, d: None)

    def _must_not_write(*a, **k):
        raise AssertionError("가격이 없는데 주문을 변경했다")

    monkeypatch.setattr(virtual_orders, "_mark_filled", _must_not_write)
    monkeypatch.setattr(virtual_orders, "_mark_rejected", _must_not_write)

    res = _client().post("/virtual-orders/5/execute")
    assert res.status_code == 409


# --- 체결: 성공 → filled + 음수 원장 한 번, 결정일보다 뒤 시가 사용 ----------

def test_execute_fills_with_next_day_open(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_orders, "_lock_account", lambda cur: _account())
    monkeypatch.setattr(virtual_orders, "_select_order", lambda cur, oid, lock=False: _pending_order())

    seen = {}

    def _earliest(cur, ticker, decision):
        seen["decision"] = decision
        seen["ticker"] = ticker
        return _price()

    monkeypatch.setattr(market_data, "earliest_unadjusted_open_after", _earliest)
    monkeypatch.setattr(virtual_account, "_sum_cash", lambda cur, aid: 10_000_000)

    calls = {"filled": 0}

    def _mark_filled(cur, account_id, order_id, now, price, calc):
        calls["filled"] += 1
        seen["calc"] = calc
        seen["price"] = price
        order = _pending_order()
        order.update(status="filled", gross_amount_krw=calc["gross_amount_krw"], fee_krw=calc["fee_krw"])
        return order

    monkeypatch.setattr(virtual_orders, "_mark_filled", _mark_filled)
    monkeypatch.setattr(virtual_orders, "_mark_rejected",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("현금 충분한데 거부")))

    res = _client().post("/virtual-orders/5/execute")
    assert res.status_code == 200
    assert res.json()["status"] == "filled"
    assert calls["filled"] == 1
    # 결정일(2024-01-02)을 기준으로 그 뒤 시가를 조회한다. 기준가는 조회된 open_price다.
    assert seen["decision"] == date(2024, 1, 2)
    assert seen["price"]["trade_date"] == date(2024, 1, 3)
    # open 1001, slippage 0, qty 3 -> gross 3003, fee ceil(0.45045)=1
    assert seen["calc"]["gross_amount_krw"] == 3003 and seen["calc"]["fee_krw"] == 1


# --- 체결: 현금 부족 → rejected, 원장 없음 -----------------------------------

def test_execute_rejected_on_insufficient_cash(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_orders, "_lock_account", lambda cur: _account())
    monkeypatch.setattr(virtual_orders, "_select_order", lambda cur, oid, lock=False: _pending_order())
    monkeypatch.setattr(market_data, "earliest_unadjusted_open_after", lambda cur, t, d: _price())
    monkeypatch.setattr(virtual_account, "_sum_cash", lambda cur, aid: 100)  # 부족

    calls = {"rejected": 0}

    def _mark_rejected(cur, order_id, now, price, calc):
        calls["rejected"] += 1
        order = _pending_order()
        order.update(status="rejected_insufficient_cash", termination_reason="insufficient_cash")
        return order

    monkeypatch.setattr(virtual_orders, "_mark_rejected", _mark_rejected)
    monkeypatch.setattr(virtual_orders, "_mark_filled",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("현금 부족한데 체결")))

    res = _client().post("/virtual-orders/5/execute")
    assert res.status_code == 200
    assert res.json()["status"] == "rejected_insufficient_cash"
    assert calls["rejected"] == 1


# --- 체결: 이미 종료된 주문은 결과만 반환, 원장 추가 없음 ---------------------

def test_execute_terminated_order_returns_existing(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_orders, "_lock_account", lambda cur: _account())
    filled = _pending_order()
    filled.update(status="filled", gross_amount_krw=3003, fee_krw=1)
    monkeypatch.setattr(virtual_orders, "_select_order", lambda cur, oid, lock=False: filled)

    def _must_not(*a, **k):
        raise AssertionError("종료된 주문을 다시 처리했다")

    monkeypatch.setattr(market_data, "earliest_unadjusted_open_after", _must_not)
    monkeypatch.setattr(virtual_orders, "_mark_filled", _must_not)
    monkeypatch.setattr(virtual_orders, "_mark_rejected", _must_not)

    res = _client().post("/virtual-orders/5/execute")
    assert res.status_code == 200
    assert res.json()["status"] == "filled"


# --- 목록 조회: 외부 수집·체결 시작 안 함, 순서 유지 -------------------------

def test_list_orders_returns_rows(monkeypatch):
    monkeypatch.setattr(virtual_orders, "_connect", _fake_connect)
    o1 = _pending_order()
    o2 = _pending_order()
    o2["id"] = 6
    o2["created_at"] = datetime(2024, 1, 4, tzinfo=timezone.utc)
    monkeypatch.setattr(virtual_orders, "_select_all_orders", lambda cur: [o1, o2])
    res = _client().get("/virtual-orders")
    assert res.status_code == 200
    ids = [o["order_id"] for o in res.json()["orders"]]
    assert ids == [5, 6]
