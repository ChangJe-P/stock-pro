"""기존 PostgreSQL 테이블(T-002~T-004)에 호환 타입으로 매핑한 Django model.

- 모든 KRW 금액은 BigIntegerField, 수집 제외 사유는 JSONField, 수수료율은 기존
  DOUBLE PRECISION과 호환되는 FloatField.
- execution_order_id, collection_run_id는 현재 DB에서 외래키가 아니므로 그대로 정수/문자열로 둔다.
- 스키마는 migration이 관리한다(요청 처리 중 DDL 없음).
"""

from django.db import models


class MarketDataCollectionRun(models.Model):
    run_id = models.CharField(primary_key=True, max_length=64)
    data_source = models.TextField()
    ticker = models.TextField()
    from_date = models.DateField()
    to_date = models.DateField()
    collected_at = models.DateTimeField()
    raw_hash = models.TextField()
    returned_rows = models.IntegerField()
    inserted_rows = models.IntegerField()
    updated_rows = models.IntegerField()
    excluded_rows = models.IntegerField()
    status = models.TextField()
    failure_reason = models.TextField(null=True, blank=True)
    excluded_reasons = models.JSONField(default=dict)

    class Meta:
        db_table = "market_data_collection_runs"


class DailyPrice(models.Model):
    ticker = models.TextField()
    trade_date = models.DateField()
    open_price = models.BigIntegerField()
    high_price = models.BigIntegerField()
    low_price = models.BigIntegerField()
    close_price = models.BigIntegerField()
    volume = models.BigIntegerField()
    data_source = models.TextField()
    adjusted = models.BooleanField()
    collected_at = models.DateTimeField()
    collection_run_id = models.TextField()

    class Meta:
        db_table = "daily_prices"
        constraints = [
            models.UniqueConstraint(fields=["ticker", "trade_date"], name="daily_prices_ticker_trade_date_key"),
        ]


class VirtualAccount(models.Model):
    created_at = models.DateTimeField()
    policy_version = models.TextField()
    initial_cash_krw = models.BigIntegerField()
    buy_fee_rate = models.FloatField()
    sell_fee_rate = models.FloatField()
    sell_tax_rate = models.FloatField()
    slippage_bps = models.IntegerField()
    # 단일 로컬 계좌만 존재하도록 DB 수준에서 보장(항상 True인 유일 컬럼).
    singleton = models.BooleanField(default=True, unique=True)

    class Meta:
        db_table = "virtual_accounts"
        constraints = [
            models.CheckConstraint(condition=models.Q(singleton=True), name="virtual_accounts_singleton_true"),
        ]


class CashLedgerEntry(models.Model):
    account = models.ForeignKey(
        VirtualAccount, on_delete=models.DO_NOTHING, db_column="account_id", related_name="ledger_entries"
    )
    created_at = models.DateTimeField()
    entry_type = models.TextField()
    amount_krw = models.BigIntegerField()
    description = models.TextField()
    # 체결 주문 연결(외래키로 바꾸지 않는다). 주문당 원장 1행을 유일 인덱스로 보장.
    execution_order_id = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "cash_ledger_entries"
        constraints = [
            models.UniqueConstraint(fields=["execution_order_id"], name="uq_cash_ledger_execution_order"),
        ]


class VirtualBuyOrder(models.Model):
    account = models.ForeignKey(
        VirtualAccount, on_delete=models.DO_NOTHING, db_column="account_id", related_name="buy_orders"
    )
    ticker = models.TextField()
    quantity = models.BigIntegerField()
    decision_trade_date = models.DateField()
    created_at = models.DateTimeField()
    status = models.TextField(default="pending")
    executed_at = models.DateTimeField(null=True, blank=True)
    execution_trade_date = models.DateField(null=True, blank=True)
    base_open_price_krw = models.BigIntegerField(null=True, blank=True)
    execution_price_krw = models.BigIntegerField(null=True, blank=True)
    gross_amount_krw = models.BigIntegerField(null=True, blank=True)
    fee_krw = models.BigIntegerField(null=True, blank=True)
    price_data_source = models.TextField(null=True, blank=True)
    price_adjusted = models.BooleanField(null=True, blank=True)
    price_collection_run_id = models.TextField(null=True, blank=True)
    termination_reason = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "virtual_buy_orders"
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name="virtual_buy_orders_quantity_positive"),
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "filled", "rejected_insufficient_cash"]),
                name="virtual_buy_orders_status_valid",
            ),
        ]
