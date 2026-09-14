"""backend 설정 계층. 모든 환경변수는 여기에서만 읽는다.

비밀값은 backend 프로세스 안에서만 사용하고 로그나 응답에 노출하지 않는다.
필수 DB 설정이 없으면 pydantic이 명시적 오류를 내며, 값 자체는 출력하지 않는다.
"""

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
    def market_data_configured(self) -> bool:
        # 제공처·주소·인증키 중 하나라도 비어 있으면 시장 데이터 요청을 보내지 않는다.
        return bool(
            self.market_data_provider
            and self.market_data_base_url
            and self.market_data_api_key
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
