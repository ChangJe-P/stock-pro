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
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from . import accounts, market_data, orders, portfolio
from .accounts import ACCOUNT_KIND, DISCLAIMER
from .config import VirtualPolicyError, load_virtual_policy, market_data_configured
from .errors import ApiError
from .models import MarketDataCollectionRun, VirtualAccount, VirtualBuyOrder

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
    """포트폴리오 평가와 최근 주문을 읽기 전용으로 표시한다.

    포트폴리오 계산·조회는 읽기 전용이다. 외부 수집·계좌 초기화·주문 체결·원장 쓰기를
    시작하지 않는다. DB 오류·계좌 없음·보유 없음·계산 불가를 구별해 안내한다.
    """
    context = {"account": None, "portfolio": None, "recent_orders": [], "disclaimer": DISCLAIMER, "db_error": False}
    try:
        account = VirtualAccount.objects.first()
        if account is not None:
            context["account"] = account
            context["portfolio"] = portfolio.compute_portfolio(account)
            context["recent_orders"] = list(VirtualBuyOrder.objects.order_by("-created_at", "-id")[:20])
    except Exception:
        # DB 미준비 등: 초기화·수집을 시도하지 않고 안내만 표시한다.
        context["db_error"] = True
    return render(request, "trading/dashboard.html", context)


# --- 시작·데이터 준비 화면(T-007) --------------------------------------------

def _setup_context() -> dict:
    """GET/POST가 공유하는 읽기 전용 컨텍스트. 계좌·정책·설정만 읽고 아무 것도 쓰지 않는다."""
    ctx = {
        "disclaimer": DISCLAIMER,
        "db_error": False,
        "account": None,
        "available_cash_krw": None,
        "policy": None,        # 계좌 없음: 검증된 정책의 시작 현금·버전
        "policy_error": None,  # 정책 설정 오류(값 노출 없는 안전한 메시지)
        "market_configured": False,
        "adjusted_label": "비조정 (adjusted=False)",
    }
    try:
        account = VirtualAccount.objects.first()
        if account is not None:
            ctx["account"] = account
            ctx["available_cash_krw"] = accounts.available_cash(account)
        else:
            # 계좌가 없을 때만 검증된 정책에서 시작 현금·버전을 읽어 안내한다(숫자 하드코딩 없음).
            try:
                policy = load_virtual_policy()
                ctx["policy"] = {
                    "initial_cash_krw": policy.initial_cash_krw,
                    "policy_version": policy.policy_version,
                }
            except VirtualPolicyError as exc:
                ctx["policy_error"] = str(exc)
        ctx["market_configured"] = market_data_configured()
    except Exception:
        # DB 미준비 등: 계좌 생성·수집을 시도하지 않고 안내만 표시한다.
        ctx["db_error"] = True
    return ctx


@require_http_methods(["GET"])
def setup(request):
    """읽기 전용 시작·데이터 준비 화면. 계좌·원장·가격 행을 쓰거나 pykrx를 호출하지 않는다."""
    ctx = _setup_context()
    # 수집 실행 결과 표시(있을 때만). 기존 실행 기록을 읽을 뿐 외부 수집을 시작하지 않는다.
    run_id = request.GET.get("collection_run")
    if run_id and not ctx["db_error"]:
        ctx["collection_run_id"] = run_id
        run = MarketDataCollectionRun.objects.filter(run_id=run_id).first()
        if run is None:
            ctx["collection_missing"] = True  # 없거나 형식이 잘못된 run_id: 안전한 안내
        else:
            ctx["collection_run"] = run
    return render(request, "trading/setup.html", ctx)


@require_http_methods(["POST"])
def setup_account_initialize(request):
    """CSRF 보호 form 제출로만 최초 계좌를 만든다. 반복 제출은 기존 계좌를 재설정하지 않는다."""
    try:
        accounts.initialize_account()  # one-time 초기화 규칙 재사용
    except ApiError as exc:
        ctx = _setup_context()
        ctx["account_error"] = exc.detail
        return render(request, "trading/setup.html", ctx, status=exc.status_code)
    # PRG: 새로고침으로 POST가 반복되지 않게 303으로 GET /setup에 이동한다.
    response = HttpResponseRedirect(reverse("setup"))
    response.status_code = 303
    return response


@require_http_methods(["POST"])
def setup_market_data_collect(request):
    """CSRF 보호 form 제출로만 한 종목·기간의 일봉을 수집한다. 입력 검증은 T-002 규칙을 재사용한다."""
    form = {
        "ticker": request.POST.get("ticker", ""),
        "from_date": request.POST.get("from_date", ""),
        "to_date": request.POST.get("to_date", ""),
    }
    # 1) 서버 검증. 실패 시 pykrx를 호출하지 않고 422 HTML로 같은 화면에 오류를 표시한다.
    try:
        ticker = _require_ticker(form["ticker"])
        from_date = _require_date(form["from_date"], "from_date")
        to_date = _require_date(form["to_date"], "to_date")
        if from_date > to_date:
            raise ApiError(422, "from_date는 to_date보다 늦을 수 없습니다.")
    except ApiError as exc:
        ctx = _setup_context()
        ctx["collect_error"] = exc.detail
        ctx["collect_form"] = form
        return render(request, "trading/setup.html", ctx, status=exc.status_code)
    # 2) 유효 입력에서만 기존 수집 함수를 한 번 호출한다(설정 확인·pykrx는 함수 내부).
    try:
        result = market_data.collect_daily_prices(ticker, from_date, to_date)
    except ApiError as exc:
        # 설정 오류(503)·외부 조회 실패(502)를 값 노출 없이 구분해 표시한다. 다른 제공처·재시도 없음.
        ctx = _setup_context()
        ctx["collect_error"] = exc.detail
        ctx["collect_form"] = form
        return render(request, "trading/setup.html", ctx, status=exc.status_code)
    # PRG: 수집 실행 기록을 읽어 표시하도록 303으로 이동한다.
    response = HttpResponseRedirect(reverse("setup") + f"?collection_run={result['run_id']}")
    response.status_code = 303
    return response
