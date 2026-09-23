"""HTTP 계층: 기존 JSON API 경로·상태 코드·응답 의미를 유지하고 읽기 전용 대시보드를 렌더링한다.

JSON POST view에는 비로그인 로컬 API 호환을 위해 CSRF 예외를 명시한다(향후 form은 CSRF 토큰 사용).
오류 body는 안전한 detail 메시지만 담고 비밀값·연결 문자열을 넣지 않는다.
"""

import json
import re
from datetime import date

from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import accounts, market_data, orders
from .accounts import ACCOUNT_KIND, DISCLAIMER
from .errors import ApiError
from .models import VirtualAccount, VirtualBuyOrder

_TICKER = re.compile(r"^\d{6}$")


def _json(data, status=200):
    return JsonResponse(
        data, status=status, encoder=DjangoJSONEncoder, json_dumps_params={"ensure_ascii": False}
    )


def _error(exc: ApiError):
    return _json({"detail": exc.detail}, status=exc.status_code)


def _parse_json_body(request) -> dict:
    try:
        parsed = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        raise ApiError(422, "요청 본문이 올바른 JSON이 아닙니다.")
    # 문법상 유효해도 객체(dict)가 아니면(예: 배열·문자열) 안전한 422로 거절한다.
    # 그러지 않으면 호출부의 body.get(...)에서 예외가 나 500이 된다.
    if not isinstance(parsed, dict):
        raise ApiError(422, "요청 본문은 JSON 객체여야 합니다.")
    return parsed


def _require_ticker(value) -> str:
    if not isinstance(value, str) or not _TICKER.match(value):
        raise ApiError(422, "ticker는 숫자 6자리여야 합니다.")
    return value


def _require_quantity(value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ApiError(422, "quantity는 양수 정수여야 합니다.")
    return value


def _require_date(value, name: str) -> date:
    if not isinstance(value, str):
        raise ApiError(422, f"{name}는 ISO 날짜(YYYY-MM-DD)여야 합니다.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ApiError(422, f"{name}는 ISO 날짜(YYYY-MM-DD)여야 합니다.")


# --- 상태 확인 ---------------------------------------------------------------

@require_http_methods(["GET"])
def health(request):
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        db_ok = True
    except Exception:
        db_ok = False
    if not db_ok:
        return _json({"status": "unhealthy", "app_env": settings.APP_ENV, "database": "unavailable"}, status=503)
    return _json({"status": "ok", "app_env": settings.APP_ENV, "database": "connected"})


# --- 시장 데이터 -------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def market_data_collect(request):
    try:
        body = _parse_json_body(request)
        ticker = _require_ticker(body.get("ticker"))
        from_date = _require_date(body.get("from_date"), "from_date")
        to_date = _require_date(body.get("to_date"), "to_date")
        if from_date > to_date:
            raise ApiError(422, "from_date는 to_date보다 늦을 수 없습니다.")
        return _json(market_data.collect_daily_prices(ticker, from_date, to_date))
    except ApiError as exc:
        return _error(exc)


@require_http_methods(["GET"])
def market_data_list(request):
    try:
        ticker = _require_ticker(request.GET.get("ticker"))
        from_date = _require_date(request.GET.get("from_date"), "from_date")
        to_date = _require_date(request.GET.get("to_date"), "to_date")
        if from_date > to_date:
            raise ApiError(422, "from_date는 to_date보다 늦을 수 없습니다.")
        rows = market_data.query_daily_prices(ticker, from_date, to_date)
        return _json({"ticker": ticker, "from_date": from_date, "to_date": to_date, "rows": rows})
    except ApiError as exc:
        return _error(exc)


# --- 가상계좌 ---------------------------------------------------------------

@csrf_exempt
@require_http_methods(["POST"])
def virtual_account_initialize(request):
    try:
        return _json(accounts.initialize_account())
    except ApiError as exc:
        return _error(exc)


@require_http_methods(["GET"])
def virtual_account_detail(request):
    try:
        return _json(accounts.get_account())
    except ApiError as exc:
        return _error(exc)


@require_http_methods(["GET"])
def virtual_account_cash_ledger(request):
    try:
        return _json(accounts.list_cash_ledger())
    except ApiError as exc:
        return _error(exc)


# --- 가상 매수 주문 ----------------------------------------------------------

@csrf_exempt
@require_http_methods(["GET", "POST"])
def virtual_orders(request):
    try:
        if request.method == "POST":
            body = _parse_json_body(request)
            ticker = _require_ticker(body.get("ticker"))
            quantity = _require_quantity(body.get("quantity"))
            decision = _require_date(body.get("decision_trade_date"), "decision_trade_date")
            return _json(orders.create_order(ticker, quantity, decision))
        return _json(orders.list_orders())
    except ApiError as exc:
        return _error(exc)


@csrf_exempt
@require_http_methods(["POST"])
def virtual_order_execute(request, order_id: int):
    try:
        return _json(orders.execute_order(order_id))
    except ApiError as exc:
        return _error(exc)


# --- 읽기 전용 대시보드 ------------------------------------------------------

@require_http_methods(["GET"])
def dashboard(request):
    """계좌 요약과 최근 주문을 읽기 전용으로 표시한다.

    외부 수집·계좌 초기화·주문 체결을 자동으로 시작하지 않는다. DB나 계좌가 없어도 안내만 표시한다.
    """
    context = {"account": None, "available_cash_krw": None, "recent_orders": [], "disclaimer": DISCLAIMER, "db_error": False}
    try:
        account = VirtualAccount.objects.first()
        if account is not None:
            context["account"] = account
            context["available_cash_krw"] = accounts.available_cash(account)
            context["recent_orders"] = list(VirtualBuyOrder.objects.order_by("-created_at", "-id")[:20])
    except Exception:
        # DB 미준비 등: 초기화·수집을 시도하지 않고 안내만 표시한다.
        context["db_error"] = True
    return render(request, "trading/dashboard.html", context)
