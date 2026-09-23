"""설정 계층 읽기: 시장 데이터 제공처 판정과 가상 거래 정책 검증.

값은 django settings(환경변수)에서만 읽고, 오류 메시지에 값 자체를 넣지 않는다.
"""

from dataclasses import dataclass

from django.conf import settings


def market_data_provider_normalized() -> str:
    return (settings.MARKET_DATA_PROVIDER or "").strip().lower()


def market_data_configured() -> bool:
    # T-002에서 승인된 제공처는 pykrx뿐이다. 빈 값이나 다른 값은 미설정으로 본다.
    return market_data_provider_normalized() == "pykrx"


# --- 가상 거래 정책(T-003) ---------------------------------------------------

class VirtualPolicyError(ValueError):
    """가상 거래 정책 설정 오류. 메시지에 설정 값 자체나 비밀값을 넣지 않는다."""


@dataclass(frozen=True)
class VirtualPolicy:
    initial_cash_krw: int
    buy_fee_rate: float
    sell_fee_rate: float
    sell_tax_rate: float
    slippage_bps: int
    policy_version: str


def _required(raw, name: str) -> str:
    if raw is None or str(raw).strip() == "":
        raise VirtualPolicyError(f"{name} 설정이 필요합니다.")
    return str(raw).strip()


def _as_int(raw, name: str) -> int:
    try:
        return int(_required(raw, name))
    except (ValueError, TypeError):
        raise VirtualPolicyError(f"{name} 값 형식이 올바르지 않습니다.")


def _as_float(raw, name: str) -> float:
    try:
        return float(_required(raw, name))
    except (ValueError, TypeError):
        raise VirtualPolicyError(f"{name} 값 형식이 올바르지 않습니다.")


def load_virtual_policy() -> VirtualPolicy:
    """설정 계층의 가상 거래 값을 검증해 정책 스냅샷으로 만든다.

    누락·형식 오류, 음수 현금, 음수/1 이상 비율, 음수 슬리피지는 값 노출 없이 오류로 끝낸다.
    """
    cash = _as_int(settings.VIRTUAL_INITIAL_CASH_KRW, "VIRTUAL_INITIAL_CASH_KRW")
    buy = _as_float(settings.VIRTUAL_BUY_FEE_RATE, "VIRTUAL_BUY_FEE_RATE")
    sell = _as_float(settings.VIRTUAL_SELL_FEE_RATE, "VIRTUAL_SELL_FEE_RATE")
    tax = _as_float(settings.VIRTUAL_SELL_TAX_RATE, "VIRTUAL_SELL_TAX_RATE")
    slippage = _as_int(settings.VIRTUAL_SLIPPAGE_BPS, "VIRTUAL_SLIPPAGE_BPS")
    version = _required(settings.VIRTUAL_TRADING_POLICY_VERSION, "VIRTUAL_TRADING_POLICY_VERSION")

    if cash <= 0:
        raise VirtualPolicyError("VIRTUAL_INITIAL_CASH_KRW는 양수여야 합니다.")
    for name, rate in (
        ("VIRTUAL_BUY_FEE_RATE", buy),
        ("VIRTUAL_SELL_FEE_RATE", sell),
        ("VIRTUAL_SELL_TAX_RATE", tax),
    ):
        if not (0 <= rate < 1):
            raise VirtualPolicyError(f"{name}는 0 이상 1 미만이어야 합니다.")
    if slippage < 0:
        raise VirtualPolicyError("VIRTUAL_SLIPPAGE_BPS는 0 이상이어야 합니다.")

    return VirtualPolicy(cash, buy, sell, tax, slippage, version)
