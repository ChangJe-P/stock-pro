# T-005: FastAPI/psycopg 시절 스키마를 Django state로 채택하는 첫 migration.
# SeparateDatabaseAndState로 (1) Django model state를 등록하고,
# (2) 실제 DDL은 재실행 안전한 idempotent SQL로 처리한다.
#   - 새 DB: CREATE TABLE IF NOT EXISTS 등으로 기존 스키마와 호환되는 테이블을 만든다.
#   - 기존 DB: 모두 no-op이라 기존 행을 보존하고 state만 등록한다.
# 기존 테이블을 DROP/TRUNCATE하지 않는다.

import django.db.models.deletion
from django.db import migrations, models

# 기존 T-002~T-004가 만든 스키마와 동일한 idempotent DDL.
_ADOPT_SQL = """
CREATE TABLE IF NOT EXISTS market_data_collection_runs (
    run_id TEXT PRIMARY KEY,
    data_source TEXT NOT NULL,
    ticker TEXT NOT NULL,
    from_date DATE NOT NULL,
    to_date DATE NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    raw_hash TEXT NOT NULL,
    returned_rows INTEGER NOT NULL,
    inserted_rows INTEGER NOT NULL,
    updated_rows INTEGER NOT NULL,
    excluded_rows INTEGER NOT NULL,
    status TEXT NOT NULL,
    failure_reason TEXT,
    excluded_reasons JSONB NOT NULL DEFAULT '{}'::jsonb
);
ALTER TABLE market_data_collection_runs
    ADD COLUMN IF NOT EXISTS excluded_reasons JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE TABLE IF NOT EXISTS daily_prices (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open_price BIGINT NOT NULL,
    high_price BIGINT NOT NULL,
    low_price BIGINT NOT NULL,
    close_price BIGINT NOT NULL,
    volume BIGINT NOT NULL,
    data_source TEXT NOT NULL,
    adjusted BOOLEAN NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    collection_run_id TEXT NOT NULL,
    UNIQUE (ticker, trade_date)
);

CREATE TABLE IF NOT EXISTS virtual_accounts (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    policy_version TEXT NOT NULL,
    initial_cash_krw BIGINT NOT NULL,
    buy_fee_rate DOUBLE PRECISION NOT NULL,
    sell_fee_rate DOUBLE PRECISION NOT NULL,
    sell_tax_rate DOUBLE PRECISION NOT NULL,
    slippage_bps INTEGER NOT NULL,
    singleton BOOLEAN NOT NULL DEFAULT TRUE UNIQUE CHECK (singleton)
);

CREATE TABLE IF NOT EXISTS cash_ledger_entries (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES virtual_accounts(id),
    created_at TIMESTAMPTZ NOT NULL,
    entry_type TEXT NOT NULL,
    amount_krw BIGINT NOT NULL,
    description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS virtual_buy_orders (
    id BIGSERIAL PRIMARY KEY,
    account_id BIGINT NOT NULL REFERENCES virtual_accounts(id),
    ticker TEXT NOT NULL,
    quantity BIGINT NOT NULL CHECK (quantity > 0),
    decision_trade_date DATE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'filled', 'rejected_insufficient_cash')),
    executed_at TIMESTAMPTZ,
    execution_trade_date DATE,
    base_open_price_krw BIGINT,
    execution_price_krw BIGINT,
    gross_amount_krw BIGINT,
    fee_krw BIGINT,
    price_data_source TEXT,
    price_adjusted BOOLEAN,
    price_collection_run_id TEXT,
    termination_reason TEXT
);

ALTER TABLE cash_ledger_entries ADD COLUMN IF NOT EXISTS execution_order_id BIGINT;
CREATE UNIQUE INDEX IF NOT EXISTS uq_cash_ledger_execution_order
    ON cash_ledger_entries (execution_order_id);
"""

_STATE_OPERATIONS = [
    migrations.CreateModel(
        name="MarketDataCollectionRun",
        fields=[
            ("run_id", models.CharField(max_length=64, primary_key=True, serialize=False)),
            ("data_source", models.TextField()),
            ("ticker", models.TextField()),
            ("from_date", models.DateField()),
            ("to_date", models.DateField()),
            ("collected_at", models.DateTimeField()),
            ("raw_hash", models.TextField()),
            ("returned_rows", models.IntegerField()),
            ("inserted_rows", models.IntegerField()),
            ("updated_rows", models.IntegerField()),
            ("excluded_rows", models.IntegerField()),
            ("status", models.TextField()),
            ("failure_reason", models.TextField(blank=True, null=True)),
            ("excluded_reasons", models.JSONField(default=dict)),
        ],
        options={"db_table": "market_data_collection_runs"},
    ),
    migrations.CreateModel(
        name="DailyPrice",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("ticker", models.TextField()),
            ("trade_date", models.DateField()),
            ("open_price", models.BigIntegerField()),
            ("high_price", models.BigIntegerField()),
            ("low_price", models.BigIntegerField()),
            ("close_price", models.BigIntegerField()),
            ("volume", models.BigIntegerField()),
            ("data_source", models.TextField()),
            ("adjusted", models.BooleanField()),
            ("collected_at", models.DateTimeField()),
            ("collection_run_id", models.TextField()),
        ],
        options={
            "db_table": "daily_prices",
            "constraints": [
                models.UniqueConstraint(fields=("ticker", "trade_date"), name="daily_prices_ticker_trade_date_key")
            ],
        },
    ),
    migrations.CreateModel(
        name="VirtualAccount",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField()),
            ("policy_version", models.TextField()),
            ("initial_cash_krw", models.BigIntegerField()),
            ("buy_fee_rate", models.FloatField()),
            ("sell_fee_rate", models.FloatField()),
            ("sell_tax_rate", models.FloatField()),
            ("slippage_bps", models.IntegerField()),
            ("singleton", models.BooleanField(default=True, unique=True)),
        ],
        options={
            "db_table": "virtual_accounts",
            "constraints": [
                models.CheckConstraint(condition=models.Q(("singleton", True)), name="virtual_accounts_singleton_true")
            ],
        },
    ),
    migrations.CreateModel(
        name="CashLedgerEntry",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("created_at", models.DateTimeField()),
            ("entry_type", models.TextField()),
            ("amount_krw", models.BigIntegerField()),
            ("description", models.TextField()),
            ("execution_order_id", models.BigIntegerField(blank=True, null=True)),
            (
                "account",
                models.ForeignKey(
                    db_column="account_id", on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name="ledger_entries", to="trading.virtualaccount",
                ),
            ),
        ],
        options={
            "db_table": "cash_ledger_entries",
            "constraints": [
                models.UniqueConstraint(fields=("execution_order_id",), name="uq_cash_ledger_execution_order")
            ],
        },
    ),
    migrations.CreateModel(
        name="VirtualBuyOrder",
        fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("ticker", models.TextField()),
            ("quantity", models.BigIntegerField()),
            ("decision_trade_date", models.DateField()),
            ("created_at", models.DateTimeField()),
            ("status", models.TextField(default="pending")),
            ("executed_at", models.DateTimeField(blank=True, null=True)),
            ("execution_trade_date", models.DateField(blank=True, null=True)),
            ("base_open_price_krw", models.BigIntegerField(blank=True, null=True)),
            ("execution_price_krw", models.BigIntegerField(blank=True, null=True)),
            ("gross_amount_krw", models.BigIntegerField(blank=True, null=True)),
            ("fee_krw", models.BigIntegerField(blank=True, null=True)),
            ("price_data_source", models.TextField(blank=True, null=True)),
            ("price_adjusted", models.BooleanField(blank=True, null=True)),
            ("price_collection_run_id", models.TextField(blank=True, null=True)),
            ("termination_reason", models.TextField(blank=True, null=True)),
            (
                "account",
                models.ForeignKey(
                    db_column="account_id", on_delete=django.db.models.deletion.DO_NOTHING,
                    related_name="buy_orders", to="trading.virtualaccount",
                ),
            ),
        ],
        options={
            "db_table": "virtual_buy_orders",
            "constraints": [
                models.CheckConstraint(condition=models.Q(("quantity__gt", 0)), name="virtual_buy_orders_quantity_positive"),
                models.CheckConstraint(
                    condition=models.Q(("status__in", ["pending", "filled", "rejected_insufficient_cash"])),
                    name="virtual_buy_orders_status_valid",
                ),
            ],
        },
    ),
]


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=_STATE_OPERATIONS,
            database_operations=[migrations.RunSQL(sql=_ADOPT_SQL, reverse_sql=migrations.RunSQL.noop)],
        )
    ]
