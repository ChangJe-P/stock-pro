"""주몽 backend FastAPI 애플리케이션."""

from fastapi import FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import check_database
from .market_data import router as market_data_router
from .virtual_account import router as virtual_account_router
from .virtual_orders import router as virtual_orders_router

settings = get_settings()

app = FastAPI(title="주몽 backend")

if settings.cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(market_data_router)
app.include_router(virtual_account_router)
app.include_router(virtual_orders_router)


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
