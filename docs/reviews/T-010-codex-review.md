---
task_id: T-010
branch: codex/auth
base: origin/dev (1cfa343)
reviewed_head: bdaa62f
implementation_commit: b9f97bc
status: changes_requested
reviewed_at: 2026-10-06
---

# T-010 Codex 검토

## 검토 범위

- 인수인계: `docs/handoffs/T-010-claude-handoff.md`
- 비교 범위: `origin/dev...codex/auth` — 25개 파일, 1,593행 추가 / 130행 삭제
- Git 확인: 작업 트리 깨끗함, `git diff --check origin/dev...HEAD` 오류 없음
- 독립 실행: 현재 `codex/auth`로 Docker web 이미지를 새로 빌드하고 임시 web 컨테이너에서 실행했다. 기존 개발 DB의 migration·데이터 초기화는 실행하지 않았다.

## 독립 실행 결과

| 명령 | 결과 |
|---|---|
| `docker compose run --rm --no-deps web python manage.py check` | `System check identified no issues (0 silenced).` |
| `docker compose run --rm --no-deps web python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `docker compose run --rm --no-deps web python manage.py test trading` | 82개 테스트 실행, `OK` |
| CSRF middleware 재현: 비로그인 JSON POST `/virtual-orders` | **실패** — `403 Forbidden (CSRF cookie not set.)`, 명세의 401 JSON이 아님 |
| Docker 이미지 실제 패키지 버전 확인 | Django 5.2.17, django-allauth 65.19.6, psycopg 3.3.6, pykrx 1.2.9 |

테스트 출력의 `pykrx 조회 실패` 메시지는 기존 테스트가 외부 조회 실패 경로를 검증하면서 낸 로그이며, 전체 테스트는 성공했다. 실제 Google OAuth 및 실제 KRX 네트워크 수집은 이번 검토에서도 실행하지 않았다.

## 완료 기준 대조

| 완료 기준 | 판정 | Codex 확인 근거 |
|---|---|---|
| 최소 Google scope·환경변수 설정·비밀값 미노출 | 부분 충족 | `settings.py`의 설정 기반 provider와 `openid`·`email`·`profile`은 확인했다. 실제 OAuth 로그인은 사용자 설정 전이라 미확인이다. |
| 사용자별 계좌·원장·주문·대시보드·포트폴리오 분리 | 충족 | `VirtualAccount.owner` 1:1, user-scoped service/view, A/B 격리 테스트 82개 통과를 독립 확인했다. |
| legacy 행 보존·본인 명시적 1회 연결 | 충족 | migration executor 테스트가 0001에서 0002로 기존 계좌·원장·주문을 보존하는 것을 포함해 통과했다. |
| 비로그인 HTML/JSON, CSRF, 타인 주문, 비운영자 수집 차단 | 수정 필요 | HTML redirect·타인 주문 404·운영자 수집 제한은 코드와 테스트에서 확인했다. 비로그인 JSON POST의 401 계약은 실제 CSRF middleware에서 실패한다(P1-1). |
| 공용 일봉 읽기·초기 소유자만 수집 | 충족 | `can_manage_market_data` 선행 검사와 비운영자 외부 호출 없음 테스트를 확인했다. |
| 실제 돈·증권사·실주문 경로 없음, 다음 거래일 시가 유지 | 충족 | diff에 증권사·결제·실제 주문 경로가 없고, user-scoped 다음 거래일 시가 회귀 테스트가 통과했다. |
| 전체 검사·lock·수동 OAuth 구분 | 수정 필요 | Django 검사·dry-run·테스트는 통과했지만 lock이 현재 Docker 설치 결과와 불일치한다(P1-2). 실제 OAuth는 미확인으로 올바르게 구분해야 한다. |

## 발견 사항

### P1 — 비로그인 JSON POST가 401이 아니라 CSRF 403으로 끝난다

- 위치: `backend/jumong/settings.py:45`, `backend/trading/views.py:43`, `backend/trading/views.py:192`
- 재현: CSRF 검사를 강제한 Django client로 `POST /virtual-orders`를 보내면 view의 `_login_required_json`보다 `CsrfViewMiddleware`가 먼저 실행되어 `403 Forbidden (CSRF cookie not set.)` HTML을 반환한다.
- 영향: 작업 명세의 정확한 `401 {"detail":"로그인이 필요합니다."}` JSON 계약을 POST API에서 지키지 못한다. 현재 테스트는 비강제 기본 client로만 비로그인 POST를 검사해 이 문제를 놓쳤다.
- 수정 기준: 비로그인 JSON POST는 CSRF 토큰이 없어도 먼저 정확한 401 JSON을 반환하고, 로그인 사용자에게만 CSRF 없는 상태 변경 POST가 403이 되도록 경계를 구현한다. 두 경우를 `Client(enforce_csrf_checks=True)`로 회귀 테스트한다.

### P1 — `requirements.lock.txt`가 현재 Docker 이미지의 실제 설치 결과와 다르다

- 위치: `backend/requirements.lock.txt:33-41`
- 증거: 새 Docker 이미지에서 `psycopg=3.3.6`, `pykrx=1.2.9`가 설치됐으나 lock에는 각각 `3.3.5`, `1.2.8`로 기록돼 있다. lock에는 이번 작업과 무관한 FastAPI·pytest 계열도 추가됐다.
- 영향: Dockerfile은 `requirements.txt`만 설치하므로 lock이 재현 가능한 실제 설치 결과라는 인수인계 설명과 맞지 않는다.
- 수정 기준: 현재 Docker 이미지에서 얻은 실제 설치 결과로 lock 전체를 재생성하거나, 프로젝트가 사용하지 않는 lock 파일이라면 그 역할과 변경 범위를 명확히 정리한다. 핵심 런타임 버전과 lock의 일치를 검증한다.

### P1 — 상위 프로젝트 명세가 단일 로컬 사용자라고 남아 있다

- 위치: `docs/PROJECT_SPEC.md:9`
- 증거: T-010은 Google 로그인 사용자마다 독립된 가상 계좌를 만드는 설계인데, 프로젝트의 MVP 고정 범위는 아직 `가상 현금 기반의 단일 로컬 사용자`다.
- 영향: 이후 작업에서 `AGENTS.md`가 요구하는 프로젝트 명세를 읽으면 다중 사용자·소유권 경계를 되돌릴 위험이 있다.
- 수정 기준: 실제 증권계좌·실제 돈을 쓰지 않는 가상 투자 원칙을 유지한 채, 현재 결정인 Google 로그인 사용자별 독립 가상계좌로 명세를 갱신한다.

## P2 및 미확인 항목

- 실제 Google OAuth 로그인은 Client ID·Secret과 redirect URI를 사용자가 로컬에 설정한 뒤 수동 확인해야 한다. 비밀값은 인수인계·리뷰·Git에 넣지 않는다.
- 실제 pykrx/KRX 일봉 수집 성공은 이번 검토 범위에서 확인하지 않았다. 권한 경계와 저장 일봉 기반 체결 회귀 테스트만 통과했다.

## 병합 판단

**수정 후 가능.** P0는 없지만 P1 세 가지가 남아 있어 현재 상태로 push·PR·병합을 진행하지 않는다. Claude Code가 P1을 수정하고 인수인계를 갱신하면, Codex가 CSRF 재현·Docker lock·Django 전체 검증을 다시 실행한다.
