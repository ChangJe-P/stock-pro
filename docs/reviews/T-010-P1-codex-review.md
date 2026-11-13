---
task_id: T-010-P1
branch: codex/oauth
base: origin/dev (b0e4331)
reviewed_head: d67575e
status: approved
reviewed_at: 2026-11-12
---

# T-010-P1 Codex 검토

## 검토 범위

- 인수인계: `docs/handoffs/T-010-P1-claude-handoff.md`
- 구현 커밋: `d67575e`
- 비교 범위: `origin/dev...codex/oauth`
- 독립 실행: Codex가 새 Docker `web` 이미지를 빌드하고 `web`만 강제 재생성했다. PostgreSQL 볼륨·개발 데이터는 삭제하거나 초기화하지 않았다.

## 변경 대조

- 구현 커밋은 `backend/jumong/settings.py`의 allauth backend 경로 한 줄, `backend/trading/test_auth.py`의 로딩 회귀 테스트, 인수인계 파일만 변경한다.
- 브랜치 전체 diff의 나머지 네 파일은 Codex가 Claude 구현 전 만든 설계·계획·작업 명세·구현 프롬프트다.
- `.env`, OAuth Client ID·Secret, OAuth code·state, dependency, migration, DB 데이터, template/CSS, 가상계좌·주문·KRX·실제 거래 경로 변경은 확인하지 못했다.
- `git diff --check origin/dev...HEAD`는 공백 오류 없이 통과했다.

## 독립 실행 결과

| 명령 | 결과 |
|---|---|
| `docker compose up -d --force-recreate web` | 새 이미지의 web 컨테이너 재생성 성공, db healthy |
| `python manage.py test trading.test_auth.AuthenticationBackendConfigurationTests` | 1개 실행, 통과 |
| `python manage.py test trading` | 84개 실행, 통과 |
| `python manage.py check` | 문제 없음 |
| `python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `GET /health` | HTTP 200, database connected |

테스트 중 보인 `pykrx 조회 실패` 메시지는 기존 외부 조회 실패 경로 테스트의 출력이며, 테스트 전체는 성공했다. 실제 pykrx 네트워크 수집은 실행하지 않았다.

## 완료 기준 대조

| 완료 기준 | 판정 | Codex 확인 근거 |
|---|---|---|
| 실제 allauth backend 경로와 오타 경로 제거 | 충족 | 설정값이 `allauth.account.auth_backends.AuthenticationBackend`이고, 회귀 테스트가 새 이미지에서 통과했다. |
| 수정 전 실패·수정 후 Django/allauth backend 로드 | 충족 | 신규 테스트가 `get_backends()` 결과에 Django `ModelBackend`와 allauth `AuthenticationBackend`를 모두 확인한다. |
| 전체 테스트·check·migration dry-run | 충족 | Codex가 컨테이너 재생성 후 84개 테스트, check, dry-run을 직접 통과시켰다. |
| 범위·비밀값·가상투자 경계 유지 | 충족 | 설정 문자열과 테스트만 바뀌었고, 새 자격증명·실제 거래·DB 변경이 없다. |
| 실제 Google 로그인 성공 | 미확인 | 실제 브라우저 OAuth 콜백은 사용자 Google 세션이 필요하다. 현재 web은 수정본으로 기동되어 있어 사용자가 직접 한 번 확인해야 한다. |

## 발견 사항

### P2 — 인수인계의 변경 파일 수 설명을 더 정확히 쓸 필요가 있다

- 인수인계는 설정·테스트 두 파일만 바뀐 것처럼 적었지만, Claude 구현 커밋에는 인수인계 파일도 포함된다. 또한 브랜치 전체 diff에는 Codex 준비 문서 네 파일이 있다.
- 기능·보안 영향은 없고 범위 확장은 아니다. 다음 인수인계부터는 `구현 코드 파일`과 `인수인계·Codex 준비 문서`를 구분해 전체 변경 파일 목록을 명시하면 된다.

## 병합 판단

**수동 확인 대기.** 실제 증상은 브라우저 Google OAuth 완료 시점에 발생했으므로, 병합 요청 준비 전 사용자가 현재 `http://localhost:3000/login/`에서 같은 Google 계정으로 로그인해 대시보드 또는 `/setup`으로 이동하는지 확인해야 한다. 실패하면 화면의 오류 문구만 공유하고 OAuth code·state·비밀값·`.env` 내용은 공유하지 않는다.

---

## 사용자 수동 OAuth 확인 — 2026-11-12

사용자가 현재 `codex/oauth` 수정본으로 Google 로그인을 수행해 **성공**했다고 보고했다. 이는 이전에 500으로 끝났던 callback 이후 Django 세션 생성 경로가 실제 Google OAuth 흐름에서도 완료됐다는 수동 증거다. OAuth query parameter·비밀값·`.env` 내용은 요청하거나 기록하지 않았다.

## 최종 병합 판단

**승인.** 자동 검증과 사용자 수동 Google 로그인 확인이 모두 완료됐다. P0·P1은 없으며, P2 인수인계 파일 목록 표현은 기능 병합을 막지 않는 문서 개선 사항이다. 사용자 요청이 있으면 `codex/oauth`를 push하고 `dev` 병합 요청을 준비할 수 있다.
