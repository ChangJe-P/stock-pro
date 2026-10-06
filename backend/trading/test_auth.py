"""T-010 인증·사용자별 격리·legacy 연결·CSRF·수집 권한·migration 보존 테스트.

실제 Google OAuth 네트워크·실제 자격증명은 사용하지 않는다(pykrx도 mock). Google Client ID·
Secret이 없는 환경에서의 안전한 동작을 확인한다.
"""

from datetime import date, datetime, timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase, override_settings

from trading import accounts, orders, ownership
from trading.models import CashLedgerEntry, DailyPrice, VirtualAccount, VirtualBuyOrder

SETTINGS = dict(
    VIRTUAL_INITIAL_CASH_KRW="1000000",
    VIRTUAL_BUY_FEE_RATE="0.00015",
    VIRTUAL_SELL_FEE_RATE="0.00015",
    VIRTUAL_SELL_TAX_RATE="0",
    VIRTUAL_SLIPPAGE_BPS="0",
    VIRTUAL_TRADING_POLICY_VERSION="vtest",
    MARKET_DATA_PROVIDER="pykrx",
    KRX_ID="fake-id",
    KRX_PW="fake-pw",
    INITIAL_OWNER_GOOGLE_EMAIL="owner@example.com",
)


def _user(email, username=None):
    return User.objects.create_user(username=username or email, email=email, password="x")


def _seed_price(ticker, d, open_p, close_p=None):
    DailyPrice.objects.create(
        ticker=ticker, trade_date=d, open_price=open_p, high_price=open_p + 50, low_price=open_p - 50,
        close_price=close_p if close_p is not None else open_p, volume=1000, data_source="pykrx",
        adjusted=False, collected_at=datetime(2024, 1, 1, tzinfo=timezone.utc), collection_run_id="seed",
    )


# --- Task 1: OAuth 설정·인증 경계 ---------------------------------------------

@override_settings(GOOGLE_OAUTH_CLIENT_ID="", GOOGLE_OAUTH_CLIENT_SECRET="")
class LoginScreenTests(TestCase):
    def test_login_safe_when_oauth_missing(self):
        res = self.client.get("/login/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "설정되지 않았습니다")
        # 비밀값·provider 시작 URL을 렌더링하지 않는다.
        self.assertNotContains(res, "accounts/google/login")

    def test_unauthenticated_html_redirects_to_login(self):
        for path in ("/", "/setup"):
            res = self.client.get(path)
            self.assertEqual(res.status_code, 302)
            self.assertTrue(res["Location"].startswith("/login/"))

    def test_unauthenticated_json_api_returns_401(self):
        self.assertEqual(self.client.get("/virtual-account").status_code, 401)
        self.assertEqual(self.client.get("/virtual-account").json()["detail"], "로그인이 필요합니다.")
        self.assertEqual(self.client.get("/virtual-orders").status_code, 401)
        res = self.client.post("/virtual-orders", data="{}", content_type="application/json")
        self.assertEqual(res.status_code, 401)
        # 비로그인 요청은 계좌를 만들지 않는다.
        self.assertEqual(VirtualAccount.objects.count(), 0)

    def test_health_is_public(self):
        self.assertEqual(self.client.get("/health").status_code, 200)


# --- Task 2·3: 사용자 소유·A/B 격리 -------------------------------------------

@override_settings(**SETTINGS)
class AccountOwnershipTests(TestCase):
    def test_each_user_gets_own_single_account(self):
        a, b = _user("a@example.com"), _user("b@example.com")
        ra = accounts.initialize_account(a)
        rb = accounts.initialize_account(b)
        self.assertNotEqual(ra["account_id"], rb["account_id"])
        # 반복 초기화는 재설정·행 추가 없음(멱등).
        again = accounts.initialize_account(a)
        self.assertEqual(again["account_id"], ra["account_id"])
        self.assertEqual(VirtualAccount.objects.filter(owner=a).count(), 1)
        self.assertEqual(CashLedgerEntry.objects.filter(account__owner=a).count(), 1)

    def test_order_isolation_and_other_order_is_404(self):
        a, b = _user("a@example.com"), _user("b@example.com")
        accounts.initialize_account(a)
        accounts.initialize_account(b)
        _seed_price("005930", date(2024, 1, 2), 900)
        _seed_price("005930", date(2024, 1, 3), 1000)
        b_order = orders.create_order(b, "005930", 1, date(2024, 1, 2))["order_id"]
        # A는 B의 주문을 조회·체결할 수 없다(존재를 밝히지 않는 404).
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            from trading.errors import ApiError
            with self.assertRaises(ApiError) as ctx:
                orders.execute_order(a, b_order)
            self.assertEqual(ctx.exception.status_code, 404)
        # A의 주문 목록에 B의 주문이 없다.
        self.assertEqual(orders.list_orders(a)["orders"], [])
        # B의 주문은 그대로다.
        self.assertEqual(VirtualBuyOrder.objects.get(id=b_order).status, "pending")

    def test_next_day_open_execution_after_user_scoping(self):
        a = _user("a@example.com")
        accounts.initialize_account(a)
        _seed_price("005930", date(2024, 1, 2), 900)   # 결정일(같은 날, 사용 금지)
        _seed_price("005930", date(2024, 1, 3), 1000)  # 다음 거래일 시가
        oid = orders.create_order(a, "005930", 2, date(2024, 1, 2))["order_id"]
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            res = orders.execute_order(a, oid)
        self.assertEqual(res["status"], "filled")
        self.assertEqual(res["execution_trade_date"], date(2024, 1, 3))
        self.assertEqual(res["base_open_price_krw"], 1000)
        # 반복 체결은 기존 결과만 반환(중복 원장 없음).
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            orders.execute_order(a, oid)
        self.assertEqual(CashLedgerEntry.objects.filter(entry_type="buy_execution").count(), 1)

    def test_dashboard_shows_only_own_data(self):
        a, b = _user("a@example.com"), _user("b@example.com")
        accounts.initialize_account(a)
        accounts.initialize_account(b)
        _seed_price("005930", date(2024, 1, 2), 900)
        orders.create_order(b, "005930", 1, date(2024, 1, 2))  # B의 주문
        self.client.force_login(a)
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        # A의 대시보드에는 B의 종목/주문이 없다.
        self.assertNotContains(res, "005930")


# --- legacy 계좌 명시적 1회 연결 ----------------------------------------------

@override_settings(**SETTINGS)
class LegacyClaimTests(TestCase):
    def _make_legacy(self):
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        acc = VirtualAccount.objects.create(
            owner=None, created_at=now, policy_version="v1", initial_cash_krw=10_000_000,
            buy_fee_rate=0.00015, sell_fee_rate=0.00015, sell_tax_rate=0.0, slippage_bps=0,
        )
        CashLedgerEntry.objects.create(
            account=acc, created_at=now, entry_type="opening_balance", amount_krw=10_000_000, description="개시",
        )
        VirtualBuyOrder.objects.create(
            account=acc, ticker="005930", quantity=1, decision_trade_date=date(2024, 1, 2),
            created_at=now, status="pending",
        )
        return acc

    def test_owner_can_claim_once_and_rows_preserved(self):
        legacy = self._make_legacy()
        owner = _user("owner@example.com")
        self.assertTrue(ownership.can_claim_legacy(owner))
        claimed = ownership.claim_legacy_account(owner)
        self.assertEqual(claimed.id, legacy.id)
        self.assertEqual(claimed.owner_id, owner.id)
        # 반복 연결은 멱등(계좌·행 추가 없음).
        again = ownership.claim_legacy_account(owner)
        self.assertEqual(again.id, legacy.id)
        self.assertEqual(VirtualAccount.objects.count(), 1)
        self.assertEqual(CashLedgerEntry.objects.filter(account=legacy).count(), 1)
        self.assertEqual(VirtualBuyOrder.objects.filter(account=legacy).count(), 1)

    def test_non_owner_cannot_claim_or_see_legacy(self):
        legacy = self._make_legacy()
        other = _user("other@example.com")
        self.assertFalse(ownership.can_claim_legacy(other))
        from trading.errors import ApiError
        with self.assertRaises(ApiError) as ctx:
            ownership.claim_legacy_account(other)
        self.assertEqual(ctx.exception.status_code, 403)
        legacy.refresh_from_db()
        self.assertIsNone(legacy.owner_id)
        # 다른 사용자의 대시보드·setup에 legacy 데이터가 보이지 않는다.
        self.client.force_login(other)
        self.assertNotContains(self.client.get("/"), "005930")

    def test_claim_via_post_is_prg(self):
        self._make_legacy()
        owner = _user("owner@example.com")
        self.client.force_login(owner)
        res = self.client.post("/setup/legacy-account/claim")
        self.assertEqual(res.status_code, 303)
        self.assertEqual(res["Location"], "/")
        self.assertEqual(VirtualAccount.objects.filter(owner=owner).count(), 1)


# --- CSRF·수집 권한 -----------------------------------------------------------

@override_settings(**SETTINGS)
class CsrfAndCollectPermissionTests(TestCase):
    def test_csrf_required_on_user_post(self):
        user = _user("owner@example.com")
        c = Client(enforce_csrf_checks=True)
        c.force_login(user)
        self.assertEqual(c.post("/setup/account/initialize").status_code, 403)
        # JSON API도 CSRF 보호(csrf_exempt 제거): 로그인 사용자는 토큰 없는 POST가 403.
        self.assertEqual(
            c.post("/virtual-account/initialize", data="{}", content_type="application/json").status_code, 403
        )
        self.assertEqual(
            c.post("/virtual-orders", data="{}", content_type="application/json").status_code, 403
        )

    def test_unauth_json_post_is_401_even_under_csrf_enforcement(self):
        # CSRF를 강제한 client로도 비로그인 JSON POST는 CSRF 403이 아니라 정확히 401 JSON이어야 한다.
        c = Client(enforce_csrf_checks=True)  # 로그인하지 않음
        for path in ("/virtual-orders", "/virtual-account/initialize", "/market-data/daily-prices/collect"):
            res = c.post(path, data="{}", content_type="application/json")
            self.assertEqual(res.status_code, 401, path)
            self.assertEqual(res.json()["detail"], "로그인이 필요합니다.", path)
        # 비로그인 요청은 계좌·수집 기록을 만들지 않는다.
        from trading.models import MarketDataCollectionRun
        self.assertEqual(VirtualAccount.objects.count(), 0)
        self.assertEqual(MarketDataCollectionRun.objects.count(), 0)

    def test_non_operator_collect_is_403_without_fetch(self):
        user = _user("not-owner@example.com")  # 운영자 아님
        self.client.force_login(user)
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("fetch 호출")):
            html = self.client.post(
                "/setup/market-data/collect",
                {"ticker": "005930", "from_date": "2024-01-02", "to_date": "2024-01-03"},
            )
            jsonr = self.client.post(
                "/market-data/daily-prices/collect",
                data='{"ticker":"005930","from_date":"2024-01-02","to_date":"2024-01-03"}',
                content_type="application/json",
            )
        self.assertEqual(html.status_code, 403)
        self.assertEqual(jsonr.status_code, 403)
        from trading.models import MarketDataCollectionRun
        self.assertEqual(MarketDataCollectionRun.objects.count(), 0)

    def test_logged_in_user_can_read_public_prices(self):
        user = _user("not-owner@example.com")
        _seed_price("005930", date(2024, 1, 2), 900)
        self.client.force_login(user)
        with patch("trading.market_data.fetch_ohlcv", side_effect=AssertionError("외부 수집 호출")):
            res = self.client.get("/market-data/daily-prices?ticker=005930&from_date=2024-01-01&to_date=2024-01-05")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.json()["rows"]), 1)


# --- legacy migration 보존(0001 → 0002) ---------------------------------------

class LegacyMigrationTests(TransactionTestCase):
    def test_existing_single_account_rows_preserved_after_0002(self):
        executor = MigrationExecutor(connection)
        executor.migrate([("trading", "0001_initial")])
        old_apps = executor.loader.project_state([("trading", "0001_initial")]).apps
        VA = old_apps.get_model("trading", "VirtualAccount")
        CLE = old_apps.get_model("trading", "CashLedgerEntry")
        VBO = old_apps.get_model("trading", "VirtualBuyOrder")
        now = datetime(2024, 1, 1, tzinfo=timezone.utc)
        acc = VA.objects.create(
            created_at=now, policy_version="v1", initial_cash_krw=10_000_000, buy_fee_rate=0.00015,
            sell_fee_rate=0.00015, sell_tax_rate=0.0, slippage_bps=0, singleton=True,
        )
        CLE.objects.create(account_id=acc.id, created_at=now, entry_type="opening_balance",
                           amount_krw=10_000_000, description="개시")
        VBO.objects.create(account_id=acc.id, ticker="005930", quantity=1,
                           decision_trade_date=date(2024, 1, 2), created_at=now, status="pending")
        acc_id = acc.id

        # 0002 적용: 기존 행 보존, owner만 비어 있어야 한다.
        executor.loader.build_graph()
        executor.migrate([("trading", "0002_user_owned_virtual_accounts")])
        new_apps = executor.loader.project_state([("trading", "0002_user_owned_virtual_accounts")]).apps
        VA2 = new_apps.get_model("trading", "VirtualAccount")
        CLE2 = new_apps.get_model("trading", "CashLedgerEntry")
        VBO2 = new_apps.get_model("trading", "VirtualBuyOrder")
        acc2 = VA2.objects.get(id=acc_id)
        self.assertIsNone(acc2.owner_id)
        self.assertEqual(VA2.objects.count(), 1)
        self.assertEqual(CLE2.objects.filter(account_id=acc_id).count(), 1)
        self.assertEqual(VBO2.objects.filter(account_id=acc_id).count(), 1)

    def tearDown(self):
        # 다른 테스트를 위해 최신 마이그레이션 상태로 되돌린다.
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate(executor.loader.graph.leaf_nodes())
