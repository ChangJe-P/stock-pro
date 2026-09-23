"""T-005 Django 테스트. 외부 pykrx는 mock 처리하고, DB는 Django 테스트 DB(실제 Postgres)를 쓴다.

health, 시장 데이터 검증·upsert·GET 무외부호출, 단일 계좌·원장, 다음 거래일 시가·비용 올림·
현금 부족·반복 체결, root template 렌더링을 확인한다.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
from django.test import TestCase, override_settings

from trading import accounts, market_data, orders
from trading.config import VirtualPolicyError, load_virtual_policy
from trading.models import CashLedgerEntry, DailyPrice, MarketDataCollectionRun, VirtualBuyOrder

POLICY = dict(
    VIRTUAL_INITIAL_CASH_KRW="1000000",
    VIRTUAL_BUY_FEE_RATE="0.00015",
    VIRTUAL_SELL_FEE_RATE="0.00015",
    VIRTUAL_SELL_TAX_RATE="0",
    VIRTUAL_SLIPPAGE_BPS="0",
    VIRTUAL_TRADING_POLICY_VERSION="vtest",
    MARKET_DATA_PROVIDER="pykrx",
)


def _df(rows):
    idx = pd.to_datetime([r[0] for r in rows])
    return pd.DataFrame(
        {
            "시가": [r[1] for r in rows], "고가": [r[2] for r in rows], "저가": [r[3] for r in rows],
            "종가": [r[4] for r in rows], "거래량": [r[5] for r in rows],
        },
        index=idx,
    )


def _seed_price(ticker, d, open_p):
    DailyPrice.objects.create(
        ticker=ticker, trade_date=d, open_price=open_p, high_price=open_p + 50,
        low_price=open_p - 50, close_price=open_p + 10, volume=1000, data_source="pykrx",
        adjusted=False, collected_at=datetime(2024, 1, 1, tzinfo=timezone.utc), collection_run_id="seed",
    )


class HealthTests(TestCase):
    def test_health_ok(self):
        res = self.client.get("/health")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["database"], "connected")


class MarketDataValidationTests(TestCase):
    def test_duplicate_and_quality_split(self):
        df = _df([
            ("2024-01-01", 100, 110, 90, 105, 1000),
            ("2024-01-01", 100, 110, 90, 105, 1000),  # duplicate_date
            ("2024-01-02", 0, 110, 90, 105, 1000),     # non_positive
            ("2024-01-10", 100, 110, 90, 105, 1000),   # out_of_range
        ])
        valid, excluded = market_data.validate_and_transform(df, "005930", date(2024, 1, 1), date(2024, 1, 5))
        self.assertEqual(len(valid), 1)
        self.assertEqual(
            {e["reason"] for e in excluded}, {"duplicate_date", "non_positive_price", "out_of_range"}
        )


@override_settings(**POLICY)
class MarketDataApiTests(TestCase):
    def test_collect_stores_rows_and_run(self):
        df = _df([("2024-01-02", 100, 110, 90, 105, 1000), ("2024-01-10", 100, 110, 90, 105, 1000)])
        with patch("trading.market_data.fetch_ohlcv", return_value=df):
            res = self.client.post(
                "/market-data/daily-prices/collect",
                data={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
                content_type="application/json",
            )
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "partial")
        self.assertEqual(body["excluded_reasons"], {"out_of_range": 1})
        self.assertEqual(DailyPrice.objects.filter(ticker="005930").count(), 1)
        self.assertEqual(MarketDataCollectionRun.objects.count(), 1)

    @override_settings(MARKET_DATA_PROVIDER="")
    def test_collect_blocked_when_not_pykrx(self):
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 호출")):
            res = self.client.post(
                "/market-data/daily-prices/collect",
                data={"ticker": "005930", "from_date": "2024-01-01", "to_date": "2024-01-05"},
                content_type="application/json",
            )
        self.assertEqual(res.status_code, 503)

    def test_collect_rejects_bad_ticker(self):
        res = self.client.post(
            "/market-data/daily-prices/collect",
            data={"ticker": "12", "from_date": "2024-01-01", "to_date": "2024-01-05"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 422)

    def test_get_is_ascending_and_no_external_call(self):
        _seed_price("005930", date(2024, 1, 3), 1030)
        _seed_price("005930", date(2024, 1, 2), 1000)
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("GET이 외부 수집 시작")):
            res = self.client.get("/market-data/daily-prices?ticker=005930&from_date=2024-01-01&to_date=2024-01-05")
        self.assertEqual(res.status_code, 200)
        dates = [r["trade_date"] for r in res.json()["rows"]]
        self.assertEqual(dates, sorted(dates))


class PolicyValidationTests(TestCase):
    @override_settings(**POLICY)
    def test_valid_policy(self):
        p = load_virtual_policy()
        self.assertEqual(p.initial_cash_krw, 1000000)
        self.assertIsInstance(p.initial_cash_krw, int)

    @override_settings(**{**POLICY, "VIRTUAL_BUY_FEE_RATE": "1"})
    def test_rate_out_of_range(self):
        with self.assertRaises(VirtualPolicyError):
            load_virtual_policy()

    @override_settings(**{**POLICY, "VIRTUAL_INITIAL_CASH_KRW": None})
    def test_missing_cash(self):
        with self.assertRaises(VirtualPolicyError):
            load_virtual_policy()


@override_settings(**POLICY)
class VirtualAccountTests(TestCase):
    def test_initialize_creates_single_and_opening(self):
        res = self.client.post("/virtual-account/initialize")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["available_cash_krw"], 1000000)
        # 반복 초기화: 재설정·행 추가 없음
        self.client.post("/virtual-account/initialize")
        from trading.models import VirtualAccount
        self.assertEqual(VirtualAccount.objects.count(), 1)
        self.assertEqual(CashLedgerEntry.objects.count(), 1)

    def test_get_account_not_found(self):
        self.assertEqual(self.client.get("/virtual-account").status_code, 404)

    def test_cash_ledger_ascending(self):
        self.client.post("/virtual-account/initialize")
        res = self.client.get("/virtual-account/cash-ledger")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["entries"][0]["entry_type"], "opening_balance")


class ComputeTests(TestCase):
    def test_slippage_and_fee_ceil(self):
        calc = orders.compute_execution(open_price=1001, quantity=3, slippage_bps=50, buy_fee_rate=0.00015)
        self.assertEqual(calc, {"execution_price_krw": 1007, "gross_amount_krw": 3021, "fee_krw": 1, "cash_delta_krw": -3022})


@override_settings(**POLICY)
class OrderTests(TestCase):
    def _init(self):
        self.client.post("/virtual-account/initialize")

    def test_create_requires_decision_day_price(self):
        self._init()
        res = self.client.post(
            "/virtual-orders",
            data={"ticker": "005930", "quantity": 1, "decision_trade_date": "2024-01-02"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 409)

    def test_create_pending_without_cash_change(self):
        self._init()
        _seed_price("005930", date(2024, 1, 2), 900)
        res = self.client.post(
            "/virtual-orders",
            data={"ticker": "005930", "quantity": 3, "decision_trade_date": "2024-01-02"},
            content_type="application/json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["status"], "pending")
        # 현금 불변
        self.assertEqual(self.client.get("/virtual-account").json()["available_cash_krw"], 1000000)

    def test_execute_fills_with_next_day_open(self):
        self._init()
        _seed_price("005930", date(2024, 1, 2), 900)   # 결정일(같은 날, 사용 금지)
        _seed_price("005930", date(2024, 1, 3), 1000)  # 다음 거래일 시가
        order_id = self.client.post(
            "/virtual-orders",
            data={"ticker": "005930", "quantity": 2, "decision_trade_date": "2024-01-02"},
            content_type="application/json",
        ).json()["order_id"]
        res = self.client.post(f"/virtual-orders/{order_id}/execute")
        self.assertEqual(res.status_code, 200)
        body = res.json()
        self.assertEqual(body["status"], "filled")
        self.assertEqual(body["execution_trade_date"], "2024-01-03")
        self.assertEqual(body["base_open_price_krw"], 1000)
        self.assertEqual(body["gross_amount_krw"], 2000)
        self.assertEqual(body["fee_krw"], 1)  # ceil(2000 * 0.00015)
        # 음수 원장 한 행
        self.assertEqual(CashLedgerEntry.objects.filter(entry_type="buy_execution").count(), 1)
        self.assertEqual(self.client.get("/virtual-account").json()["available_cash_krw"], 1000000 - 2001)
        # 반복 체결: 결과만 반환, 원장 추가 없음
        self.client.post(f"/virtual-orders/{order_id}/execute")
        self.assertEqual(CashLedgerEntry.objects.filter(entry_type="buy_execution").count(), 1)

    def test_execute_pending_when_no_next_day(self):
        self._init()
        _seed_price("005930", date(2024, 1, 3), 1000)  # 결정일이 곧 마지막
        order_id = self.client.post(
            "/virtual-orders",
            data={"ticker": "005930", "quantity": 1, "decision_trade_date": "2024-01-03"},
            content_type="application/json",
        ).json()["order_id"]
        res = self.client.post(f"/virtual-orders/{order_id}/execute")
        self.assertEqual(res.status_code, 409)
        self.assertEqual(VirtualBuyOrder.objects.get(id=order_id).status, "pending")

    def test_execute_rejected_on_insufficient_cash(self):
        self._init()
        _seed_price("005930", date(2024, 1, 2), 900)
        _seed_price("005930", date(2024, 1, 3), 1000)
        order_id = self.client.post(
            "/virtual-orders",
            data={"ticker": "005930", "quantity": 100000, "decision_trade_date": "2024-01-02"},
            content_type="application/json",
        ).json()["order_id"]
        res = self.client.post(f"/virtual-orders/{order_id}/execute")
        self.assertEqual(res.json()["status"], "rejected_insufficient_cash")
        self.assertEqual(CashLedgerEntry.objects.filter(entry_type="buy_execution").count(), 0)
        self.assertEqual(self.client.get("/virtual-account").json()["available_cash_krw"], 1000000)


class JsonBodyContractTests(TestCase):
    """공통 JSON 파서는 문법상 유효해도 객체(dict)가 아니면 500이 아닌 안전한 422 JSON을 낸다."""

    def test_collect_rejects_json_array_body(self):
        res = self.client.post(
            "/market-data/daily-prices/collect", data="[]", content_type="application/json"
        )
        self.assertEqual(res.status_code, 422)
        self.assertIn("detail", res.json())

    def test_orders_rejects_json_array_body(self):
        res = self.client.post("/virtual-orders", data="[]", content_type="application/json")
        self.assertEqual(res.status_code, 422)
        self.assertIn("detail", res.json())


class DashboardTests(TestCase):
    def test_dashboard_read_only_renders(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "가상 학습 계좌")
        # 계좌·주문이 생성되지 않았음(대시보드는 읽기 전용)
        from trading.models import VirtualAccount
        self.assertEqual(VirtualAccount.objects.count(), 0)
