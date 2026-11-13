---
title: Google OAuth 콜백 인증 백엔드 P1 수정 설계
status: user-directed
branch: codex/oauth
scope: T-010-P1-oauth-callback
---

# Google OAuth 콜백 인증 백엔드 P1 수정 설계

## 의도와 확인된 원인

T-010 병합 후 실제 Google OAuth 콜백은 `/accounts/google/login/callback/`까지 도달했다. 그러나 Django가 로그인 세션을 만들 때 `AUTHENTICATION_BACKENDS`의 `allauth.account.auth.backends.AuthenticationBackend`를 불러오려 해 `ModuleNotFoundError`가 발생했다.

현재 설치된 `django-allauth==65.19.6`의 실제 클래스 경로는 `allauth.account.auth_backends.AuthenticationBackend`다. 이 P1은 그 문자열을 바로잡고, 실제 Google 자격증명 없이도 모든 인증 백엔드가 로드되는 회귀 테스트를 추가한다.

## 목표와 제외 범위

- 목표: Google OAuth 완료 뒤 Django 세션 로그인 단계가 존재하는 allauth 인증 백엔드를 정상 로드한다.
- 목표: 잘못된 모듈 경로가 다시 들어오면 자동 테스트가 실패하게 한다.
- 제외: Google Cloud Console 설정, `.env`, OAuth Client ID·Secret, redirect URI, DB migration, 의존성, 화면, 권한 범위, 계좌·주문·KRX 로직.
- 절대 제외: 실제 증권계좌·실제 돈·결제·실주문·자동매매.

## 검토한 접근과 선택

| 접근 | 판단 |
|---|---|
| 설정 문자열을 실제 모듈 경로로 최소 수정하고 `get_backends()` 회귀 테스트 추가 | 채택. 원인 한 곳만 고치고 실제 로그인 직전의 Django 로딩 경계를 자동 검증한다. |
| Google Client ID·Secret 또는 redirect URI를 다시 변경 | 제외. 콜백이 이미 allauth 로그인 완료 단계까지 도달했으므로 원인이 아니다. |
| 자체 인증 백엔드나 직접 OAuth 토큰 처리를 추가 | 제외. 검증된 django-allauth 흐름을 우회해 보안·유지보수 범위를 불필요하게 넓힌다. |

## 구현 경계

1. `backend/jumong/settings.py`의 allauth backend 문자열 한 줄만 `allauth.account.auth_backends.AuthenticationBackend`로 바꾼다.
2. `backend/trading/test_auth.py`에 실제 프로젝트 설정의 모든 인증 백엔드를 `django.contrib.auth.get_backends()`로 불러오는 테스트를 추가한다. allauth의 `AuthenticationBackend` 인스턴스가 포함되는지 확인한다.
3. 테스트는 OAuth 네트워크·사용자 Client ID·Secret·브라우저 콜백을 사용하지 않는다.
4. Docker Compose는 소스를 bind mount하지 않으므로 코드 변경 뒤 `docker compose up -d --build web`으로 새 이미지를 만든 후 검증한다.

## 완료 기준

1. `AUTHENTICATION_BACKENDS`에 정확한 allauth 경로가 있고, 오타 경로는 없다.
2. 신규 회귀 테스트는 수정 전 `ModuleNotFoundError`로 실패하고 수정 후 통과한다.
3. 전체 `trading` 테스트, Django `check`, migration dry-run이 통과한다.
4. migration·의존성·환경변수·OAuth scope·데이터 모델·실제 거래 경로를 변경하지 않는다.
5. 실제 Google 로그인은 사용자가 수정본을 병합·배포한 뒤 수동으로 재확인하며, OAuth code·state·비밀값을 로그나 인수인계에 기록하지 않는다.
