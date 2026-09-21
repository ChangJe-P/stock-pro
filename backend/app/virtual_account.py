"""T-003 가상계좌·현금 원장.

단일 로컬 사용자의 가상 학습 계좌와 추가 전용(append-only) 현금 원장을 만든다.
실제 돈·계좌·주문과 무관하다. 모든 금액은 KRW 정수(bigint)로 다룬다.
현재 현금은 원장 금액의 합으로 계산하며, 별도 잔액을 저장·갱신하지 않는다.
정책 값은 config 계층에서만 읽고, 계좌 최초 생성 시 스냅샷으로 저장한다.
"""

import logging
from datetime import datetime, timezone

import psycopg
from fastapi import APIRouter, HTTPException, status
from psycopg.rows import dict_row

from .config import VirtualPolicy, VirtualPolicyError, get_settings, get_virtual_policy

logger = logging.getLogger("jumong.virtual_account")

ACCOUNT_KIND = "virtual_learning"
DISCLAIMER = "실제 돈·계좌·주문과 무관한 가상 학습 계좌입니다."
OPENING_BALANCE = "opening_balance"

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS virtual_accounts (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    policy_version TEXT NOT NULL,
    initial_cash_krw BIGINT NOT NULL,
    buy_fee_rate DOUBLE PRECISION NOT NULL,
    sell_fee_rate DOUBLE PRECISION NOT NULL,
    sell_tax_rate DOUBLE PRECISION NOT NULL,
    slippage_bps INTEGER NOT NULL,
    -- 단일 로컬 계좌만 존재하도록 DB 수준에서 보장한다(항상 TRUE인 유일 컬럼).
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
"""


def _connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().database_url, connect_timeout=5, row_factory=dict_row)
    with conn.cursor() as cur:
        # 마이그레이션 프레임워크 없이 재실행에 안전한 최소 스키마 초기화(T-002와 동일 방식).
        cur.execute(_SCHEMA_DDL)
    conn.commit()
    return conn


# --- 저장소 함수(커서 기반, 테스트에서 대체 가능) ----------------------------

def _select_account(cur) -> dict | None:
    cur.execute(
        """
        SELECT id, created_at, policy_version, initial_cash_krw,
               buy_fee_rate, sell_fee_rate, sell_tax_rate, slippage_bps
        FROM virtual_accounts
        ORDER BY id
        LIMIT 1
        """
    )
    return cur.fetchone()


def _create_account_with_opening(cur, policy: VirtualPolicy) -> dict:
    """계좌 한 개와 opening_balance 원장 한 개를 같은 트랜잭션에서 생성한다."""
    now = datetime.now(timezone.utc)
    cur.execute(
        """
        INSERT INTO virtual_accounts (
            created_at, policy_version, initial_cash_krw,
            buy_fee_rate, sell_fee_rate, sell_tax_rate, slippage_bps
        ) VALUES (%s,%s,%s,%s,%s,%s,%s)
        RETURNING id, created_at, policy_version, initial_cash_krw,
                  buy_fee_rate, sell_fee_rate, sell_tax_rate, slippage_bps
        """,
        (
            now, policy.policy_version, policy.initial_cash_krw,
            policy.buy_fee_rate, policy.sell_fee_rate, policy.sell_tax_rate, policy.slippage_bps,
        ),
    )
    account = cur.fetchone()
    cur.execute(
        """
        INSERT INTO cash_ledger_entries (account_id, created_at, entry_type, amount_krw, description)
        VALUES (%s,%s,%s,%s,%s)
        """,
        (account["id"], now, OPENING_BALANCE, policy.initial_cash_krw, "가상 학습 계좌 최초 적립"),
    )
    return account


def _sum_cash(cur, account_id: int) -> int:
    cur.execute(
        "SELECT COALESCE(SUM(amount_krw), 0) AS cash FROM cash_ledger_entries WHERE account_id = %s",
        (account_id,),
    )
    return int(cur.fetchone()["cash"])


def _list_ledger(cur, account_id: int) -> list[dict]:
    cur.execute(
        """
        SELECT id, account_id, created_at, entry_type, amount_krw, description
        FROM cash_ledger_entries
        WHERE account_id = %s
        ORDER BY created_at ASC, id ASC
        """,
        (account_id,),
    )
    return cur.fetchall()


# --- 응답 조립 ---------------------------------------------------------------

def _account_response(account: dict, available_cash: int) -> dict:
    return {
        "account_kind": ACCOUNT_KIND,
        "disclaimer": DISCLAIMER,
        "account_id": account["id"],
        "created_at": account["created_at"],
        "policy_version": account["policy_version"],
        "policy_snapshot": {
            "initial_cash_krw": account["initial_cash_krw"],
            "buy_fee_rate": account["buy_fee_rate"],
            "sell_fee_rate": account["sell_fee_rate"],
            "sell_tax_rate": account["sell_tax_rate"],
            "slippage_bps": account["slippage_bps"],
        },
        "initial_cash_krw": account["initial_cash_krw"],
        "available_cash_krw": available_cash,
    }


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="가상 학습 계좌가 아직 없습니다. 먼저 초기화하세요.",
    )


# --- 서비스 ------------------------------------------------------------------

def initialize_account() -> dict:
    """계좌가 없으면 설정 스냅샷으로 한 번만 생성하고, 있으면 기존 계좌를 그대로 반환한다."""
    # 설정 검증을 먼저 수행해, 오류 시 외부 요청·DB 부분 기록 없이 명시적으로 실패한다.
    try:
        policy = get_virtual_policy()
    except VirtualPolicyError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                account = _select_account(cur)
                if account is None:
                    try:
                        account = _create_account_with_opening(cur, policy)
                    except psycopg.errors.UniqueViolation:
                        # 동시 초기화 경합. DB 유일 제약이 두 번째 생성을 막았으므로 기존 계좌를 반환한다.
                        conn.rollback()
                        account = _select_account(cur)
                cash = _sum_cash(cur, account["id"])
                return _account_response(account, cash)
    except psycopg.Error:
        logger.warning("가상계좌 초기화 실패")
        raise HTTPException(status_code=500, detail="가상계좌 초기화 중 오류가 발생했습니다.")


def get_account() -> dict:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                account = _select_account(cur)
                if account is None:
                    raise _not_found()
                cash = _sum_cash(cur, account["id"])
                return _account_response(account, cash)
    except psycopg.Error:
        logger.warning("가상계좌 조회 실패")
        raise HTTPException(status_code=500, detail="가상계좌 조회 중 오류가 발생했습니다.")


def list_cash_ledger() -> dict:
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                account = _select_account(cur)
                if account is None:
                    raise _not_found()
                rows = _list_ledger(cur, account["id"])
                return {
                    "account_kind": ACCOUNT_KIND,
                    "disclaimer": DISCLAIMER,
                    "account_id": account["id"],
                    "entries": rows,
                }
    except psycopg.Error:
        logger.warning("현금 원장 조회 실패")
        raise HTTPException(status_code=500, detail="현금 원장 조회 중 오류가 발생했습니다.")


# --- API ---------------------------------------------------------------------

router = APIRouter(prefix="/virtual-account", tags=["virtual-account"])


@router.post("/initialize")
def initialize() -> dict:
    return initialize_account()


@router.get("")
def read_account() -> dict:
    return get_account()


@router.get("/cash-ledger")
def read_cash_ledger() -> dict:
    return list_cash_ledger()
