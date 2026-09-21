"""T-002 시장 데이터 수집·조회.

승인된 유일한 수집 수단은 pykrx 패키지 호출이다. 직접 HTTP 요청을 만들지 않고,
API 키·endpoint·요청 제한 변수를 읽거나 로그에 남기지 않는다. pykrx는 pykrx만 사용한다.
가격·거래량은 정수로 저장하고, 연결 문자열·비밀값·원본 응답 전문은 저장·로그하지 않는다.
"""

import hashlib
import logging
import uuid
from collections import Counter
from datetime import date, datetime, timezone

import psycopg
from fastapi import APIRouter, HTTPException, Query, status
from psycopg.rows import dict_row
from psycopg.types.json import Json
from pydantic import BaseModel, Field, model_validator

from .config import get_settings

logger = logging.getLogger("jumong.market_data")

DATA_SOURCE = "pykrx"
# 수집 시점의 비조정 가격을 저장한다(adjusted=False).
ADJUSTED = False

# pykrx 일봉 DataFrame의 한국어 컬럼 이름.
_COLUMN_OPEN = "시가"
_COLUMN_HIGH = "고가"
_COLUMN_LOW = "저가"
_COLUMN_CLOSE = "종가"
_COLUMN_VOLUME = "거래량"

_SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS market_data_collection_runs (
    run_id TEXT PRIMARY KEY,
    data_source TEXT NOT NULL,
    ticker TEXT NOT NULL,
    from_date DATE NOT NULL,
    to_date DATE NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    raw_hash TEXT NOT NULL,
    returned_rows INTEGER NOT NULL,
    inserted_rows INTEGER NOT NULL,
    updated_rows INTEGER NOT NULL,
    excluded_rows INTEGER NOT NULL,
    status TEXT NOT NULL,
    failure_reason TEXT,
    excluded_reasons JSONB NOT NULL DEFAULT '{}'::jsonb
);
-- 기존 DB에도 안전하게 이유별 건수 컬럼을 보강한다(마이그레이션 프레임워크 없이 재실행 안전).
ALTER TABLE market_data_collection_runs
    ADD COLUMN IF NOT EXISTS excluded_reasons JSONB NOT NULL DEFAULT '{}'::jsonb;
CREATE TABLE IF NOT EXISTS daily_prices (
    id BIGSERIAL PRIMARY KEY,
    ticker TEXT NOT NULL,
    trade_date DATE NOT NULL,
    open_price BIGINT NOT NULL,
    high_price BIGINT NOT NULL,
    low_price BIGINT NOT NULL,
    close_price BIGINT NOT NULL,
    volume BIGINT NOT NULL,
    data_source TEXT NOT NULL,
    adjusted BOOLEAN NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL,
    collection_run_id TEXT NOT NULL,
    UNIQUE (ticker, trade_date)
);
"""


# --- 설정 게이트 ------------------------------------------------------------

def _require_configured() -> None:
    """pykrx로 설정되지 않았으면 외부 요청 없이 명시적 오류를 낸다.

    오류 메시지에 비밀값이나 환경변수 값을 넣지 않고, 필요한 설정 이름만 알린다.
    """
    if not get_settings().market_data_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="시장 데이터 수집이 설정되지 않았습니다. MARKET_DATA_PROVIDER=pykrx가 필요합니다.",
        )


# --- DB ---------------------------------------------------------------------

def _connect() -> psycopg.Connection:
    conn = psycopg.connect(get_settings().database_url, connect_timeout=5, row_factory=dict_row)
    with conn.cursor() as cur:
        # 마이그레이션 프레임워크 없이 재실행에 안전한 최소 스키마 초기화.
        cur.execute(_SCHEMA_DDL)
    conn.commit()
    return conn


# --- pykrx 호출 --------------------------------------------------------------

def fetch_ohlcv(ticker: str, from_date: date, to_date: date):
    """pykrx로 한 종목·기간의 일봉 OHLCV DataFrame을 가져온다.

    직접 HTTP 요청을 만들지 않고 pykrx 호출만 사용한다. 테스트는 이 함수를 mock한다.
    """
    from pykrx import stock  # 지연 임포트: 테스트에서 mock 가능하도록.

    return stock.get_market_ohlcv(
        from_date.strftime("%Y%m%d"),
        to_date.strftime("%Y%m%d"),
        ticker,
        adjusted=ADJUSTED,
    )


def compute_raw_hash(df) -> str:
    """원본 DataFrame을 결정적으로 직렬화해 SHA-256 해시를 계산한다."""
    serialized = df.sort_index().to_csv().encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


# --- 검증 --------------------------------------------------------------------

def validate_and_transform(df, ticker: str, from_date: date, to_date: date):
    """반환 데이터를 검증해 유효 행과 제외 행(사유 포함)으로 나눈다.

    검사: 기간 내 날짜, 거래일 중복 없음, 양수 OHLC, `저가<=시가/종가<=고가`,
    거래량 0 이상. 비거래일로 인한 빈 반환은 오류가 아니다.
    """
    valid: list[dict] = []
    excluded: list[dict] = []
    seen_dates: set[date] = set()

    for idx, row in df.iterrows():
        trade_date = idx.date() if hasattr(idx, "date") else idx

        # 중복 거래일은 행 품질과 무관하게 먼저 추적한다. 첫 행이 잘못된 값으로
        # 제외되더라도 같은 날짜의 이후 행은 duplicate_date로 남긴다(원본 중복 미은닉).
        if trade_date in seen_dates:
            excluded.append({"trade_date": str(trade_date), "reason": "duplicate_date"})
            continue
        seen_dates.add(trade_date)

        reason = None
        try:
            open_p = int(row[_COLUMN_OPEN])
            high_p = int(row[_COLUMN_HIGH])
            low_p = int(row[_COLUMN_LOW])
            close_p = int(row[_COLUMN_CLOSE])
            volume = int(row[_COLUMN_VOLUME])
        except (KeyError, ValueError, TypeError):
            excluded.append({"trade_date": str(trade_date), "reason": "malformed_row"})
            continue

        if not (from_date <= trade_date <= to_date):
            reason = "out_of_range"
        elif min(open_p, high_p, low_p, close_p) <= 0:
            reason = "non_positive_price"
        elif not (low_p <= open_p <= high_p and low_p <= close_p <= high_p):
            reason = "invalid_ohlc"
        elif volume < 0:
            reason = "negative_volume"

        if reason:
            excluded.append({"trade_date": str(trade_date), "reason": reason})
            continue

        valid.append(
            {
                "ticker": ticker,
                "trade_date": trade_date,
                "open_price": open_p,
                "high_price": high_p,
                "low_price": low_p,
                "close_price": close_p,
                "volume": volume,
            }
        )

    return valid, excluded


def _decide_status(returned: int, valid: int, excluded: int) -> tuple[str, str | None]:
    if valid > 0 and excluded == 0:
        return "success", None
    if valid > 0:
        return "partial", f"excluded_rows={excluded}"
    if returned == 0:
        return "partial", "no_data_in_range"
    return "partial", "all_rows_excluded"


def summarize_excluded(excluded_rows: list[dict]) -> dict[str, int]:
    """제외 행을 사유별 건수로 집계한다. 값(가격 등)은 담지 않아 안전하다."""
    return dict(Counter(e["reason"] for e in excluded_rows))


# --- 저장 --------------------------------------------------------------------

def _insert_run(cur, run: dict) -> None:
    """수집 실행 기록을 저장한다. 이유별 건수는 JSONB로 남긴다."""
    cur.execute(
        """
        INSERT INTO market_data_collection_runs (
            run_id, data_source, ticker, from_date, to_date, collected_at,
            raw_hash, returned_rows, inserted_rows, updated_rows,
            excluded_rows, status, failure_reason, excluded_reasons
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            run["run_id"], DATA_SOURCE, run["ticker"], run["from_date"], run["to_date"],
            run["collected_at"], run["raw_hash"], run["returned_rows"], run["inserted_rows"],
            run["updated_rows"], run["excluded_rows"], run["status"], run["failure_reason"],
            Json(run["excluded_reasons"]),
        ),
    )


def store_collection(ticker, from_date, to_date, df, valid_rows, excluded_rows):
    """유효 행을 upsert하고 실행 기록을 남긴다. 하나의 트랜잭션으로 처리한다."""
    run_id = uuid.uuid4().hex
    collected_at = datetime.now(timezone.utc)
    raw_hash = compute_raw_hash(df)
    returned = len(df)
    inserted = updated = 0

    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                for r in valid_rows:
                    cur.execute(
                        """
                        INSERT INTO daily_prices (
                            ticker, trade_date, open_price, high_price, low_price,
                            close_price, volume, data_source, adjusted,
                            collected_at, collection_run_id
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        ON CONFLICT (ticker, trade_date) DO UPDATE SET
                            open_price = EXCLUDED.open_price,
                            high_price = EXCLUDED.high_price,
                            low_price = EXCLUDED.low_price,
                            close_price = EXCLUDED.close_price,
                            volume = EXCLUDED.volume,
                            data_source = EXCLUDED.data_source,
                            adjusted = EXCLUDED.adjusted,
                            collected_at = EXCLUDED.collected_at,
                            collection_run_id = EXCLUDED.collection_run_id
                        RETURNING (xmax = 0) AS inserted
                        """,
                        (
                            r["ticker"], r["trade_date"], r["open_price"], r["high_price"],
                            r["low_price"], r["close_price"], r["volume"], DATA_SOURCE,
                            ADJUSTED, collected_at, run_id,
                        ),
                    )
                    if cur.fetchone()["inserted"]:
                        inserted += 1
                    else:
                        updated += 1

                run_status, failure_reason = _decide_status(returned, len(valid_rows), len(excluded_rows))
                run = {
                    "run_id": run_id,
                    "ticker": ticker,
                    "from_date": from_date,
                    "to_date": to_date,
                    "data_source": DATA_SOURCE,
                    "adjusted": ADJUSTED,
                    "collected_at": collected_at,
                    "raw_hash": raw_hash,
                    "returned_rows": returned,
                    "inserted_rows": inserted,
                    "updated_rows": updated,
                    "excluded_rows": len(excluded_rows),
                    "status": run_status,
                    "failure_reason": failure_reason,
                    "excluded_reasons": summarize_excluded(excluded_rows),
                }
                _insert_run(cur, run)
    except psycopg.Error:
        # 연결 문자열이 섞이지 않도록 원본 예외를 응답에 노출하지 않는다.
        logger.warning("시장 데이터 저장 실패")
        raise HTTPException(status_code=500, detail="시장 데이터 저장 중 오류가 발생했습니다.")

    # 응답에는 이유별 건수와 행별 사유를 함께 반환해 검증 결과를 숨기지 않는다.
    return {**run, "excluded": excluded_rows}


def record_failed_fetch(ticker, from_date, to_date) -> str | None:
    """외부 조회 실패도 DB가 정상이면 실패 실행으로 남긴다. 안전한 사유만 저장한다."""
    run = {
        "run_id": uuid.uuid4().hex,
        "ticker": ticker,
        "from_date": from_date,
        "to_date": to_date,
        "collected_at": datetime.now(timezone.utc),
        "raw_hash": "",
        "returned_rows": 0,
        "inserted_rows": 0,
        "updated_rows": 0,
        "excluded_rows": 0,
        "status": "failed",
        "failure_reason": "external_fetch_failed",
        "excluded_reasons": {},
    }
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                _insert_run(cur, run)
        return run["run_id"]
    except psycopg.Error:
        # DB도 접속 불가면 원 실패(502)를 가리지 않도록 조용히 넘어간다.
        logger.warning("실패 실행 기록 저장 실패")
        return None


def query_daily_prices(ticker, from_date, to_date) -> list[dict]:
    """저장된 일봉을 거래일 오름차순으로 조회한다. 외부 수집을 시작하지 않는다."""
    try:
        with _connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticker, trade_date, open_price, high_price, low_price,
                           close_price, volume, data_source, adjusted, collected_at
                    FROM daily_prices
                    WHERE ticker = %s AND trade_date BETWEEN %s AND %s
                    ORDER BY trade_date ASC
                    """,
                    (ticker, from_date, to_date),
                )
                return cur.fetchall()
    except psycopg.Error:
        logger.warning("시장 데이터 조회 실패")
        raise HTTPException(status_code=500, detail="시장 데이터 조회 중 오류가 발생했습니다.")


# --- 오케스트레이션 ----------------------------------------------------------

def collect_daily_prices(ticker, from_date, to_date) -> dict:
    _require_configured()
    try:
        df = fetch_ohlcv(ticker, from_date, to_date)
    except HTTPException:
        raise
    except Exception:
        # 외부 조회 실패. 안전한 사유만 실패 실행으로 남기고 상세 예외는 노출하지 않는다.
        logger.warning("pykrx 조회 실패")
        record_failed_fetch(ticker, from_date, to_date)
        raise HTTPException(status_code=502, detail="시장 데이터 제공처 조회에 실패했습니다.")

    valid_rows, excluded_rows = validate_and_transform(df, ticker, from_date, to_date)
    return store_collection(ticker, from_date, to_date, df, valid_rows, excluded_rows)


# --- API ---------------------------------------------------------------------

_TICKER = r"^\d{6}$"

router = APIRouter(prefix="/market-data/daily-prices", tags=["market-data"])


class CollectRequest(BaseModel):
    ticker: str = Field(pattern=_TICKER)
    from_date: date
    to_date: date

    @model_validator(mode="after")
    def _check_range(self) -> "CollectRequest":
        if self.from_date > self.to_date:
            raise ValueError("from_date는 to_date보다 늦을 수 없습니다.")
        return self


@router.post("/collect")
def collect(req: CollectRequest) -> dict:
    return collect_daily_prices(req.ticker, req.from_date, req.to_date)


@router.get("")
def list_prices(
    ticker: str = Query(pattern=_TICKER),
    from_date: date = Query(),
    to_date: date = Query(),
) -> dict:
    if from_date > to_date:
        raise HTTPException(status_code=422, detail="from_date는 to_date보다 늦을 수 없습니다.")
    rows = query_daily_prices(ticker, from_date, to_date)
    return {"ticker": ticker, "from_date": from_date, "to_date": to_date, "rows": rows}
