"""T-002 시장 데이터 수집·조회(Django ORM 이식).

승인된 유일한 수집 수단은 pykrx 패키지 호출이다. 직접 HTTP·다른 제공처·키를 쓰지 않는다.
조회 GET은 외부 수집을 시작하지 않는다. 가격·거래량은 KRW 정수로 저장한다.
"""

import hashlib
import logging
import uuid
from collections import Counter
from datetime import date, datetime, timezone

from django.db import transaction

from .config import market_data_configured
from .errors import ApiError
from .models import DailyPrice, MarketDataCollectionRun

logger = logging.getLogger("jumong.market_data")

DATA_SOURCE = "pykrx"
ADJUSTED = False  # 수집 시점의 비조정 가격을 저장한다.

_COLUMN_OPEN = "시가"
_COLUMN_HIGH = "고가"
_COLUMN_LOW = "저가"
_COLUMN_CLOSE = "종가"
_COLUMN_VOLUME = "거래량"


def fetch_ohlcv(ticker: str, from_date: date, to_date: date):
    """pykrx로 한 종목·기간의 일봉 OHLCV DataFrame을 가져온다(테스트에서 mock)."""
    from pykrx import stock  # 지연 임포트

    return stock.get_market_ohlcv(
        from_date.strftime("%Y%m%d"),
        to_date.strftime("%Y%m%d"),
        ticker,
        adjusted=ADJUSTED,
    )


def compute_raw_hash(df) -> str:
    serialized = df.sort_index().to_csv().encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def validate_and_transform(df, ticker: str, from_date: date, to_date: date):
    """반환 데이터를 검증해 유효 행과 제외 행(사유 포함)으로 나눈다."""
    valid: list[dict] = []
    excluded: list[dict] = []
    seen_dates: set = set()

    for idx, row in df.iterrows():
        trade_date = idx.date() if hasattr(idx, "date") else idx

        # 중복 거래일은 행 품질과 무관하게 먼저 추적한다(원본 중복 미은닉).
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
                "ticker": ticker, "trade_date": trade_date,
                "open_price": open_p, "high_price": high_p, "low_price": low_p,
                "close_price": close_p, "volume": volume,
            }
        )

    return valid, excluded


def _decide_status(returned: int, valid: int, excluded: int):
    if valid > 0 and excluded == 0:
        return "success", None
    if valid > 0:
        return "partial", f"excluded_rows={excluded}"
    if returned == 0:
        return "partial", "no_data_in_range"
    return "partial", "all_rows_excluded"


def summarize_excluded(excluded_rows: list[dict]) -> dict:
    return dict(Counter(e["reason"] for e in excluded_rows))


def store_collection(ticker, from_date, to_date, df, valid_rows, excluded_rows) -> dict:
    """유효 행을 upsert하고 실행 기록을 남긴다. 하나의 트랜잭션으로 처리한다."""
    run_id = uuid.uuid4().hex
    collected_at = datetime.now(timezone.utc)
    raw_hash = compute_raw_hash(df)
    returned = len(df)
    inserted = updated = 0

    with transaction.atomic():
        for r in valid_rows:
            _, created = DailyPrice.objects.update_or_create(
                ticker=r["ticker"], trade_date=r["trade_date"],
                defaults={
                    "open_price": r["open_price"], "high_price": r["high_price"],
                    "low_price": r["low_price"], "close_price": r["close_price"],
                    "volume": r["volume"], "data_source": DATA_SOURCE, "adjusted": ADJUSTED,
                    "collected_at": collected_at, "collection_run_id": run_id,
                },
            )
            if created:
                inserted += 1
            else:
                updated += 1

        run_status, failure_reason = _decide_status(returned, len(valid_rows), len(excluded_rows))
        reasons = summarize_excluded(excluded_rows)
        MarketDataCollectionRun.objects.create(
            run_id=run_id, data_source=DATA_SOURCE, ticker=ticker, from_date=from_date,
            to_date=to_date, collected_at=collected_at, raw_hash=raw_hash,
            returned_rows=returned, inserted_rows=inserted, updated_rows=updated,
            excluded_rows=len(excluded_rows), status=run_status,
            failure_reason=failure_reason, excluded_reasons=reasons,
        )

    return {
        "run_id": run_id, "ticker": ticker, "from_date": from_date, "to_date": to_date,
        "data_source": DATA_SOURCE, "adjusted": ADJUSTED, "collected_at": collected_at,
        "raw_hash": raw_hash, "returned_rows": returned, "inserted_rows": inserted,
        "updated_rows": updated, "excluded_rows": len(excluded_rows), "status": run_status,
        "failure_reason": failure_reason, "excluded_reasons": reasons, "excluded": excluded_rows,
    }


def record_failed_fetch(ticker, from_date, to_date) -> str | None:
    """외부 조회 실패도 실패 실행으로 남긴다. 안전한 사유만 저장한다."""
    run_id = uuid.uuid4().hex
    try:
        MarketDataCollectionRun.objects.create(
            run_id=run_id, data_source=DATA_SOURCE, ticker=ticker, from_date=from_date,
            to_date=to_date, collected_at=datetime.now(timezone.utc), raw_hash="",
            returned_rows=0, inserted_rows=0, updated_rows=0, excluded_rows=0,
            status="failed", failure_reason="external_fetch_failed", excluded_reasons={},
        )
        return run_id
    except Exception:
        logger.warning("실패 실행 기록 저장 실패")
        return None


def collect_daily_prices(ticker, from_date, to_date) -> dict:
    if not market_data_configured():
        raise ApiError(503, "시장 데이터 수집이 설정되지 않았습니다. MARKET_DATA_PROVIDER=pykrx가 필요합니다.")
    try:
        df = fetch_ohlcv(ticker, from_date, to_date)
    except Exception:
        logger.warning("pykrx 조회 실패")
        record_failed_fetch(ticker, from_date, to_date)
        raise ApiError(502, "시장 데이터 제공처 조회에 실패했습니다.")

    valid_rows, excluded_rows = validate_and_transform(df, ticker, from_date, to_date)
    return store_collection(ticker, from_date, to_date, df, valid_rows, excluded_rows)


def query_daily_prices(ticker, from_date, to_date) -> list[dict]:
    """저장된 일봉을 거래일 오름차순으로 조회한다. 외부 수집을 시작하지 않는다."""
    qs = (
        DailyPrice.objects.filter(ticker=ticker, trade_date__gte=from_date, trade_date__lte=to_date)
        .order_by("trade_date", "id")
    )
    return [
        {
            "ticker": p.ticker, "trade_date": p.trade_date, "open_price": p.open_price,
            "high_price": p.high_price, "low_price": p.low_price, "close_price": p.close_price,
            "volume": p.volume, "data_source": p.data_source, "adjusted": p.adjusted,
            "collected_at": p.collected_at,
        }
        for p in qs
    ]


def stored_unadjusted_price_exists(ticker, trade_date) -> bool:
    """해당 종목·거래일에 저장된 비조정 일봉이 있는지 확인한다(외부 수집 없음)."""
    return DailyPrice.objects.filter(ticker=ticker, trade_date=trade_date, adjusted=False).exists()


def earliest_unadjusted_open_after(ticker, decision_trade_date) -> dict | None:
    """결정 거래일보다 엄격히 뒤인 가장 이른 비조정 일봉을 반환한다(없으면 None)."""
    return (
        DailyPrice.objects.filter(ticker=ticker, trade_date__gt=decision_trade_date, adjusted=False)
        .order_by("trade_date", "id")
        .values("trade_date", "open_price", "data_source", "adjusted", "collection_run_id")
        .first()
    )
