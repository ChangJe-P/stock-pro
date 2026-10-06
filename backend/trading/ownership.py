"""T-010 사용자별 계좌 소유권·legacy 연결·운영자 판정.

전역 `objects.first()` 대신 로그인 사용자의 계좌만 조회한다. 기존 단일 계좌는 허용된 본인
Google 이메일이 명시적 POST로 1회 연결할 때만 소유자를 설정한다. 다른 사용자에게는 legacy
계좌의 존재·ID·잔액·주문을 노출하지 않는다.
"""

from django.conf import settings
from django.db import transaction

from .errors import ApiError
from .models import VirtualAccount


def _normalize_email(value) -> str:
    return (value or "").strip().lower()


def initial_owner_email() -> str:
    return _normalize_email(settings.INITIAL_OWNER_GOOGLE_EMAIL)


def is_initial_owner(user) -> bool:
    """INITIAL_OWNER_GOOGLE_EMAIL과 대소문자·공백 무시 일치하는 로그인 사용자인지."""
    owner_email = initial_owner_email()
    if not owner_email or user is None or not user.is_authenticated:
        return False
    return _normalize_email(getattr(user, "email", "")) == owner_email


def can_manage_market_data(user) -> bool:
    """초기 소유자(운영자)만 수동 일봉 수집을 실행할 수 있다."""
    return is_initial_owner(user)


def get_account_for_user(user, *, for_update: bool = False):
    """로그인 사용자의 계좌만 조회한다(없으면 None)."""
    if user is None or not user.is_authenticated:
        return None
    qs = VirtualAccount.objects.filter(owner=user)
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def _legacy_account(*, for_update: bool = False):
    """소유자 없는 기존 단일 계좌(있으면)."""
    qs = VirtualAccount.objects.filter(owner__isnull=True)
    if for_update:
        qs = qs.select_for_update()
    return qs.first()


def can_claim_legacy(user) -> bool:
    """초기 소유자이고, 아직 계좌가 없으며, 연결 가능한 legacy 계좌가 있을 때만 True."""
    if not is_initial_owner(user):
        return False
    if get_account_for_user(user) is not None:
        return False
    return _legacy_account() is not None


def claim_legacy_account(user):
    """허용된 본인만, 트랜잭션·행 잠금으로 owner 없는 계좌 1개를 1회 연결한다.

    - 권한 없는 사용자: 기록 존재를 노출하지 않는 403.
    - 이미 계좌가 있으면 추가 생성·재설정 없이 기존 계좌를 반환한다(멱등).
    """
    if not is_initial_owner(user):
        # 존재 여부를 밝히지 않는다. 권한 자체가 없다는 안전한 메시지만.
        raise ApiError(403, "기존 가상 학습 기록을 연결할 권한이 없습니다.")
    with transaction.atomic():
        existing = get_account_for_user(user, for_update=True)
        if existing is not None:
            return existing  # 이미 연결됨. 멱등.
        legacy = _legacy_account(for_update=True)
        if legacy is None:
            raise ApiError(404, "연결할 기존 가상 학습 기록이 없습니다.")
        legacy.owner = user
        legacy.save(update_fields=["owner"])
        return legacy
