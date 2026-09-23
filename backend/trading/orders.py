"""T-004 가상 매수 주문·다음 거래일 시가 체결(Django ORM 이식).

매수만 지원한다. 체결은 결정 거래일보다 엄격히 뒤인 첫 저장 비조정 일봉 시가로만 이루어진다.
금액은 KRW 정수, 수수료는 Decimal(str(rate))와 명시적 올림으로 계산한다(binary float 금지).
가격 조회·체결은 pykrx·외부 수집을 호출하지 않고 저장된 daily_prices만 읽는다.
"""

import logging
from datetime import date, datetime, timezone
from decimal import ROUND_CEILING, Decimal

from django.db import IntegrityError, transaction

from . import accounts, market_data
from .accounts import ACCOUNT_KIND, DISCLAIMER
from .errors import ApiError
from .models import CashLedgerEntry, VirtualAccount, VirtualBuyOrder

logger = logging.getLogger("jumong.virtual_orders")

BUY_EXECUTION = "buy_execution"


def _ceil_div(numerator: int, denominator: int) -> int:
    # 양의 정수 올림 나눗셈. binary float를 쓰지 않는다.
    return -(-numerator // denominator)


def compute_execution(open_price: int, quantity: int, slippage_bps: int, buy_fee_rate) -> dict:
    """문서의 슬리피지·수수료 올림 규칙을 결정적 정수/Decimal로 적용한다."""
    execution_price = _ceil_div(open_price * (10_000 + slippage_bps), 10_000)
    gross = execution_price * quantity
    fee_decimal = (Decimal(gross) * Decimal(str(buy_fee_rate))).to_integral_value(rounding=ROUND_CEILING)
    fee = int(fee_decimal)
    return {
        "execution_price_krw": execution_price,
        "gross_amount_krw": gross,
        "fee_krw": fee,
        "cash_delta_krw": -(gross + fee),
    }


def _order_response(order: VirtualBuyOrder) -> dict:
    return {
        "account_kind": ACCOUNT_KIND,
        "disclaimer": DISCLAIMER,
        "order_id": order.id,
        "account_id": order.account_id,
        "side": "buy",
        "ticker": order.ticker,
        "quantity": order.quantity,
        "decision_trade_date": order.decision_trade_date,
        "created_at": order.created_at,
        "status": order.status,
        "executed_at": order.executed_at,
        "execution_trade_date": order.execution_trade_date,
        "base_open_price_krw": order.base_open_price_krw,
        "execution_price_krw": order.execution_price_krw,
        "gross_amount_krw": order.gross_amount_krw,
        "fee_krw": order.fee_krw,
        "price_source": {
            "data_source": order.price_data_source,
            "adjusted": order.price_adjusted,
            "collection_run_id": order.price_collection_run_id,
        },
        "termination_reason": order.termination_reason,
    }


def create_order(ticker: str, quantity: int, decision_trade_date: date) -> dict:
    """결정일의 비조정 저장 일봉이 있을 때만 pending 매수 주문을 만든다. 현금은 바꾸지 않는다."""
    account = VirtualAccount.objects.first()
    if account is None:
        raise ApiError(404, "가상 학습 계좌가 아직 없습니다. 먼저 계좌를 초기화하세요.")
    # 결정일 비조정 일봉 존재만 확인한다. 외부 수집을 시작하지 않는다.
    if not market_data.stored_unadjusted_price_exists(ticker, decision_trade_date):
        raise ApiError(409, "결정 거래일의 저장된 비조정 일봉이 없습니다. 먼저 해당 일봉을 수집하세요.")
    order = VirtualBuyOrder.objects.create(
        account=account, ticker=ticker, quantity=quantity,
        decision_trade_date=decision_trade_date, created_at=datetime.now(timezone.utc),
        status="pending",
    )
    return _order_response(order)


def _apply_execution(order: VirtualBuyOrder, status_value: str, now, price: dict, calc: dict, termination_reason):
    order.status = status_value
    order.executed_at = now
    order.execution_trade_date = price["trade_date"]
    order.base_open_price_krw = price["open_price"]
    order.execution_price_krw = calc["execution_price_krw"]
    order.gross_amount_krw = calc["gross_amount_krw"]
    order.fee_krw = calc["fee_krw"]
    order.price_data_source = price["data_source"]
    order.price_adjusted = price["adjusted"]
    order.price_collection_run_id = price["collection_run_id"]
    order.termination_reason = termination_reason
    order.save()
    return order


def execute_order(order_id: int) -> dict:
    """지정한 pending 주문 한 건만 수동 체결한다(계좌 잠금으로 직렬화)."""
    try:
        with transaction.atomic():
            # 계좌 행을 잠가 현금 확인·상태 갱신·원장 추가를 직렬화한다.
            account = VirtualAccount.objects.select_for_update().order_by("id").first()
            if account is None:
                raise ApiError(404, "가상 학습 계좌가 아직 없습니다. 먼저 계좌를 초기화하세요.")
            try:
                order = VirtualBuyOrder.objects.select_for_update().get(id=order_id)
            except VirtualBuyOrder.DoesNotExist:
                raise ApiError(404, "주문을 찾을 수 없습니다.")
            if order.account_id != account.id:
                raise ApiError(404, "주문을 찾을 수 없습니다.")
            if order.status != "pending":
                # 이미 filled/rejected: 기존 결과만 반환하고 원장을 더 만들지 않는다.
                return _order_response(order)

            price = market_data.earliest_unadjusted_open_after(order.ticker, order.decision_trade_date)
            if price is None:
                # 다음 거래일 시가 미저장: pending 유지, 외부 수집 없이 409.
                raise ApiError(409, "다음 거래일 시가가 아직 저장되지 않았습니다. pending을 유지합니다.")

            calc = compute_execution(
                price["open_price"], order.quantity, account.slippage_bps, account.buy_fee_rate
            )
            needed = calc["gross_amount_krw"] + calc["fee_krw"]
            current_cash = accounts.available_cash(account)
            now = datetime.now(timezone.utc)

            if current_cash < needed:
                # 현금 부족: 종료 상태만 남기고 원장은 만들지 않는다.
                return _order_response(
                    _apply_execution(order, "rejected_insufficient_cash", now, price, calc, "insufficient_cash")
                )

            # 현금 충분: 음수 buy_execution 원장 한 행 + 주문 filled를 한 트랜잭션에서 기록한다.
            CashLedgerEntry.objects.create(
                account=account, created_at=now, entry_type=BUY_EXECUTION,
                amount_krw=calc["cash_delta_krw"], description="가상 매수 체결",
                execution_order_id=order.id,
            )
            return _order_response(_apply_execution(order, "filled", now, price, calc, None))
    except IntegrityError:
        # 동시 체결 경합으로 원장 유일 제약 위반. 중복 차감 없이 기존 결과를 반환한다.
        logger.warning("체결 원장 유일 제약 위반(동시 체결 추정)")
        order = VirtualBuyOrder.objects.filter(id=order_id).first()
        if order is None:
            raise ApiError(404, "주문을 찾을 수 없습니다.")
        return _order_response(order)


def list_orders() -> dict:
    """주문을 created_at ASC, id ASC로 반환한다. 외부 수집·체결·상태 변경을 시작하지 않는다."""
    orders = VirtualBuyOrder.objects.order_by("created_at", "id")
    return {
        "account_kind": ACCOUNT_KIND,
        "disclaimer": DISCLAIMER,
        "orders": [_order_response(o) for o in orders],
    }
