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
    # Django 인증·세션·메시지(T-010). Google 로그인은 세션 기반이다.
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    # 개발 Compose에서 app static CSS를 제공하기 위한 Django 내장 앱(새 패키지 아님).
    "django.contrib.staticfiles",
    # Google OAuth(django-allauth). 직접 토큰 교환을 구현하지 않는다.
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "trading",
]

SITE_ID = 1

# 같은 origin에서 화면과 JSON API를 제공하므로 CORS 미들웨어를 두지 않는다(T-010: 세션 로그인 사용).
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

ROOT_URLCONF = "jumong.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    },
]

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth.backends.AuthenticationBackend",
]

# 로그인 흐름. 비로그인 HTML은 /login/으로 이동하고, 로그인 성공 후 대시보드로 보낸다.
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
ACCOUNT_LOGOUT_REDIRECT_URL = "/login/"

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

# app static CSS 제공(개발용 최소 설정). production static 배포(STATIC_ROOT/CDN)는 범위 밖.
STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"

# --- 도메인 설정값(설정 계층에서만 읽는다) -----------------------------------
# 시장 데이터 제공처(T-002). pykrx만 승인된 제공처다.
MARKET_DATA_PROVIDER = os.environ.get("MARKET_DATA_PROVIDER", "")

# KRX 로그인 자격증명(T-008). pykrx 인증 요청에 필요할 수 있다. 존재 여부만 판정에 쓰고
# 값·길이·마스킹을 반환·표시·로그에 넣지 않는다. 실제 값은 로컬 .env에만 둔다.
KRX_ID = os.environ.get("KRX_ID", "")
KRX_PW = os.environ.get("KRX_PW", "")

# 가상 거래 정책(T-003). 원시 문자열로 두고 trading.config에서 형식·범위를 검증한다.
VIRTUAL_INITIAL_CASH_KRW = os.environ.get("VIRTUAL_INITIAL_CASH_KRW")
VIRTUAL_BUY_FEE_RATE = os.environ.get("VIRTUAL_BUY_FEE_RATE")
VIRTUAL_SELL_FEE_RATE = os.environ.get("VIRTUAL_SELL_FEE_RATE")
VIRTUAL_SELL_TAX_RATE = os.environ.get("VIRTUAL_SELL_TAX_RATE")
VIRTUAL_SLIPPAGE_BPS = os.environ.get("VIRTUAL_SLIPPAGE_BPS")
VIRTUAL_TRADING_POLICY_VERSION = os.environ.get("VIRTUAL_TRADING_POLICY_VERSION")

# --- Google OAuth(T-010) -----------------------------------------------------
# Client ID·Secret·초기 소유자 이메일은 .env와 설정 계층에서만 읽는다. 값·길이·마스킹을
# template·response·로그·DB에 넣지 않는다. 두 OAuth 값이 모두 있을 때만 provider를 구성한다.
GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")
# 기존 단일 가상계좌를 1회 연결할 수 있는 본인 Google 이메일(없으면 legacy 연결 비활성).
INITIAL_OWNER_GOOGLE_EMAIL = os.environ.get("INITIAL_OWNER_GOOGLE_EMAIL", "")

# Client ID·Secret은 DB SocialApp이 아니라 설정 기반 APPS에만 둔다(두 값이 모두 있을 때만).
_GOOGLE_APPS = (
    [{"client_id": GOOGLE_OAUTH_CLIENT_ID, "secret": GOOGLE_OAUTH_CLIENT_SECRET, "key": ""}]
    if GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET
    else []
)
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "SCOPE": ["openid", "email", "profile"],  # 최소 identity scope만
        "AUTH_PARAMS": {"access_type": "online"},  # refresh token 목적의 offline 미사용
        "OAUTH_PKCE_ENABLED": True,
        "APPS": _GOOGLE_APPS,
    }
}
# 신원 확인용 소셜 로그인만 사용한다. 비밀번호 로그인·이메일 인증 메일은 쓰지 않는다.
SOCIALACCOUNT_AUTO_SIGNUP = True
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_LOGIN_ON_GET = False  # 소셜 로그인 시작은 CSRF 보호 POST로만
