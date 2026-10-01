"""T-005 Django 테스트. 외부 pykrx는 mock 처리하고, DB는 Django 테스트 DB(실제 Postgres)를 쓴다.

health, 시장 데이터 검증·upsert·GET 무외부호출, 단일 계좌·원장, 다음 거래일 시가·비용 올림·
현금 부족·반복 체결, root template 렌더링을 확인한다.
"""

import io
import sys
import types
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pandas as pd
from django.db import OperationalError
from django.test import Client, TestCase, override_settings

from trading import accounts, market_data, orders, portfolio
from trading.config import VirtualPolicyError, load_virtual_policy, market_data_configured
from trading.models import (
    CashLedgerEntry,
    DailyPrice,
    MarketDataCollectionRun,
    VirtualAccount,
    VirtualBuyOrder,
)

POLICY = dict(
    VIRTUAL_INITIAL_CASH_KRW="1000000",
    VIRTUAL_BUY_FEE_RATE="0.00015",
    VIRTUAL_SELL_FEE_RATE="0.00015",
    VIRTUAL_SELL_TAX_RATE="0",
    VIRTUAL_SLIPPAGE_BPS="0",
    VIRTUAL_TRADING_POLICY_VERSION="vtest",
    MARKET_DATA_PROVIDER="pykrx",
    # 테스트 전용 가짜 자격증명(실제 값 아님). 존재 여부 판정과 비노출 검증에만 쓴다.
    KRX_ID="test-krx-id",
    KRX_PW="test-krx-pw",
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
        # 계좌·주문이 생성되지 않았음(대시보드는 읽기 전용)
        self.assertEqual(VirtualAccount.objects.count(), 0)


# --- T-006 포트폴리오 계산 ---------------------------------------------------

def _account(initial=1_000_000):
    now = datetime(2024, 1, 1, tzinfo=timezone.utc)
    acc = VirtualAccount.objects.create(
        created_at=now, policy_version="v1", initial_cash_krw=initial,
        buy_fee_rate=0.00015, sell_fee_rate=0.00015, sell_tax_rate=0.0, slippage_bps=0, singleton=True,
    )
    CashLedgerEntry.objects.create(
        account=acc, created_at=now, entry_type="opening_balance", amount_krw=initial, description="개시",
    )
    return acc


def _fill(acc, ticker, qty, gross, fee, exec_date, decision_date=date(2024, 1, 2)):
    now = datetime(2024, 1, 5, tzinfo=timezone.utc)
    order = VirtualBuyOrder.objects.create(
        account=acc, ticker=ticker, quantity=qty, decision_trade_date=decision_date, created_at=now,
        status="filled", executed_at=now, execution_trade_date=exec_date,
        base_open_price_krw=gross // qty if qty else None, execution_price_krw=gross // qty if qty else None,
        gross_amount_krw=gross, fee_krw=fee, price_data_source="pykrx", price_adjusted=False,
        price_collection_run_id="r",
    )
    # 현금 원장도 함께 남겨 available_cash가 일관되게 한다.
    CashLedgerEntry.objects.create(
        account=acc, created_at=now, entry_type="buy_execution", amount_krw=-(gross + fee),
        description="체결", execution_order_id=order.id,
    )
    return order


def _price(ticker, d, close):
    DailyPrice.objects.create(
        ticker=ticker, trade_date=d, open_price=close, high_price=close, low_price=close,
        close_price=close, volume=1000, data_source="pykrx", adjusted=False,
        collected_at=datetime(2024, 1, 1, tzinfo=timezone.utc), collection_run_id="seed",
    )


class PortfolioCalcTests(TestCase):
    def test_single_holding_valuation(self):
        acc = _account(1_000_000)
        _fill(acc, "005930", qty=10, gross=100_000, fee=0, exec_date=date(2024, 1, 3))
        _price("005930", date(2024, 1, 3), 10_000)
        _price("005930", date(2024, 1, 5), 12_000)  # 최신 공통일
        p = portfolio.compute_portfolio(acc)
        self.assertTrue(p["valuation_available"])
        self.assertEqual(p["valuation_trade_date"], date(2024, 1, 5))
        h = p["holdings"][0]
        self.assertEqual((h["quantity"], h["cost_krw"], h["market_value_krw"], h["pnl_krw"]), (10, 100_000, 120_000, 20_000))
        self.assertEqual(h["return_pct"], "20.00")
        self.assertEqual(h["state"], "positive")
        s = p["summary"]
        self.assertEqual(s["available_cash_krw"], 900_000)
        self.assertEqual(s["total_assets_krw"], 1_020_000)
        self.assertEqual(s["total_pnl_krw"], 20_000)
        self.assertEqual(s["total_return_pct"], "2.00")

    def test_cost_includes_fee(self):
        acc = _account()
        _fill(acc, "005930", qty=10, gross=100_000, fee=50, exec_date=date(2024, 1, 3))
        _price("005930", date(2024, 1, 3), 10_000)
        p = portfolio.compute_portfolio(acc)
        self.assertEqual(p["holdings"][0]["cost_krw"], 100_050)

    def test_multiple_tickers_common_latest_date(self):
        acc = _account()
        _fill(acc, "005930", qty=1, gross=10_000, fee=0, exec_date=date(2024, 1, 3))
        _fill(acc, "000660", qty=1, gross=20_000, fee=0, exec_date=date(2024, 1, 4))
        _price("005930", date(2024, 1, 2), 9_000)   # 체결일 이전 공통 후보(제외돼야 함)
        _price("000660", date(2024, 1, 2), 19_000)
        _price("005930", date(2024, 1, 5), 11_000)
        _price("000660", date(2024, 1, 5), 21_000)
        p = portfolio.compute_portfolio(acc)
        self.assertEqual(p["valuation_trade_date"], date(2024, 1, 5))
        self.assertEqual(len(p["holdings"]), 2)

    def test_pending_and_rejected_excluded(self):
        acc = _account()
        _fill(acc, "005930", qty=1, gross=10_000, fee=0, exec_date=date(2024, 1, 3))
        _price("005930", date(2024, 1, 3), 10_000)
        VirtualBuyOrder.objects.create(
            account=acc, ticker="000660", quantity=5, decision_trade_date=date(2024, 1, 2),
            created_at=datetime(2024, 1, 5, tzinfo=timezone.utc), status="pending",
        )
        VirtualBuyOrder.objects.create(
            account=acc, ticker="035720", quantity=5, decision_trade_date=date(2024, 1, 2),
            created_at=datetime(2024, 1, 5, tzinfo=timezone.utc), status="rejected_insufficient_cash",
        )
        p = portfolio.compute_portfolio(acc)
        tickers = {h["ticker"] for h in p["holdings"]}
        self.assertEqual(tickers, {"005930"})

    def test_no_common_date_is_unavailable(self):
        acc = _account()
        _fill(acc, "005930", qty=1, gross=10_000, fee=0, exec_date=date(2024, 1, 3))
        _fill(acc, "000660", qty=1, gross=20_000, fee=0, exec_date=date(2024, 1, 3))
        _price("005930", date(2024, 1, 5), 11_000)
        _price("000660", date(2024, 1, 6), 21_000)  # 겹치는 공통일 없음
        p = portfolio.compute_portfolio(acc)
        self.assertFalse(p["valuation_available"])
        self.assertEqual(p["unavailable_reason"], portfolio.REASON_NO_COMMON_DATE)
        # 보유 수량·원가는 여전히 표시 가능
        self.assertEqual(len(p["holdings"]), 2)
        self.assertIsNone(p["summary"]["total_assets_krw"])

    def test_incomplete_fill_is_unavailable(self):
        acc = _account()
        # 체결일 누락(불완전)
        VirtualBuyOrder.objects.create(
            account=acc, ticker="005930", quantity=1, decision_trade_date=date(2024, 1, 2),
            created_at=datetime(2024, 1, 5, tzinfo=timezone.utc), status="filled",
            executed_at=datetime(2024, 1, 5, tzinfo=timezone.utc), execution_trade_date=None,
            gross_amount_krw=10_000, fee_krw=0,
        )
        p = portfolio.compute_portfolio(acc)
        self.assertFalse(p["valuation_available"])
        self.assertEqual(p["unavailable_reason"], portfolio.REASON_INCOMPLETE_FILL)

    def test_empty_holdings(self):
        acc = _account(1_000_000)
        p = portfolio.compute_portfolio(acc)
        self.assertTrue(p["empty"])
        self.assertIsNone(p["valuation_trade_date"])
        self.assertEqual(p["summary"]["total_assets_krw"], 1_000_000)
        self.assertEqual(p["summary"]["total_pnl_krw"], 0)

    def test_get_dashboard_is_read_only(self):
        acc = _account()
        _fill(acc, "005930", qty=1, gross=10_000, fee=0, exec_date=date(2024, 1, 3))
        _price("005930", date(2024, 1, 3), 10_000)
        before_orders = VirtualBuyOrder.objects.count()
        before_ledger = CashLedgerEntry.objects.count()
        before_prices = DailyPrice.objects.count()
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(VirtualBuyOrder.objects.count(), before_orders)
        self.assertEqual(CashLedgerEntry.objects.count(), before_ledger)
        self.assertEqual(DailyPrice.objects.count(), before_prices)


class PortfolioInvalidDataTests(TestCase):
    """비정상 filled 주문(0/음수 금액)·무효 계좌 데이터를 예외 없이 계산 불가로 처리한다."""

    def _price_005930(self):
        _price("005930", date(2024, 1, 3), 10_000)

    def test_zero_cost_is_unavailable_not_500(self):
        acc = _account()
        _fill(acc, "005930", qty=10, gross=0, fee=0, exec_date=date(2024, 1, 3))
        self._price_005930()
        p = portfolio.compute_portfolio(acc)  # ZeroDivisionError가 나면 실패
        self.assertFalse(p["valuation_available"])
        self.assertEqual(p["unavailable_reason"], portfolio.REASON_INCOMPLETE_FILL)

    def test_negative_gross_is_unavailable(self):
        acc = _account()
        _fill(acc, "005930", qty=10, gross=-100, fee=0, exec_date=date(2024, 1, 3))
        self._price_005930()
        p = portfolio.compute_portfolio(acc)
        self.assertFalse(p["valuation_available"])
        self.assertEqual(p["unavailable_reason"], portfolio.REASON_INCOMPLETE_FILL)

    def test_negative_fee_is_unavailable(self):
        acc = _account()
        _fill(acc, "005930", qty=10, gross=100_000, fee=-1, exec_date=date(2024, 1, 3))
        self._price_005930()
        p = portfolio.compute_portfolio(acc)
        self.assertFalse(p["valuation_available"])
        self.assertEqual(p["unavailable_reason"], portfolio.REASON_INCOMPLETE_FILL)

    def test_invalid_initial_cash_with_holdings(self):
        acc = _account(initial=0)
        _fill(acc, "005930", qty=1, gross=10_000, fee=0, exec_date=date(2024, 1, 3))
        self._price_005930()
        p = portfolio.compute_portfolio(acc)
        self.assertFalse(p["valuation_available"])
        self.assertEqual(p["unavailable_reason"], portfolio.REASON_INVALID_ACCOUNT_DATA)

    def test_invalid_initial_cash_empty(self):
        acc = _account(initial=0)
        p = portfolio.compute_portfolio(acc)
        self.assertTrue(p["empty"])
        self.assertFalse(p["valuation_available"])
        self.assertEqual(p["unavailable_reason"], portfolio.REASON_INVALID_ACCOUNT_DATA)

    def test_get_dashboard_200_and_read_only_on_bad_data(self):
        acc = _account()
        _fill(acc, "005930", qty=10, gross=0, fee=0, exec_date=date(2024, 1, 3))
        self._price_005930()
        before = (VirtualBuyOrder.objects.count(), CashLedgerEntry.objects.count(), DailyPrice.objects.count())
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            res = self.client.get("/")
        self.assertEqual(res.status_code, 200)  # 500이 아니어야 한다
        self.assertContains(res, "계산할 수 없습니다")
        after = (VirtualBuyOrder.objects.count(), CashLedgerEntry.objects.count(), DailyPrice.objects.count())
        self.assertEqual(before, after)


class DashboardRenderTests(TestCase):
    def test_no_account_notice(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "아직 가상 학습 계좌가 없습니다")

    def test_empty_holdings_notice(self):
        _account()
        res = self.client.get("/")
        self.assertContains(res, "보유 종목이 없습니다")

    def test_calculation_unavailable_notice(self):
        acc = _account()
        VirtualBuyOrder.objects.create(
            account=acc, ticker="005930", quantity=1, decision_trade_date=date(2024, 1, 2),
            created_at=datetime(2024, 1, 5, tzinfo=timezone.utc), status="filled",
            executed_at=datetime(2024, 1, 5, tzinfo=timezone.utc), execution_trade_date=None,
            gross_amount_krw=10_000, fee_krw=0,
        )
        res = self.client.get("/")
        self.assertContains(res, "계산할 수 없습니다")

    def test_db_error_notice(self):
        with patch("trading.views.VirtualAccount.objects.first", side_effect=Exception("db down")):
            res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "데이터베이스에 연결할 수 없습니다")


# --- T-007 시작·데이터 준비 화면 --------------------------------------------

@override_settings(**POLICY)
class SetupScreenTests(TestCase):
    def test_get_setup_is_read_only(self):
        before = (
            VirtualAccount.objects.count(), VirtualBuyOrder.objects.count(),
            CashLedgerEntry.objects.count(), DailyPrice.objects.count(),
            MarketDataCollectionRun.objects.count(),
        )
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            res = self.client.get("/setup")
        self.assertEqual(res.status_code, 200)
        after = (
            VirtualAccount.objects.count(), VirtualBuyOrder.objects.count(),
            CashLedgerEntry.objects.count(), DailyPrice.objects.count(),
            MarketDataCollectionRun.objects.count(),
        )
        self.assertEqual(before, after)

    def test_get_setup_no_account_shows_start_cash_and_form(self):
        res = self.client.get("/setup")
        self.assertContains(res, "가상 학습 계좌 시작")   # 최초 생성 form 버튼
        self.assertContains(res, "1000000")             # 정책 설정의 시작 현금(하드코딩 아님)
        self.assertContains(res, "csrfmiddlewaretoken")  # CSRF 보호 form

    def test_post_initialize_creates_account_and_redirects_303(self):
        res = self.client.post("/setup/account/initialize")
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res["Location"], "/setup")
        self.assertEqual(VirtualAccount.objects.count(), 1)
        self.assertEqual(CashLedgerEntry.objects.count(), 1)

    def test_repeat_initialize_does_not_reset(self):
        self.client.post("/setup/account/initialize")
        self.client.post("/setup/account/initialize")
        self.assertEqual(VirtualAccount.objects.count(), 1)
        self.assertEqual(CashLedgerEntry.objects.count(), 1)

    def test_get_setup_with_account_hides_reset(self):
        self.client.post("/setup/account/initialize")
        res = self.client.get("/setup")
        self.assertContains(res, "최초 가상 현금")
        self.assertContains(res, "재설정")               # "재설정하지 않습니다" 안내
        self.assertNotContains(res, "가상 학습 계좌 시작")  # 생성 버튼 없음

    @override_settings(VIRTUAL_INITIAL_CASH_KRW="0")
    def test_policy_error_hides_button(self):
        res = self.client.get("/setup")
        self.assertContains(res, "정책 설정이 유효하지 않아")
        self.assertNotContains(res, "가상 학습 계좌 시작")

    def test_csrf_protected_forms(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post("/setup/account/initialize").status_code, 403)
        self.assertEqual(
            c.post("/setup/market-data/collect", {"ticker": "005930", "from_date": "2024-01-02", "to_date": "2024-01-05"}).status_code,
            403,
        )

    def test_collect_bad_input_is_422_without_external_call(self):
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            bad_ticker = self.client.post("/setup/market-data/collect", {"ticker": "12", "from_date": "2024-01-02", "to_date": "2024-01-05"})
            reversed_range = self.client.post("/setup/market-data/collect", {"ticker": "005930", "from_date": "2024-01-05", "to_date": "2024-01-02"})
            bad_date = self.client.post("/setup/market-data/collect", {"ticker": "005930", "from_date": "nope", "to_date": "2024-01-05"})
        self.assertEqual(bad_ticker.status_code, 422)
        self.assertEqual(reversed_range.status_code, 422)
        self.assertEqual(bad_date.status_code, 422)
        self.assertEqual(MarketDataCollectionRun.objects.count(), 0)

    def test_collect_success_prg_and_result_display(self):
        df = _df([("2024-01-02", 100, 110, 90, 105, 1000)])
        with patch("trading.market_data.fetch_ohlcv", return_value=df):
            res = self.client.post("/setup/market-data/collect", {"ticker": "005930", "from_date": "2024-01-02", "to_date": "2024-01-05"})
        self.assertEqual(res.status_code, 303)
        self.assertTrue(res["Location"].startswith("/setup?collection_run="))
        run = MarketDataCollectionRun.objects.get()
        # PRG 뒤 GET: 외부 수집 없이 실행 기록을 표시한다.
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("GET이 외부 수집")):
            result = self.client.get(res["Location"])
        self.assertEqual(result.status_code, 200)
        self.assertContains(result, "수집 결과")
        self.assertContains(result, run.status)
        self.assertContains(result, "pykrx")

    @override_settings(MARKET_DATA_PROVIDER="")
    def test_collect_config_error_is_safe(self):
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            res = self.client.post("/setup/market-data/collect", {"ticker": "005930", "from_date": "2024-01-02", "to_date": "2024-01-05"})
        self.assertEqual(res.status_code, 503)
        self.assertContains(res, "pykrx", status_code=503)
        self.assertEqual(MarketDataCollectionRun.objects.count(), 0)

    def test_collect_fetch_failure_is_safe(self):
        with patch("trading.market_data.fetch_ohlcv", side_effect=RuntimeError("network down")):
            res = self.client.post("/setup/market-data/collect", {"ticker": "005930", "from_date": "2024-01-02", "to_date": "2024-01-05"})
        self.assertEqual(res.status_code, 502)
        self.assertNotContains(res, "network down", status_code=502)

    def test_unknown_collection_run_is_safe(self):
        res = self.client.get("/setup?collection_run=does-not-exist")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "찾을 수 없습니다")

    # --- P1: DB 오류는 500·예외 노출이 아니라 안전한 503 안내 ---

    def test_get_setup_db_error_is_safe_503(self):
        before = (VirtualAccount.objects.count(), CashLedgerEntry.objects.count(),
                  DailyPrice.objects.count(), MarketDataCollectionRun.objects.count())
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")), \
             patch("trading.views.MarketDataCollectionRun.objects.filter",
                   side_effect=OperationalError("db outage secret-like-detail")):
            res = self.client.get("/setup?collection_run=abc123")
        self.assertEqual(res.status_code, 503)
        self.assertNotContains(res, "secret-like-detail", status_code=503)
        self.assertContains(res, "데이터베이스에 연결할 수 없습니다", status_code=503)
        after = (VirtualAccount.objects.count(), CashLedgerEntry.objects.count(),
                 DailyPrice.objects.count(), MarketDataCollectionRun.objects.count())
        self.assertEqual(before, after)

    def test_setup_initialize_db_error_is_safe_503(self):
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")), \
             patch("trading.views.accounts.initialize_account",
                   side_effect=OperationalError("db outage secret-like-detail")):
            res = self.client.post("/setup/account/initialize")
        self.assertEqual(res.status_code, 503)
        self.assertNotContains(res, "secret-like-detail", status_code=503)
        self.assertContains(res, "데이터베이스에 연결할 수 없습니다", status_code=503)
        self.assertEqual(VirtualAccount.objects.count(), 0)
        self.assertEqual(CashLedgerEntry.objects.count(), 0)

    def test_setup_collect_db_error_is_safe_503(self):
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")), \
             patch("trading.views.market_data.collect_daily_prices",
                   side_effect=OperationalError("db outage secret-like-detail")):
            res = self.client.post("/setup/market-data/collect",
                                   {"ticker": "005930", "from_date": "2024-01-02", "to_date": "2024-01-05"})
        self.assertEqual(res.status_code, 503)
        self.assertNotContains(res, "secret-like-detail", status_code=503)
        self.assertContains(res, "데이터베이스에 연결할 수 없습니다", status_code=503)
        self.assertEqual(MarketDataCollectionRun.objects.count(), 0)
        self.assertEqual(DailyPrice.objects.count(), 0)


# --- T-008 KRX 인증 기반 pykrx 수집 --------------------------------------------

_FAKE_UPSTREAM = "FAKEID123 FAKEPW456 raw-response-secret"


def _fake_pykrx(get_market_ohlcv):
    """가짜 pykrx 패키지. from pykrx import stock가 이 stock을 얻게 한다."""
    stock = types.SimpleNamespace(get_market_ohlcv=get_market_ohlcv)
    pkg = types.ModuleType("pykrx")
    pkg.stock = stock
    return {"pykrx": pkg, "pykrx.stock": stock}


@override_settings(**POLICY)
class KrxAuthConfigTests(TestCase):
    def _assert_blocked(self):
        # 게이트가 fetch(=pykrx import) 이전에 막는지 확인한다.
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("pykrx import/호출")):
            res = self.client.post(
                "/setup/market-data/collect",
                {"ticker": "005930", "from_date": "2024-01-02", "to_date": "2024-01-05"},
            )
        self.assertEqual(res.status_code, 503)
        self.assertEqual(MarketDataCollectionRun.objects.count(), 0)
        self.assertEqual(DailyPrice.objects.count(), 0)

    @override_settings(KRX_ID="")
    def test_missing_krx_id_blocks_503_without_import(self):
        self.assertFalse(market_data_configured())
        self._assert_blocked()

    @override_settings(KRX_PW="")
    def test_missing_krx_pw_blocks_503_without_import(self):
        self.assertFalse(market_data_configured())
        self._assert_blocked()

    @override_settings(MARKET_DATA_PROVIDER="other")
    def test_provider_not_pykrx_blocks_503(self):
        self.assertFalse(market_data_configured())
        self._assert_blocked()

    def test_full_config_is_configured(self):
        self.assertTrue(market_data_configured())

    def test_config_never_returns_credential_values(self):
        # 판정 함수는 불리언만 반환한다. 값이 문자열로 새지 않는다.
        self.assertIn(market_data_configured(), (True, False))
        self.assertIsInstance(market_data_configured(), bool)


@override_settings(**POLICY)
class KrxUpstreamNonLeakTests(TestCase):
    def test_upstream_stdout_and_exception_not_leaked_on_failure(self):
        def boom(*a, **k):
            print(_FAKE_UPSTREAM)  # upstream이 표준 출력에 로그인 정보를 씀
            raise RuntimeError("upstream error " + _FAKE_UPSTREAM)

        cap = io.StringIO()
        with patch.dict(sys.modules, _fake_pykrx(boom)), redirect_stdout(cap), \
             self.assertLogs("jumong.market_data", level="WARNING") as logs:
            res = self.client.post(
                "/setup/market-data/collect",
                {"ticker": "005930", "from_date": "2024-01-02", "to_date": "2024-01-05"},
            )
        self.assertEqual(res.status_code, 502)
        # 응답·로그·실행 기록·가드 외부 표준 출력 어디에도 upstream 원문이 없다.
        self.assertNotContains(res, _FAKE_UPSTREAM, status_code=502)
        self.assertNotIn(_FAKE_UPSTREAM, "\n".join(logs.output))
        self.assertNotIn(_FAKE_UPSTREAM, cap.getvalue())
        run = MarketDataCollectionRun.objects.get()
        self.assertEqual(run.status, "failed")
        self.assertNotIn(_FAKE_UPSTREAM, run.failure_reason or "")

    def test_upstream_stdout_not_leaked_on_success(self):
        def ok(*a, **k):
            print(_FAKE_UPSTREAM)  # 성공 경로에서도 표준 출력에 씀
            return _df([("2024-01-02", 100, 110, 90, 105, 1000)])

        cap = io.StringIO()
        with patch.dict(sys.modules, _fake_pykrx(ok)), redirect_stdout(cap):
            result = market_data.collect_daily_prices("005930", date(2024, 1, 2), date(2024, 1, 5))
        self.assertEqual(result["status"], "success")
        self.assertNotIn(_FAKE_UPSTREAM, cap.getvalue())   # 가드가 캡처해 실제 stdout에 안 감
        self.assertNotIn(_FAKE_UPSTREAM, str(result))
        run = MarketDataCollectionRun.objects.get(run_id=result["run_id"])
        self.assertEqual(run.status, "success")
        self.assertNotIn(_FAKE_UPSTREAM, run.raw_hash)


# --- T-009 화면 render 계약 (먼저 실패 → template/CSS 최소 변경으로 통과) -------

@override_settings(**POLICY)
class UiRefreshRenderTests(TestCase):
    def test_dashboard_has_common_nav_and_identity(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "가상 학습 투자 장부")
        self.assertContains(res, 'href="/setup"')  # 공통 navigation
        self.assertContains(res, 'href="/"')

    def test_setup_has_common_nav_and_flow(self):
        res = self.client.get("/setup")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "가상 학습 투자 장부")
        self.assertContains(res, 'href="/setup"')
        self.assertContains(res, 'href="/"')
        self.assertContains(res, "대시보드 확인")  # 3단계 흐름의 마지막 단계 안내

    def test_dashboard_still_read_only_on_render(self):
        # UI 변경이 읽기 전용 보장을 깨지 않는다.
        before = (VirtualAccount.objects.count(), VirtualBuyOrder.objects.count(),
                  CashLedgerEntry.objects.count(), DailyPrice.objects.count())
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            self.client.get("/")
            self.client.get("/setup")
        after = (VirtualAccount.objects.count(), VirtualBuyOrder.objects.count(),
                 CashLedgerEntry.objects.count(), DailyPrice.objects.count())
        self.assertEqual(before, after)
