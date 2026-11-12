---
task_id: T-010-P1
title: Google OAuth 콜백 인증 백엔드 경로 수정
branch: codex/oauth
base: dev
owner: Claude Code
reviewer: Codex
---

# T-010-P1 인수인계

## 원인 (OAuth query parameter 제외)

실제 Google 로그인은 콜백 경로까지 정상 도달했으나, 로그인 세션 생성 단계에서 Django가
`AUTHENTICATION_BACKENDS`에 설정된 allauth 백엔드를 import·인스턴스화하려다 실패했다.
설정 문자열이 존재하지 않는 모듈 `allauth.account.auth.backends.AuthenticationBackend`를
가리켰기 때문이다. django-allauth 65.19.6의 실제 경로는
`allauth.account.auth_backends.AuthenticationBackend`다. `get_backends()`가 각 백엔드를
import하므로 오타 경로에서 `ModuleNotFoundError: No module named 'allauth.account.auth'`가
발생해 콜백 완료가 500으로 끝났다. (OAuth code·state·token 등 query parameter와는 무관하다.)

## 변경 파일과 완료 기준별 구현 위치

| 완료 기준 | 구현 위치 |
|---|---|
| 1. 실제 allauth 백엔드 모듈 경로 사용, 오타 경로 제거 | `backend/jumong/settings.py:70` — `allauth.account.auth_backends.AuthenticationBackend`로 한 줄 수정 |
| 2. 신규 회귀 테스트(수정 전 실패·수정 후 양쪽 백엔드 로드) | `backend/trading/test_auth.py` `AuthenticationBackendConfigurationTests.test_get_backends_loads_django_and_allauth_backends` — `get_backends()`가 `ModelBackend`와 allauth `AuthenticationBackend`를 모두 로드하는지 검증 |
| 3. 전체 trading 테스트·check·dry-run 통과 | 아래 실행 결과 |
| 4. `.env`·OAuth 설정·migration·의존성·template/CSS·계좌·주문·KRX·실거래 경로 미변경 | `git diff --stat` = 위 2개 파일만 변경 |
| 5. OAuth 비밀값·query parameter·길이·마스킹값 미기록 | 이 문서·테스트·로그에 없음 |

## 실행 결과

Docker 이미지는 소스를 bind mount하지 않으므로 각 단계에서 `docker compose up -d --build web`로
새 web 이미지를 만든 뒤 실행했다.

**수정 전 (settings 오타 복원 후 build):**

- `python manage.py test trading.test_auth.AuthenticationBackendConfigurationTests`
  → `FAILED (errors=1)`, `ModuleNotFoundError: No module named 'allauth.account.auth'`

**수정 후 (fix 적용 후 build):**

| 명령 | 결과 |
|---|---|
| `test trading.test_auth.AuthenticationBackendConfigurationTests` | `Ran 1 test`, `OK` |
| `test trading` | `Ran 84 tests`, `OK` |
| `manage.py check` | `System check identified no issues (0 silenced).` |
| `makemigrations --check --dry-run` | `No changes detected` |
| `git diff --check origin/dev...HEAD` | 공백 오류 없음 |

## 실제 Google 로그인 — 미검증

실제 브라우저 Google 로그인 성공은 **자동 테스트로 검증하지 않았다.** Codex 검증 후 사용자가
`http://localhost:3000/login/`에서 본인 Google 계정으로 1회 수동 확인해야 한다. Claude는 브라우저
세션을 사용하거나 OAuth Client ID·Secret·code·state·token·redirect URI를 요청·출력·기록하지 않았다.

## 범위·절차 준수

- 범위 밖 변경 없음: `settings.py` 1줄과 `test_auth.py` 테스트 추가만. 의존성·migration·DB 데이터·
  template/CSS·계좌·원장·주문·포트폴리오·KRX·다음 거래일 시가 체결 로직은 건드리지 않았다.
- 실제 돈·실제 증권계좌·실주문·결제·자동매매 경로를 만들지 않았다.
- push·PR·병합을 하지 않았다. 논리적 커밋만 남겼다.
