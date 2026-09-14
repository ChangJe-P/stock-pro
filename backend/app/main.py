"""주몽 backend FastAPI 애플리케이션."""

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import check_database

settings = get_settings()

app = FastAPI(title="주몽 backend")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )


@app.get("/health")
def health(response: Response) -> dict:
    """DB 연결이 확인될 때만 정상(200)으로 보고한다.

    DB에 접속할 수 없으면 503을 반환해 준비되지 않은 상태를 그대로 알린다.
    """
    if not check_database():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "unhealthy",
            "app_env": settings.app_env,
            "database": "unavailable",
        }
    return {
        "status": "ok",
        "app_env": settings.app_env,
        "database": "connected",
    }
