---
id: T-010-P1
title: Google OAuth 콜백 인증 백엔드 경로 수정
status: ready_for_claude
branch: codex/oauth
base: dev
owner: Claude Code
reviewer: Codex
depends_on: T-010
---

# T-010-P1 Google OAuth 콜백 인증 백엔드 경로 수정

## 확인된 문제

실제 Google 로그인은 콜백 경로까지 도달했으나, 로그인 세션을 만드는 단계에서 Django가 존재하지 않는 `allauth.account.auth.backends.AuthenticationBackend` 모듈을 불러오려 해 500 오류가 발생했다. 현재 설치된 django-allauth의 실제 경로는 `allauth.account.auth_backends.AuthenticationBackend`다.

## 구현 전 필독

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/ENVIRONMENT.md`
4. `docs/superpowers/specs/2026-11-12-google-oauth-callback-backend-design.md`
5. `docs/superpowers/plans/2026-11-12-google-oauth-callback-backend.md`
6. `docs/tasks/T-010-google-auth-user-accounts.md`
7. `docs/tasks/T-010-P1-google-oauth-callback.md`
8. `skills/user-owned-virtual-account/SKILL.md`

현재 브랜치가 `codex/oauth`인지 확인한다. 작업 트리에 관련 없는 변경이 있거나 문서와 실제 오류가 다르면 구현하지 말고 Codex에 질문한다.

## 범위

1. `backend/jumong/settings.py`의 allauth backend 문자열을 실제 설치 경로인 `allauth.account.auth_backends.AuthenticationBackend`로 최소 수정한다.
2. `backend/trading/test_auth.py`에 Django `get_backends()`가 현재 설정의 모든 인증 백엔드를 로드하고 allauth `AuthenticationBackend`를 포함하는지 검증하는 회귀 테스트를 추가한다.
3. Docker 이미지가 소스를 bind mount하지 않으므로 수정 후 `docker compose up -d --build web`으로 새 web 이미지를 만든다.
4. `docs/handoffs/T-010-P1-claude-handoff.md`에 원인·변경 파일·실행 결과·수동 로그인 검증 상태를 기록한다.

## 완료 기준

1. 실제 allauth backend 모듈 경로가 설정에 사용되고, 오타 경로가 없다.
2. 신규 테스트는 수정 전 설정에서 실패하고 수정 후 allauth와 Django 기본 backend를 모두 로드한다.
3. 전체 `trading` 테스트, `manage.py check`, migration dry-run이 통과한다.
4. `.env`, Google Cloud 설정, OAuth Client ID·Secret, OAuth scope, redirect URI, DB migration, 의존성, template/CSS, 계좌·주문·KRX·실제 거래 경로는 변경하지 않는다.
5. OAuth query parameter, 비밀값, 길이, 마스킹값을 테스트·로그·인수인계에 남기지 않는다.

## 사용자 수동 확인

Codex 검증 뒤 사용자가 `http://localhost:3000/login/`에서 본인 Google 계정으로 로그인한다. 실제 로그인 성공 여부는 자동 테스트와 구분해 인수인계에 기록한다. Claude는 브라우저 세션을 사용하거나 OAuth 값을 요청·출력·기록하지 않는다.

## 실행 명령

- `docker compose up -d --build web`
- `docker compose exec web python manage.py test trading`
- `docker compose exec web python manage.py check`
- `docker compose exec web python manage.py makemigrations --check --dry-run`

## 제외 범위

- 실제 증권계좌·실제 돈·결제·실주문·자동매매·투자 자문
- Google Cloud Console, OAuth 자격증명·scope·redirect URI 변경
- 다른 로그인 제공처·비밀번호 로그인·사용자 권한 모델 변경
- DB 초기화·볼륨 삭제·migration·의존성 변경
- T-011 화면, 주문 입력, 거래 내역, 차트, 관심종목, 매도, Notion 연동

## Claude Code 완료 보고

`docs/handoffs/T-010-P1-claude-handoff.md`에 변경 파일, 완료 기준별 근거, 수정 전 실패·수정 후 통과 결과, 전체 검증, 실제 OAuth 수동 확인의 미검증 여부, 제한 사항을 남긴다. 논리적 커밋만 만들고 push·PR·병합은 하지 않는다.
