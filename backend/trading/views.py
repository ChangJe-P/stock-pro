"""HTTP 계층(T-010): 로그인 사용자 범위의 HTML·JSON 응답.

- 비로그인 HTML은 /login/으로 이동, 비로그인 JSON API는 401 JSON.
- 계좌·주문·수집 POST는 세션 CSRF 보호를 사용한다(csrf_exempt 제거).
- 서비스에 request.user를 전달해 소유 계좌·주문만 읽고, 타인 주문 ID는 404로 처리한다.
- /health만 비로그인 공개. 오류 body는 안전한 detail만 담고 비밀값·연결 문자열을 넣지 않는다.
"""

import json
import re
from datetime import date
from functools import wraps

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.serializers.json import DjangoJSONEncoder
from django.db import DatabaseError, connection
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_http_methods

from . import accounts, market_data, orders, ownership, portfolio
from .accounts import DISCLAIMER
from .config import VirtualPolicyError, load_virtual_policy, market_data_configured
from .errors import ApiError
from .models import MarketDataCollectionRun, VirtualBuyOrder

_TICKER = re.compile(r"^\d{6}$")


def _json(data, status=200):
    return JsonResponse(
        data, status=status, encoder=DjangoJSONEncoder, json_dumps_params={"ensure_ascii": False}
    )


def _error(exc: ApiError):
    return _json({"detail": exc.detail}, status=exc.status_code)


def _login_required_json(view):
    """JSON API 경계.

    - 비로그인 요청은 CSRF 검사보다 먼저 정확히 401 JSON을 반환한다(상태 변경 없음).
      그래서 view 전체를 csrf_exempt로 두어 CsrfViewMiddleware를 건너뛴다.
    - 로그인 사용자의 상태 변경(POST 등)은 csrf_protect로 CSRF를 강제한다(없으면 403).
      안전 메서드(GET)에는 csrf_protect가 영향을 주지 않는다.
    """
    protected = csrf_protect(view)

    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return _json({"detail": "로그인이 필요합니다."}, status=401)
        return protected(request, *args, **kwargs)

    return wrapper


def _parse_json_body(request) -> dict:
    try:
        parsed = json.loads(request.body or b"{}")
    except (ValueError, TypeError):
        raise ApiError(422, "요청 본문이 올바른 JSON이 아닙니다.")
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


def _google_oauth_configured() -> bool:
    # 두 OAuth 값이 모두 있을 때만 로그인 시작을 허용한다(값·길이·마스킹은 노출하지 않는다).
    return bool(settings.GOOGLE_OAUTH_CLIENT_ID) and bool(settings.GOOGLE_OAUTH_CLIENT_SECRET)


# --- 상태 확인(비로그인 공개) ------------------------------------------------

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


# --- 로그인/로그아웃 ---------------------------------------------------------

@require_http_methods(["GET"])
def login_view(request):
    """Google 로그인 화면. 설정이 없으면 안전한 안내만 보이고 OAuth를 시작하지 않는다."""
    if request.user.is_authenticated:
        return HttpResponseRedirect(reverse("dashboard"))
    return render(request, "trading/login.html", {
        "disclaimer": DISCLAIMER,
        "google_configured": _google_oauth_configured(),
    })


@require_http_methods(["POST"])
def logout_view(request):
    """CSRF 보호 POST 로그아웃."""
    logout(request)
    return HttpResponseRedirect(reverse("login"))


# --- 시장 데이터(로그인 필수; 수집은 운영자만) --------------------------------

@_login_required_json
@require_http_methods(["POST"])
def market_data_collect(request):
    try:
        # 초기 소유자(운영자)만 수집한다. 그 외는 fetch 호출 전에 403.
        if not ownership.can_manage_market_data(request.user):
            raise ApiError(403, "일봉 수집 권한이 없습니다.")
        body = _parse_json_body(request)
        ticker = _require_ticker(body.get("ticker"))
        from_date = _require_date(body.get("from_date"), "from_date")
        to_date = _require_date(body.get("to_date"), "to_date")
        if from_date > to_date:
            raise ApiError(422, "from_date는 to_date보다 늦을 수 없습니다.")
        return _json(market_data.collect_daily_prices(ticker, from_date, to_date))
    except ApiError as exc:
        return _error(exc)


@_login_required_json
@require_http_methods(["GET"])
def market_data_list(request):
    # 저장된 공용 일봉은 로그인 사용자가 읽을 수 있다(외부 호출 없음).
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


# --- 가상계좌(로그인 사용자 범위) --------------------------------------------

@_login_required_json
@require_http_methods(["POST"])
def virtual_account_initialize(request):
    try:
        return _json(accounts.initialize_account(request.user))
    except ApiError as exc:
        return _error(exc)


@_login_required_json
@require_http_methods(["GET"])
def virtual_account_detail(request):
    try:
        return _json(accounts.get_account(request.user))
    except ApiError as exc:
        return _error(exc)


@_login_required_json
@require_http_methods(["GET"])
def virtual_account_cash_ledger(request):
    try:
        return _json(accounts.list_cash_ledger(request.user))
    except ApiError as exc:
        return _error(exc)


# --- 가상 매수 주문(로그인 사용자 범위) --------------------------------------

@_login_required_json
@require_http_methods(["GET", "POST"])
def virtual_orders(request):
    try:
        if request.method == "POST":
            body = _parse_json_body(request)
            ticker = _require_ticker(body.get("ticker"))
            quantity = _require_quantity(body.get("quantity"))
            decision = _require_date(body.get("decision_trade_date"), "decision_trade_date")
            return _json(orders.create_order(request.user, ticker, quantity, decision))
        return _json(orders.list_orders(request.user))
    except ApiError as exc:
        return _error(exc)


@_login_required_json
@require_http_methods(["POST"])
def virtual_order_execute(request, order_id: int):
    try:
        return _json(orders.execute_order(request.user, order_id))
    except ApiError as exc:
        return _error(exc)


# --- 읽기 전용 대시보드(로그인 필수) -----------------------------------------

@login_required(login_url="/login/")
@require_http_methods(["GET"])
def dashboard(request):
    """로그인 사용자의 포트폴리오·최근 주문만 읽기 전용으로 표시한다."""
    context = {
        "account": None, "portfolio": None, "recent_orders": [], "disclaimer": DISCLAIMER,
        "db_error": False, "user_email": request.user.email, "can_claim_legacy": False,
    }
    try:
        account = ownership.get_account_for_user(request.user)
        context["can_claim_legacy"] = ownership.can_claim_legacy(request.user)
        if account is not None:
            context["account"] = account
            context["portfolio"] = portfolio.compute_portfolio(account)
            context["recent_orders"] = list(
                VirtualBuyOrder.objects.filter(account=account).order_by("-created_at", "-id")[:20]
            )
    except DatabaseError:
        context["db_error"] = True
    return render(request, "trading/dashboard.html", context)


# --- 시작·데이터 준비 화면(로그인 사용자 범위) -------------------------------

def _setup_context(user) -> dict:
    """GET/POST가 공유하는 읽기 전용 컨텍스트. 로그인 사용자의 계좌·정책·설정만 읽는다."""
    ctx = {
        "disclaimer": DISCLAIMER,
        "db_error": False,
        "account": None,
        "available_cash_krw": None,
        "policy": None,
        "policy_error": None,
        "market_configured": False,
        "can_manage_market_data": ownership.can_manage_market_data(user),
        "can_claim_legacy": False,
        "user_email": getattr(user, "email", ""),
        "adjusted_label": "비조정 (adjusted=False)",
    }
    try:
        account = ownership.get_account_for_user(user)
        ctx["can_claim_legacy"] = ownership.can_claim_legacy(user)
        if account is not None:
            ctx["account"] = account
            ctx["available_cash_krw"] = accounts.available_cash(account)
        else:
            try:
                policy = load_virtual_policy()
                ctx["policy"] = {
                    "initial_cash_krw": policy.initial_cash_krw,
                    "policy_version": policy.policy_version,
                }
            except VirtualPolicyError as exc:
                ctx["policy_error"] = str(exc)
        ctx["market_configured"] = market_data_configured()
    except DatabaseError:
        ctx["db_error"] = True
    return ctx


def _db_error_response(request):
    return render(
        request, "trading/setup.html", {"disclaimer": DISCLAIMER, "db_error": True}, status=503
    )


@login_required(login_url="/login/")
@require_http_methods(["GET"])
def setup(request):
    """읽기 전용 시작·데이터 준비 화면. 계좌·원장·가격 행을 쓰거나 pykrx를 호출하지 않는다."""
    ctx = _setup_context(request.user)
    run_id = request.GET.get("collection_run")
    if run_id and not ctx["db_error"]:
        ctx["collection_run_id"] = run_id
        try:
            run = MarketDataCollectionRun.objects.filter(run_id=run_id).first()
        except DatabaseError:
            ctx["db_error"] = True
        else:
            if run is None:
                ctx["collection_missing"] = True
            else:
                ctx["collection_run"] = run
    status = 503 if ctx["db_error"] else 200
    return render(request, "trading/setup.html", ctx, status=status)


@login_required(login_url="/login/")
@require_http_methods(["POST"])
def setup_account_initialize(request):
    """CSRF 보호 form 제출로만 로그인 사용자의 계좌를 1회 만든다."""
    try:
        accounts.initialize_account(request.user)
    except ApiError as exc:
        ctx = _setup_context(request.user)
        ctx["account_error"] = exc.detail
        return render(request, "trading/setup.html", ctx, status=exc.status_code)
    except DatabaseError:
        return _db_error_response(request)
    response = HttpResponseRedirect(reverse("setup"))
    response.status_code = 303
    return response


@login_required(login_url="/login/")
@require_http_methods(["POST"])
def setup_legacy_claim(request):
    """허용된 본인만 기존 가상 학습 기록을 명시적 1회 연결한다(CSRF 보호, PRG)."""
    try:
        ownership.claim_legacy_account(request.user)
    except ApiError as exc:
        ctx = _setup_context(request.user)
        ctx["account_error"] = exc.detail
        return render(request, "trading/setup.html", ctx, status=exc.status_code)
    except DatabaseError:
        return _db_error_response(request)
    response = HttpResponseRedirect(reverse("dashboard"))
    response.status_code = 303
    return response


@login_required(login_url="/login/")
@require_http_methods(["POST"])
def setup_market_data_collect(request):
    """초기 소유자만 CSRF 보호 form으로 한 종목·기간의 일봉을 수집한다."""
    # 운영자가 아니면 입력 처리·fetch 전에 403으로 끝낸다.
    if not ownership.can_manage_market_data(request.user):
        ctx = _setup_context(request.user)
        ctx["collect_error"] = "일봉 수집 권한이 없습니다."
        return render(request, "trading/setup.html", ctx, status=403)

    form = {
        "ticker": request.POST.get("ticker", ""),
        "from_date": request.POST.get("from_date", ""),
        "to_date": request.POST.get("to_date", ""),
    }
    try:
        ticker = _require_ticker(form["ticker"])
        from_date = _require_date(form["from_date"], "from_date")
        to_date = _require_date(form["to_date"], "to_date")
        if from_date > to_date:
            raise ApiError(422, "from_date는 to_date보다 늦을 수 없습니다.")
    except ApiError as exc:
        ctx = _setup_context(request.user)
        ctx["collect_error"] = exc.detail
        ctx["collect_form"] = form
        return render(request, "trading/setup.html", ctx, status=exc.status_code)
    try:
        result = market_data.collect_daily_prices(ticker, from_date, to_date)
    except ApiError as exc:
        ctx = _setup_context(request.user)
        ctx["collect_error"] = exc.detail
        ctx["collect_form"] = form
        return render(request, "trading/setup.html", ctx, status=exc.status_code)
    except DatabaseError:
        return _db_error_response(request)
    response = HttpResponseRedirect(reverse("setup") + f"?collection_run={result['run_id']}")
    response.status_code = 303
    return response
