# Claude Code 구현 요청: T-010-P1 Google OAuth 콜백 인증 백엔드 수정

`codex/oauth` 브랜치에서만 작업해. push, PR 생성, 병합은 하지 마.

## 구현 전 필독

아래를 순서대로 읽고, 충돌하면 `docs/tasks/T-010-P1-google-oauth-callback.md`의 범위와 완료 기준을 우선해.

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/ENVIRONMENT.md`
4. `docs/superpowers/specs/2026-11-12-google-oauth-callback-backend-design.md`
5. `docs/superpowers/plans/2026-11-12-google-oauth-callback-backend.md`
6. `docs/tasks/T-010-google-auth-user-accounts.md`
7. `docs/tasks/T-010-P1-google-oauth-callback.md`
8. `skills/user-owned-virtual-account/SKILL.md`

## 확인된 원인과 최소 수정

실제 Google OAuth callback은 완료 단계까지 도달했지만, `AUTHENTICATION_BACKENDS`가 존재하지 않는 `allauth.account.auth.backends.AuthenticationBackend`를 참조해 500 오류가 났다. django-allauth 65.19.6의 실제 경로는 `allauth.account.auth_backends.AuthenticationBackend`다.

1. 먼저 `backend/trading/test_auth.py`에 현재 설정의 `django.contrib.auth.get_backends()`가 Django `ModelBackend`와 allauth `AuthenticationBackend`를 모두 로드하는 실패 테스트를 추가해. 이 테스트는 수정 전 `ModuleNotFoundError`로 실패해야 한다.
2. `backend/jumong/settings.py`의 allauth backend 문자열 한 줄만 올바른 경로로 고쳐.
3. 수정 뒤 web 이미지를 `docker compose up -d --build web`으로 새로 만들고, 신규 테스트와 전체 검증을 실행해.

## 엄격한 범위

- `.env`와 Google Cloud Console, Client ID·Secret, 초기 소유자 이메일, OAuth scope, redirect URI를 읽거나 수정하거나 출력하지 마.
- OAuth code·state·토큰·비밀값·길이·마스킹값을 테스트, 로그, 인수인계에 쓰지 마.
- 의존성, migration, DB 데이터, template/CSS, 사용자 계좌·원장·주문·포트폴리오·KRX·다음 거래일 시가 체결 로직을 바꾸지 마.
- 실제 돈·실제 증권계좌·실제 주문·결제·자동매매 경로를 만들지 마.
- 실제 Google 브라우저 로그인을 자동 실행하지 마. 사용자 수동 확인 항목으로만 남겨.

## 검증과 인수인계

아래를 실행하고 실제 결과를 기록해.

- `docker compose up -d --build web`
- `docker compose exec web python manage.py test trading.test_auth.AuthenticationBackendConfigurationTests`
- `docker compose exec web python manage.py test trading`
- `docker compose exec web python manage.py check`
- `docker compose exec web python manage.py makemigrations --check --dry-run`
- `git diff --check origin/dev...HEAD`

`docs/handoffs/T-010-P1-claude-handoff.md`에 다음을 남겨.

- callback이 도달한 뒤 backend import에서 실패한 원인(OAuth query parameter 제외)
- 변경 파일 전체와 완료 기준별 구현 위치
- 수정 전 실패와 수정 후 통과, 전체 테스트·check·dry-run 결과
- 실제 Google 로그인은 사용자 수동 확인이 필요한 미검증 항목이라는 사실
- 범위 밖 변경이 없고 push·PR·병합을 하지 않았다는 사실

구현과 인수인계를 논리적인 커밋으로 남긴 뒤, 커밋 해시와 인수인계 경로를 Codex에 보고해.
