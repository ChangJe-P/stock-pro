"""DB 연결 확인. 연결 문자열이나 비밀값을 로그에 남기지 않는다."""

import logging

import psycopg

from .config import get_settings

logger = logging.getLogger("jumong.db")


def check_database() -> bool:
    """PostgreSQL에 짧게 접속해 SELECT 1을 실행한다.

    성공하면 True, 실패하면 False를 반환한다. 실패해도 예외 메시지에
    연결 문자열이 섞이지 않도록 일반 경고만 남긴다.
    """
    settings = get_settings()
    try:
        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()
        return True
    except Exception:
        logger.warning("데이터베이스 연결 확인 실패")
        return False
