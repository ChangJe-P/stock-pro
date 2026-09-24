"""T-006 읽기 전용 가상 포트폴리오 계산.

체결(filled)된 가상 매수 주문과 저장된 비조정 일봉만 재사용해 보유 수량·매수 원가·평가 결과를
계산한다. 읽기만 하며 계좌 초기화·주문 생성/체결·원장 쓰기·pykrx/HTTP 가격 수집·schema 변경을
절대 시작하지 않는다. `GET /`에서만 사용한다.

금액은 정수(KRW), 수익률 중간 계산은 Decimal(소수 둘째 자리)로 처리한다. binary float를 쓰지 않는다.
매도 수수료·세금은 적용하지 않는다(매수 수수료는 이미 매수 원가에 포함).
"""

from decimal import ROUND_HALF_UP, Decimal

from . import accounts
from .models import DailyPrice, VirtualBuyOrder

# 계산 불가 사유(템플릿이 안전한 안내로 변환한다).
REASON_INCOMPLETE_FILL = "incomplete_fill_data"
REASON_NO_COMMON_DATE = "no_common_valuation_date"
REASON_INVALID_ACCOUNT_DATA = "invalid_account_data"


def _state(value: int) -> str:
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _pct(numerator: int, denominator: int) -> str:
    # 수익률은 Decimal로 계산해 소수 둘째 자리까지. denominator는 양수임을 보장한 뒤 호출한다.
    value = (Decimal(numerator) / Decimal(denominator) * Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return str(value)


def _is_complete(order: VirtualBuyOrder) -> bool:
    # 비어 있는 값뿐 아니라 유효하지 않은 값(0 이하 체결 금액, 음수 수수료)도 불완전으로 본다.
    # DB에 금액 CHECK 제약이 없어 과거·수동 입력·버그로 생긴 비정상 행을 0으로 추정 보정하지 않는다.
    return (
        order.quantity is not None
        and order.quantity > 0
        and order.gross_amount_krw is not None
        and order.gross_amount_krw > 0
        and order.fee_krw is not None
        and order.fee_krw >= 0
        and order.execution_trade_date is not None
    )


def _aggregate_holdings(complete_orders):
    """종목별 보유 수량과 매수 원가(매수 수수료 포함)를 합산한다."""
    holdings: dict[str, dict] = {}
    for o in complete_orders:
        h = holdings.setdefault(o.ticker, {"ticker": o.ticker, "quantity": 0, "cost_krw": 0})
        h["quantity"] += o.quantity
        h["cost_krw"] += o.gross_amount_krw + o.fee_krw
    return holdings


def _pick_valuation_date(tickers, latest_execution):
    """모든 보유 종목에 공통이고 모든 체결일 이후인 가장 최신 저장 거래일을 고른다(없으면 None)."""
    common = None
    for t in tickers:
        dates = set(
            DailyPrice.objects.filter(ticker=t, adjusted=False).values_list("trade_date", flat=True)
        )
        common = dates if common is None else (common & dates)
        if not common:
            return None
    candidates = [d for d in common if d >= latest_execution]
    return max(candidates) if candidates else None


def _empty_summary(account) -> dict:
    """보유 종목이 없을 때: 평가금액 0, 총자산=가용 현금, 총 손익=가용 현금-최초 현금."""
    cash = accounts.available_cash(account)
    initial = account.initial_cash_krw
    total_pnl = cash - initial
    return {
        "available_cash_krw": cash,
        "initial_cash_krw": initial,
        "valuation_available": True,
        "total_market_value_krw": 0,
        "total_assets_krw": cash,
        "total_pnl_krw": total_pnl,
        "total_return_pct": _pct(total_pnl, initial),
        "total_state": _state(total_pnl),
    }


def _unavailable_summary(account) -> dict:
    """평가 불가일 때의 요약: 가용 현금만 확정, 평가 관련 값은 None."""
    return {
        "available_cash_krw": accounts.available_cash(account),
        "initial_cash_krw": account.initial_cash_krw,
        "valuation_available": False,
        "total_market_value_krw": None,
        "total_assets_krw": None,
        "total_pnl_krw": None,
        "total_return_pct": None,
        "total_state": None,
    }


def compute_portfolio(account) -> dict:
    """계좌의 포트폴리오 읽기 모델을 만든다. 읽기 전용 ORM 조회만 수행한다."""
    filled = list(VirtualBuyOrder.objects.filter(account=account, status="filled"))
    # 최초 가상 현금은 수익률 분모이므로 0 이하·누락이면 안전 처리한다.
    initial = account.initial_cash_krw
    initial_ok = isinstance(initial, int) and initial > 0

    # 보유 종목 없음: 평가 기준일 없이 빈 상태.
    if not filled:
        if not initial_ok:
            return {
                "empty": True,
                "valuation_available": False,
                "unavailable_reason": REASON_INVALID_ACCOUNT_DATA,
                "valuation_trade_date": None,
                "price_source": None,
                "holdings": [],
                "summary": _unavailable_summary(account),
            }
        return {
            "empty": True,
            "valuation_available": True,
            "unavailable_reason": None,
            "valuation_trade_date": None,
            "price_source": None,
            "holdings": [],
            "summary": _empty_summary(account),
        }

    complete = [o for o in filled if _is_complete(o)]
    has_incomplete = len(complete) != len(filled)

    # 보유 수량·매수 원가는 가능한 경우(완전한 체결) 보여준다.
    agg = _aggregate_holdings(complete)
    base_holdings = [
        {**h, "valuation_available": False, "close_price_krw": None, "market_value_krw": None,
         "pnl_krw": None, "return_pct": None, "state": None}
        for h in sorted(agg.values(), key=lambda x: x["ticker"])
    ]

    def _unavailable(reason):
        return {
            "empty": False,
            "valuation_available": False,
            "unavailable_reason": reason,
            "valuation_trade_date": None,
            "price_source": None,
            "holdings": base_holdings,
            "summary": _unavailable_summary(account),
        }

    # 체결 필수값이 불완전/무효하거나 계산된 종목 원가가 0 이하면 0 보정·추정 없이 계산 불가.
    if has_incomplete or not complete or any(h["cost_krw"] <= 0 for h in agg.values()):
        return _unavailable(REASON_INCOMPLETE_FILL)
    # 최초 가상 현금이 무효면 총 수익률 분모가 성립하지 않으므로 안전 처리한다.
    if not initial_ok:
        return _unavailable(REASON_INVALID_ACCOUNT_DATA)

    latest_execution = max(o.execution_trade_date for o in complete)
    tickers = [h["ticker"] for h in base_holdings]
    valuation_date = _pick_valuation_date(tickers, latest_execution)

    # 공통 기준일이 없으면 외부 수집·보간 없이 계산 불가.
    if valuation_date is None:
        return _unavailable(REASON_NO_COMMON_DATE)

    holdings = []
    total_market_value = 0
    price_source = None
    for h in base_holdings:
        row = DailyPrice.objects.filter(
            ticker=h["ticker"], trade_date=valuation_date, adjusted=False
        ).first()
        close_price = row.close_price
        price_source = row.data_source if price_source is None else price_source
        market_value = h["quantity"] * close_price
        pnl = market_value - h["cost_krw"]
        total_market_value += market_value
        holdings.append({
            "ticker": h["ticker"],
            "quantity": h["quantity"],
            "cost_krw": h["cost_krw"],
            "valuation_available": True,
            "close_price_krw": close_price,
            "market_value_krw": market_value,
            "pnl_krw": pnl,
            "return_pct": _pct(pnl, h["cost_krw"]),
            "state": _state(pnl),
        })

    cash = accounts.available_cash(account)
    initial = account.initial_cash_krw
    total_assets = cash + total_market_value
    total_pnl = total_assets - initial
    summary = {
        "available_cash_krw": cash,
        "initial_cash_krw": initial,
        "valuation_available": True,
        "total_market_value_krw": total_market_value,
        "total_assets_krw": total_assets,
        "total_pnl_krw": total_pnl,
        "total_return_pct": _pct(total_pnl, initial),
        "total_state": _state(total_pnl),
    }
    return {
        "empty": False,
        "valuation_available": True,
        "unavailable_reason": None,
        "valuation_trade_date": valuation_date,
        "price_source": price_source,
        "holdings": holdings,
        "summary": summary,
    }
