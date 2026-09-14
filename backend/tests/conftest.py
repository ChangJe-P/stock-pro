"""테스트용 환경변수. 실제 비밀값이 아니라 로컬 테스트 전용 더미 값이다."""

import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("CORS_ALLOWED_ORIGINS", "http://localhost:3000")
