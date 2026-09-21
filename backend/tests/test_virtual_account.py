"""T-003 가상계좌 테스트. 실제 DB·시장 데이터·증권사에 요청하지 않는다.

설정 검증은 순수 함수로, 엔드포인트는 저장소 함수와 커넥션을 mock해 확인한다.
정책 값은 테스트 전용 입력으로 주입하며, 서비스 코드나 단언에 정책 숫자를 하드코딩하지 않는다.
"""

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app import main, virtual_account
from app.config import VirtualPolicy, VirtualPolicyError, load_virtual_policy


def _client() -> TestClient:
    return TestClient(main.app)


def _settings(**override) -> SimpleNamespace:
    base = dict(
        virtual_initial_cash_krw="1000000",
        virtual_buy_fee_rate="0.001",
        virtual_sell_fee_rate="0.002",
        virtual_sell_tax_rate="0",
        virtual_slippage_bps="0",
        virtual_trading_policy_version="vtest",
    )
    base.update(override)
    return SimpleNamespace(**base)


def _account() -> dict:
    return {
        "id": 1,
        "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
        "policy_version": "vtest",
        "initial_cash_krw": 1000000,
        "buy_fee_rate": 0.001,
        "sell_fee_rate": 0.002,
        "sell_tax_rate": 0.0,
        "slippage_bps": 0,
    }


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


# --- 설정 검증 (순수) --------------------------------------------------------

def test_valid_policy_parses_as_integers_and_floats():
    p = load_virtual_policy(_settings())
    assert isinstance(p.initial_cash_krw, int) and p.initial_cash_krw == 1000000
    assert p.buy_fee_rate == 0.001 and p.sell_fee_rate == 0.002
    assert p.sell_tax_rate == 0.0 and p.slippage_bps == 0
    assert p.policy_version == "vtest"


@pytest.mark.parametrize(
    "override",
    [
        {"virtual_initial_cash_krw": None},          # 누락
        {"virtual_trading_policy_version": ""},      # 빈 값
        {"virtual_initial_cash_krw": "abc"},         # 형식 오류
        {"virtual_buy_fee_rate": "not-a-number"},    # 형식 오류
        {"virtual_initial_cash_krw": "-1"},          # 음수 현금
        {"virtual_initial_cash_krw": "0"},           # 0 현금(양수 아님)
        {"virtual_buy_fee_rate": "1"},               # 1 이상 수수료
        {"virtual_sell_tax_rate": "1.5"},            # 1 이상 세금
        {"virtual_sell_fee_rate": "-0.1"},           # 음수 비율
        {"virtual_slippage_bps": "-1"},              # 음수 슬리피지
    ],
)
def test_invalid_policy_raises_without_leaking_value(override):
    bad_value = next(iter(override.values()))
    with pytest.raises(VirtualPolicyError) as exc:
        load_virtual_policy(_settings(**override))
    msg = str(exc.value)
    # 메시지는 설정 값이 아니라 변수 이름 기반이어야 한다.
    assert "VIRTUAL_" in msg
    # 구분 가능한(길이 3 이상) 잘못된 값은 메시지에 그대로 노출되지 않는다.
    if bad_value and len(str(bad_value)) >= 3:
        assert str(bad_value) not in msg


# --- 초기화 ------------------------------------------------------------------

def test_first_initialize_creates_account_and_opening(monkeypatch):
    policy = VirtualPolicy(1000000, 0.001, 0.002, 0.0, 0, "vtest")
    monkeypatch.setattr(virtual_account, "get_virtual_policy", lambda: policy)
    monkeypatch.setattr(virtual_account, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: None)
    created = {"n": 0}

    def _create(cur, p):
        created["n"] += 1
        assert p is policy
        return _account()

    monkeypatch.setattr(virtual_account, "_create_account_with_opening", _create)
    monkeypatch.setattr(virtual_account, "_sum_cash", lambda cur, aid: 1000000)

    res = _client().post("/virtual-account/initialize")
    assert res.status_code == 200
    body = res.json()
    assert created["n"] == 1
    assert body["account_kind"] == "virtual_learning"
    assert body["available_cash_krw"] == 1000000
    assert body["policy_snapshot"]["initial_cash_krw"] == 1000000


def test_repeat_initialize_does_not_reset_or_add(monkeypatch):
    policy = VirtualPolicy(1000000, 0.001, 0.002, 0.0, 0, "vtest")
    monkeypatch.setattr(virtual_account, "get_virtual_policy", lambda: policy)
    monkeypatch.setattr(virtual_account, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: _account())

    def _must_not_create(cur, p):
        raise AssertionError("기존 계좌가 있는데 새 계좌/원장을 만들었다")

    monkeypatch.setattr(virtual_account, "_create_account_with_opening", _must_not_create)
    monkeypatch.setattr(virtual_account, "_sum_cash", lambda cur, aid: 1000000)

    res = _client().post("/virtual-account/initialize")
    assert res.status_code == 200
    assert res.json()["account_id"] == 1
    assert res.json()["available_cash_krw"] == 1000000


def test_initialize_config_error_does_not_touch_db(monkeypatch):
    def _bad_policy():
        raise VirtualPolicyError("VIRTUAL_INITIAL_CASH_KRW 설정이 필요합니다.")

    monkeypatch.setattr(virtual_account, "get_virtual_policy", _bad_policy)

    def _no_connect():
        raise AssertionError("설정 오류인데 DB에 접속했다")

    monkeypatch.setattr(virtual_account, "_connect", _no_connect)

    res = _client().post("/virtual-account/initialize")
    assert res.status_code == 500
    assert "필요" in res.json()["detail"]


# --- 조회 --------------------------------------------------------------------

def test_get_account_not_found(monkeypatch):
    monkeypatch.setattr(virtual_account, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: None)
    res = _client().get("/virtual-account")
    assert res.status_code == 404


def test_get_account_returns_snapshot_and_cash(monkeypatch):
    monkeypatch.setattr(virtual_account, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: _account())
    monkeypatch.setattr(virtual_account, "_sum_cash", lambda cur, aid: 900000)
    res = _client().get("/virtual-account")
    assert res.status_code == 200
    body = res.json()
    assert body["available_cash_krw"] == 900000
    assert body["policy_version"] == "vtest"
    assert body["policy_snapshot"]["slippage_bps"] == 0


def test_cash_ledger_not_found(monkeypatch):
    monkeypatch.setattr(virtual_account, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: None)
    res = _client().get("/virtual-account/cash-ledger")
    assert res.status_code == 404


def test_cash_ledger_returns_ascending(monkeypatch):
    monkeypatch.setattr(virtual_account, "_connect", _fake_connect)
    monkeypatch.setattr(virtual_account, "_select_account", lambda cur: _account())
    ledger = [
        {"id": 1, "account_id": 1, "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
         "entry_type": "opening_balance", "amount_krw": 1000000, "description": "최초 적립"},
        {"id": 2, "account_id": 1, "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
         "entry_type": "opening_balance", "amount_krw": 5000, "description": "예시"},
    ]
    monkeypatch.setattr(virtual_account, "_list_ledger", lambda cur, aid: ledger)
    res = _client().get("/virtual-account/cash-ledger")
    assert res.status_code == 200
    created = [e["created_at"] for e in res.json()["entries"]]
    assert created == sorted(created)
