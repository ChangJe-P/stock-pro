"""backend 설정 계층. 모든 환경변수는 여기에서만 읽는다.

비밀값은 backend 프로세스 안에서만 사용하고 로그나 응답에 노출하지 않는다.
필수 DB 설정이 없으면 pydantic이 명시적 오류를 내며, 값 자체는 출력하지 않는다.
"""

from dataclasses import dataclass
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # .env가 있으면 읽고, 없으면(Docker/CI) 실제 환경변수를 사용한다.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"

    # DB 접속 정보. 기본값 없이 필수로 두어 누락 시 명시적 오류가 나게 한다.
    postgres_host: str
    postgres_port: int
    postgres_db: str
    postgres_user: str
    postgres_password: str

    # 콤마로 구분한 개발 frontend 주소 목록.
    cors_allowed_origins: str = ""

    # 외부 연동 값은 아직 비어 있어도 기동을 막지 않는다.
    market_data_provider: str = ""
    market_data_base_url: str = ""
    market_data_api_key: str = ""
    market_data_api_secret: str = ""
    market_data_requests_per_minute: str = ""
    notion_integration_token: str = ""

    # T-003 가상 거래 정책(v1). 값은 .env/.env.example에만 두고 여기서 기본값을 두지 않는다.
    # 원시 문자열로 받아 load_virtual_policy에서 형식·범위를 검증한다(값을 노출하지 않는 안전한 오류).
    virtual_initial_cash_krw: str | None = None
    virtual_buy_fee_rate: str | None = None
    virtual_sell_fee_rate: str | None = None
    virtual_sell_tax_rate: str | None = None
    virtual_slippage_bps: str | None = None
    virtual_trading_policy_version: str | None = None

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.cors_allowed_origins.split(",") if o.strip()]

    @property
    def market_data_provider_normalized(self) -> str:
        return self.market_data_provider.strip().lower()

    @property
    def market_data_configured(self) -> bool:
        # T-002에서 승인된 제공처는 pykrx뿐이다. 빈 값이나 다른 값은 미설정으로 본다.
        # pykrx는 API 키·endpoint가 필요 없으므로 provider 값만 확인한다.
        return self.market_data_provider_normalized == "pykrx"


@lru_cache
def get_settings() -> Settings:
    return Settings()


# --- T-003 가상 거래 정책 -----------------------------------------------------

class VirtualPolicyError(ValueError):
    """가상 거래 정책 설정 오류. 메시지에 설정 값 자체나 비밀값을 넣지 않는다."""


@dataclass(frozen=True)
class VirtualPolicy:
    """계좌 최초 생성 시 스냅샷으로 저장할 학습용 시뮬레이션 정책(v1)."""

    initial_cash_krw: int
    buy_fee_rate: float
    sell_fee_rate: float
    sell_tax_rate: float
    slippage_bps: int
    policy_version: str


def _required(raw: str | None, name: str) -> str:
    if raw is None or str(raw).strip() == "":
        raise VirtualPolicyError(f"{name} 설정이 필요합니다.")
    return str(raw).strip()


def _as_int(raw: str | None, name: str) -> int:
    try:
        return int(_required(raw, name))
    except (ValueError, TypeError):
        raise VirtualPolicyError(f"{name} 값 형식이 올바르지 않습니다.")


def _as_float(raw: str | None, name: str) -> float:
    try:
        return float(_required(raw, name))
    except (ValueError, TypeError):
        raise VirtualPolicyError(f"{name} 값 형식이 올바르지 않습니다.")


def load_virtual_policy(settings: Settings) -> VirtualPolicy:
    """설정 계층의 가상 거래 값을 검증해 정책 스냅샷으로 만든다.

    누락·형식 오류, 음수 현금, 음수/1 이상 비율, 음수 슬리피지는 값 노출 없이 오류로 끝낸다.
    """
    cash = _as_int(settings.virtual_initial_cash_krw, "VIRTUAL_INITIAL_CASH_KRW")
    buy = _as_float(settings.virtual_buy_fee_rate, "VIRTUAL_BUY_FEE_RATE")
    sell = _as_float(settings.virtual_sell_fee_rate, "VIRTUAL_SELL_FEE_RATE")
    tax = _as_float(settings.virtual_sell_tax_rate, "VIRTUAL_SELL_TAX_RATE")
    slippage = _as_int(settings.virtual_slippage_bps, "VIRTUAL_SLIPPAGE_BPS")
    version = _required(settings.virtual_trading_policy_version, "VIRTUAL_TRADING_POLICY_VERSION")

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


def get_virtual_policy() -> VirtualPolicy:
    return load_virtual_policy(get_settings())
