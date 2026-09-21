"""T-004 가상 매수 주문·다음 거래일 시가 체결.

실제 돈·실제 주문·자동매매와 무관한 학습용 기능이다. 매수만 지원한다.
체결은 결정 거래일보다 엄격히 뒤인 첫 저장 비조정 일봉 시가로만 이루어진다(미래 데이터 누수 방지).
금액은 KRW 정수(bigint)로 저장하고, 수수료는 Decimal 등 결정적 산술로 계산한다(binary float 금지).
가격 조회·체결은 pykrx·HTTP·수집 API를 호출하지 않고 저장된 daily_prices만 읽는다.
"""

import logging
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, Decimal

import psycopg
from fastapi import APIRouter, HTTPException, status
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

from . import market_data, virtual_account
from .config import get_settings

logger = logging.getLogger("jumong.virtual_orders")

ACCOUNT_KIND = virtual_account.ACCOUNT_KIND
DISCLAIMER = virtual_account.DISCLAIMER
BUY_EXECUTION = "buy_execution"

_STATUSES = ("pending", "filled", "rejected_insufficient_cash")

# 주문 테이블과 체결 원장 연결 컬럼을 재실행 안전하게 만든다.
# 체결 주문당 원장 한 행만 허용하는 유일 인덱스(비체결 원장은 NULL이라 여러 행 허용).
_ORDER_DDL = """
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


def _connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().database_url, connect_timeout=5, row_factory=dict_row)
    with conn.cursor() as cur:
        # 재실행 안전한 최소 스키마 초기화. 시장 데이터·계좌·주문 스키마를 모두 보장한다.
        cur.execute(market_data._SCHEMA_DDL)
        cur.execute(virtual_account._SCHEMA_DDL)
        cur.execute(_ORDER_DDL)
    conn.commit()
    return conn


# --- 금액 계산(결정적 정수/Decimal) ------------------------------------------

def _ceil_div(numerator: int, denominator: int) -> int:
    # 양의 정수 올림 나눗셈. binary float를 쓰지 않는다.
    return -(-numerator // denominator)


def compute_execution(open_price: int, quantity: int, slippage_bps: int, buy_fee_rate) -> dict:
    """문서의 슬리피지·수수료 올림 규칙을 결정적 정수/Decimal로 적용한다."""
    execution_price = _ceil_div(open_price * (10_000 + slippage_bps), 10_000)
    gross = execution_price * quantity
    # 수수료율은 계좌 스냅샷의 float일 수 있으므로 str을 거쳐 정확한 Decimal로 변환한다.
    fee_decimal = (Decimal(gross) * Decimal(str(buy_fee_rate))).to_integral_value(rounding=ROUND_CEILING)
    fee = int(fee_decimal)
    return {
        "execution_price_krw": execution_price,
        "gross_amount_krw": gross,
        "fee_krw": fee,
        "cash_delta_krw": -(gross + fee),
    }


# --- 저장소 ------------------------------------------------------------------

def _lock_account(cur) -> dict | None:
    # 체결을 직렬화하기 위해 단일 계좌 행을 잠근다(동시 체결로 인한 음수 현금 방지).
    cur.execute(
        "SELECT id, buy_fee_rate, slippage_bps FROM virtual_accounts ORDER BY id LIMIT 1 FOR UPDATE"
    )
    return cur.fetchone()


def _select_order(cur, order_id: int, lock: bool = False) -> dict | None:
    cur.execute(
        f"SELECT * FROM virtual_buy_orders WHERE id = %s{' FOR UPDATE' if lock else ''}",
        (order_id,),
    )
    return cur.fetchone()


def _select_all_orders(cur) -> list[dict]:
    cur.execute("SELECT * FROM virtual_buy_orders ORDER BY created_at ASC, id ASC")
    return cur.fetchall()


def _insert_pending_order(cur, account_id: int, ticker: str, quantity: int, decision_trade_date: date) -> dict:
    cur.execute(
        """
        INSERT INTO virtual_buy_orders (account_id, ticker, quantity, decision_trade_date, created_at, status)
        VALUES (%s, %s, %s, %s, %s, 'pending')
        RETURNING *
        """,
        (account_id, ticker, quantity, decision_trade_date, datetime.now(timezone.utc)),
    )
    return cur.fetchone()


def _apply_execution(cur, order_id: int, status_value: str, now, price: dict, calc: dict, termination_reason) -> dict:
    """주문에 체결 결과(가격 출처·계산값·상태)를 기록하고 갱신된 행을 반환한다."""
    cur.execute(
        """
        UPDATE virtual_buy_orders SET
            status = %s,
            executed_at = %s, execution_trade_date = %s,
            base_open_price_krw = %s, execution_price_krw = %s,
            gross_amount_krw = %s, fee_krw = %s,
            price_data_source = %s, price_adjusted = %s, price_collection_run_id = %s,
            termination_reason = %s
        WHERE id = %s RETURNING *
        """,
        (
            status_value, now, price["trade_date"], price["open_price"], calc["execution_price_krw"],
            calc["gross_amount_krw"], calc["fee_krw"],
            price["data_source"], price["adjusted"], price["collection_run_id"],
            termination_reason, order_id,
        ),
    )
    return cur.fetchone()


def _mark_rejected(cur, order_id: int, now, price: dict, calc: dict) -> dict:
    # 현금 부족: 종료 상태만 남기고 현금 원장은 만들지 않는다.
    return _apply_execution(cur, order_id, "rejected_insufficient_cash", now, price, calc, "insufficient_cash")


def _mark_filled(cur, account_id: int, order_id: int, now, price: dict, calc: dict) -> dict:
    # 음수 buy_execution 원장 한 행과 주문 filled를 같은 트랜잭션에서 기록한다.
    cur.execute(
        """
        INSERT INTO cash_ledger_entries
            (account_id, created_at, entry_type, amount_krw, description, execution_order_id)
        VALUES (%s, %s, %s, %s, %s, %s)
        """,
        (account_id, now, BUY_EXECUTION, calc["cash_delta_krw"], "가상 매수 체결", order_id),
    )
    return _apply_execution(cur, order_id, "filled", now, price, calc, None)


# --- 응답 --------------------------------------------------------------------

def _order_response(order: dict) -> dict:
    return {
        "account_kind": ACCOUNT_KIND,
        "disclaimer": DISCLAIMER,
        "order_id": order["id"],
        "account_id": order["account_id"],
        "side": "buy",
        "ticker": order["ticker"],
        "quantity": order["quantity"],
        "decision_trade_date": order["decision_trade_date"],
        "created_at": order["created_at"],
        "status": order["status"],
        "executed_at": order.get("executed_at"),
        "execution_trade_date": order.get("execution_trade_date"),
        "base_open_price_krw": order.get("base_open_price_krw"),
        "execution_price_krw": order.get("execution_price_krw"),
        "gross_amount_krw": order.get("gross_amount_krw"),
        "fee_krw": order.get("fee_krw"),
        "price_source": {
            "data_source": order.get("price_data_source"),
            "adjusted": order.get("price_adjusted"),
            "collection_run_id": order.get("price_collection_run_id"),
        },
        "termination_reason": order.get("termination_reason"),
    }


def _account_not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="가상 학습 계좌가 아직 없습니다. 먼저 계좌를 초기화하세요.",
    )


# --- 서비스 ------------------------------------------------------------------

def create_order(ticker: str, quantity: int, decision_trade_date: date) -> dict:
    """결정일의 비조정 저장 일봉이 있을 때만 pending 매수 주문을 만든다. 현금은 바꾸지 않는다."""
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                account = virtual_account._select_account(cur)
                if account is None:
                    raise _account_not_found()
                # 결정일 비조정 일봉 존재만 확인한다. 외부 수집을 시작하지 않는다.
                if not market_data.stored_unadjusted_price_exists(cur, ticker, decision_trade_date):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="결정 거래일의 저장된 비조정 일봉이 없습니다. 먼저 해당 일봉을 수집하세요.",
                    )
                order = _insert_pending_order(cur, account["id"], ticker, quantity, decision_trade_date)
                return _order_response(order)
    except psycopg.Error:
        logger.warning("가상 주문 생성 실패")
        raise HTTPException(status_code=500, detail="가상 주문 생성 중 오류가 발생했습니다.")


def execute_order(order_id: int) -> dict:
    """지정한 pending 주문 한 건만 수동 체결한다.

    - 다음 거래일 시가가 없으면 주문을 바꾸지 않고 409.
    - 현금 충분: filled + 음수 buy_execution 원장 한 행을 한 트랜잭션에서 기록.
    - 현금 부족: rejected_insufficient_cash만 기록(원장 없음).
    - 이미 종료된 주문: 기존 결과만 반환.
    """
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                # 계좌를 먼저 잠가 체결을 직렬화한다.
                account = _lock_account(cur)
                if account is None:
                    raise _account_not_found()
                order = _select_order(cur, order_id, lock=True)
                if order is None:
                    raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
                if order["status"] != "pending":
                    # 이미 filled/rejected: 기존 결과만 반환하고 원장을 더 만들지 않는다.
                    return _order_response(order)
                if order["account_id"] != account["id"]:
                    raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")

                price = market_data.earliest_unadjusted_open_after(
                    cur, order["ticker"], order["decision_trade_date"]
                )
                if price is None:
                    # 다음 거래일 시가 미저장: pending 유지, 외부 수집 없이 409.
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="다음 거래일 시가가 아직 저장되지 않았습니다. pending을 유지합니다.",
                    )

                calc = compute_execution(
                    price["open_price"], order["quantity"], account["slippage_bps"], account["buy_fee_rate"]
                )
                needed = calc["gross_amount_krw"] + calc["fee_krw"]
                current_cash = virtual_account._sum_cash(cur, account["id"])
                now = datetime.now(timezone.utc)

                if current_cash < needed:
                    return _order_response(_mark_rejected(cur, order_id, now, price, calc))

                return _order_response(_mark_filled(cur, account["id"], order_id, now, price, calc))
    except psycopg.errors.UniqueViolation:
        # 동시 체결 경합으로 원장 유일 제약 위반. 중복 차감 없이 기존 결과를 반환한다.
        logger.warning("체결 원장 유일 제약 위반(동시 체결 추정)")
        with _connect() as conn:
            with conn.cursor() as cur:
                order = _select_order(cur, order_id)
                if order is None:
                    raise HTTPException(status_code=404, detail="주문을 찾을 수 없습니다.")
                return _order_response(order)
    except psycopg.Error:
        logger.warning("가상 주문 체결 실패")
        raise HTTPException(status_code=500, detail="가상 주문 체결 중 오류가 발생했습니다.")


def list_orders() -> dict:
    """주문을 created_at ASC, id ASC로 반환한다. 외부 수집·체결·상태 변경을 시작하지 않는다."""
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                rows = _select_all_orders(cur)
                return {
                    "account_kind": ACCOUNT_KIND,
                    "disclaimer": DISCLAIMER,
                    "orders": [_order_response(r) for r in rows],
                }
    except psycopg.Error:
        logger.warning("가상 주문 조회 실패")
        raise HTTPException(status_code=500, detail="가상 주문 조회 중 오류가 발생했습니다.")


# --- API ---------------------------------------------------------------------

router = APIRouter(prefix="/virtual-orders", tags=["virtual-orders"])


class CreateOrderRequest(BaseModel):
    ticker: str = Field(pattern=r"^\d{6}$")
    quantity: int = Field(gt=0)
    decision_trade_date: date


@router.post("")
def post_order(req: CreateOrderRequest) -> dict:
    return create_order(req.ticker, req.quantity, req.decision_trade_date)


@router.post("/{order_id}/execute")
def post_execute(order_id: int) -> dict:
    return execute_order(order_id)


@router.get("")
def get_orders() -> dict:
    return list_orders()
