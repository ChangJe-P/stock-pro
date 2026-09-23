"""주몽 Django 설정. 모든 설정값은 여기(설정 계층)에서만 환경변수로 읽는다.

비밀값·DB 접속 정보·허용 호스트는 환경변수로만 읽고 로그·응답에 노출하지 않는다.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

APP_ENV = os.environ.get("APP_ENV", "development")

# 비밀 키는 환경변수에서만 읽는다. .env에만 실제 값을 두고 Git에는 예시만 저장한다.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "")

# 개발 환경에서만 DEBUG를 켠다.
DEBUG = APP_ENV == "development"

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

INSTALLED_APPS = [
    "trading",
]

# 같은 origin에서 화면과 JSON API를 제공하므로 CORS 미들웨어를 두지 않는다.
# JSON POST view는 개별적으로 CSRF 예외를 명시한다(비로그인 로컬 API 호환).
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "jumong.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "jumong.wsgi.application"
ASGI_APPLICATION = "jumong.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", ""),
        "USER": os.environ.get("POSTGRES_USER", ""),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", ""),
        "PORT": os.environ.get("POSTGRES_PORT", ""),
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"

# --- 도메인 설정값(설정 계층에서만 읽는다) -----------------------------------
# 시장 데이터 제공처(T-002). pykrx만 승인된 제공처다.
MARKET_DATA_PROVIDER = os.environ.get("MARKET_DATA_PROVIDER", "")

# 가상 거래 정책(T-003). 원시 문자열로 두고 trading.config에서 형식·범위를 검증한다.
VIRTUAL_INITIAL_CASH_KRW = os.environ.get("VIRTUAL_INITIAL_CASH_KRW")
VIRTUAL_BUY_FEE_RATE = os.environ.get("VIRTUAL_BUY_FEE_RATE")
VIRTUAL_SELL_FEE_RATE = os.environ.get("VIRTUAL_SELL_FEE_RATE")
VIRTUAL_SELL_TAX_RATE = os.environ.get("VIRTUAL_SELL_TAX_RATE")
VIRTUAL_SLIPPAGE_BPS = os.environ.get("VIRTUAL_SLIPPAGE_BPS")
VIRTUAL_TRADING_POLICY_VERSION = os.environ.get("VIRTUAL_TRADING_POLICY_VERSION")
