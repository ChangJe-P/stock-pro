"""T-003 가상계좌·현금 원장(Django ORM 이식).

단일 로컬 가상 학습 계좌와 추가 전용 현금 원장. 현재 현금은 원장 합계로 계산한다.
정책 값은 config 계층에서만 읽고 계좌 최초 생성 시 스냅샷으로 저장한다.
"""

import logging
from datetime import datetime, timezone

from django.db import IntegrityError, transaction
from django.db.models import Sum

from .config import VirtualPolicyError, load_virtual_policy
from .errors import ApiError
from .models import CashLedgerEntry, VirtualAccount

logger = logging.getLogger("jumong.virtual_account")

ACCOUNT_KIND = "virtual_learning"
DISCLAIMER = "실제 돈·계좌·주문과 무관한 가상 학습 계좌입니다."
OPENING_BALANCE = "opening_balance"


def available_cash(account: VirtualAccount) -> int:
    total = CashLedgerEntry.objects.filter(account=account).aggregate(s=Sum("amount_krw"))["s"]
    return int(total or 0)


def _account_response(account: VirtualAccount, cash: int) -> dict:
    return {
        "account_kind": ACCOUNT_KIND,
        "disclaimer": DISCLAIMER,
        "account_id": account.id,
        "created_at": account.created_at,
        "policy_version": account.policy_version,
        "policy_snapshot": {
            "initial_cash_krw": account.initial_cash_krw,
            "buy_fee_rate": account.buy_fee_rate,
            "sell_fee_rate": account.sell_fee_rate,
            "sell_tax_rate": account.sell_tax_rate,
            "slippage_bps": account.slippage_bps,
        },
        "initial_cash_krw": account.initial_cash_krw,
        "available_cash_krw": cash,
    }


def _not_found() -> ApiError:
    return ApiError(404, "가상 학습 계좌가 아직 없습니다. 먼저 초기화하세요.")


def initialize_account() -> dict:
    """계좌가 없으면 설정 스냅샷으로 한 번만 생성하고, 있으면 기존 계좌를 그대로 반환한다."""
    # 설정 검증을 먼저 수행해, 오류 시 DB 부분 기록 없이 명시적으로 실패한다.
    try:
        policy = load_virtual_policy()
    except VirtualPolicyError as exc:
        raise ApiError(500, str(exc))

    account = VirtualAccount.objects.first()
    if account is None:
        now = datetime.now(timezone.utc)
        try:
            with transaction.atomic():
                account = VirtualAccount.objects.create(
                    created_at=now, policy_version=policy.policy_version,
                    initial_cash_krw=policy.initial_cash_krw, buy_fee_rate=policy.buy_fee_rate,
                    sell_fee_rate=policy.sell_fee_rate, sell_tax_rate=policy.sell_tax_rate,
                    slippage_bps=policy.slippage_bps, singleton=True,
                )
                CashLedgerEntry.objects.create(
                    account=account, created_at=now, entry_type=OPENING_BALANCE,
                    amount_krw=policy.initial_cash_krw, description="가상 학습 계좌 최초 적립",
                )
        except IntegrityError:
            # 동시 초기화 경합. DB 유일 제약이 두 번째 생성을 막았으므로 기존 계좌를 반환한다.
            account = VirtualAccount.objects.first()

    return _account_response(account, available_cash(account))


def get_account() -> dict:
    account = VirtualAccount.objects.first()
    if account is None:
        raise _not_found()
    return _account_response(account, available_cash(account))


def list_cash_ledger() -> dict:
    account = VirtualAccount.objects.first()
    if account is None:
        raise _not_found()
    entries = (
        CashLedgerEntry.objects.filter(account=account).order_by("created_at", "id")
    )
    return {
        "account_kind": ACCOUNT_KIND,
        "disclaimer": DISCLAIMER,
        "account_id": account.id,
        "entries": [
            {
                "id": e.id, "account_id": account.id, "created_at": e.created_at,
                "entry_type": e.entry_type, "amount_krw": e.amount_krw, "description": e.description,
            }
            for e in entries
        ],
    }
