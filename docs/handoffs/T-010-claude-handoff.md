---
task_id: T-010
branch: codex/auth
commit: f5fd821
status: complete
---

# Claude Code 구현 인수인계

> 갱신(2026-10-06): Codex 검토 P1 3건 대응. 구현 `b9f97bc`, 최초 인수인계 `bdaa62f`, P1 수정 `f5fd821`. 아래 "Codex 검토 대응" 절 참조.

## Codex 검토 대응 (P1 × 3)

| 지적 | 대응 | 근거 |
|---|---|---|
| P1-1 — 비로그인 JSON POST가 CsrfViewMiddleware에서 403(CSRF)로 끝나 401 계약 위반 | `_login_required_json`을 `csrf_exempt` + (로그인 사용자에 한해) `csrf_protect`로 변경. 비로그인은 CSRF 검사 이전에 정확히 `401 {"detail":"로그인이 필요합니다."}`, 로그인 사용자의 토큰 없는 상태 변경 POST는 403. GET에는 영향 없음 | `CsrfAndCollectPermissionTests.test_unauth_json_post_is_401_even_under_csrf_enforcement`(enforce_csrf client로 401), `test_csrf_required_on_user_post`(로그인 403); Compose에서 `POST /virtual-orders` 비로그인 → 401 재확인 |
| P1-2 — lock이 Docker 실제 설치와 불일치, 무관한 FastAPI·pytest 포함 | `docker compose run --rm --no-deps web pip freeze`로 lock 전체 재생성. psycopg 3.3.6·pykrx 1.2.9·django-allauth 65.19.6과 일치, FastAPI·pytest 계열 제거 | `backend/requirements.lock.txt` |
| P1-3 — PROJECT_SPEC가 '단일 로컬 사용자'로 남음 | `docs/PROJECT_SPEC.md` MVP 고정 범위를 Google 로그인 사용자별 독립 가상계좌로 갱신(가상 전용 원칙 유지) | `docs/PROJECT_SPEC.md` |

## 작업 요약

- 구현한 내용: Google 로그인(django-allauth, Django 세션)으로 사용자마다 독립된 가상 학습 계좌·현금 원장·가상 매수 주문·포트폴리오를 제공한다. `VirtualAccount`를 Django 사용자와 1:1로 연결하고 기존 `singleton` 제약을 제거했다. 기존 단일 계좌는 owner 없는 legacy 계좌로 보존되며, `INITIAL_OWNER_GOOGLE_EMAIL`과 일치하는 본인만 CSRF 보호 POST로 **1회** 연결한다. 비로그인 HTML은 `/login/`으로 이동, 비로그인 JSON API는 401, 계좌·주문·수집 POST의 `csrf_exempt`를 제거했다. 일봉은 공용 읽기 데이터이며 수집은 초기 소유자만 실행한다(그 외 403, `fetch_ohlcv` 미호출). 실제 돈·실제 계좌·결제·실주문·자동매매 경로는 추가하지 않았고, 다음 거래일 시가 체결 원칙을 유지했다.
- 구현하지 않은 내용(제외 범위 준수): 실제 증권계좌·실제 돈·결제·실주문·자동매매, 사용자 KRX 자격증명 입력/저장, Google 외 로그인·비밀번호 로그인·다단계 권한, T-011의 주문 입력·거래 내역·설정·차트·관심종목 UI, 데이터 초기화·legacy 삭제.

## 변경·생성 파일

| 파일 | 내용 |
|---|---|
| backend/requirements.txt / requirements.lock.txt | `django-allauth[socialaccount]==65.19.6` 추가, 실제 설치 버전 lock |
| backend/jumong/settings.py | auth/sessions/messages/sites + allauth(google) 최소 구성, `SOCIALACCOUNT_PROVIDERS.APPS`(두 OAuth 값이 모두 있을 때만), `GOOGLE_OAUTH_*`·`INITIAL_OWNER_GOOGLE_EMAIL` 설정 계층 읽기, LOGIN_URL |
| backend/jumong/urls.py | `accounts/`(allauth), `/login/`·`/logout/`·`/setup/legacy-account/claim` |
| backend/trading/models.py | `VirtualAccount.owner` OneToOne(User), `singleton` 제거 |
| backend/trading/migrations/0002_user_owned_virtual_accounts.py | SeparateDatabaseAndState + idempotent SQL(기존 행 보존, owner NULL, 역방향 SQL) |
| backend/trading/ownership.py (신규) | 사용자 계좌 조회·legacy 1회 연결(행 잠금·멱등)·운영자 판정 |
| backend/trading/accounts.py / orders.py | `user` 인자로 소유 계좌·주문만 처리, 타인 주문 404 |
| backend/trading/views.py | 로그인 게이팅(HTML redirect / JSON 401), CSRF 복원, 소유권·수집 권한, login/logout/legacy view |
| backend/templates/trading/login.html (신규) | Google 로그인 화면(미설정 시 안전 안내) |
| backend/templates/trading/dashboard.html / setup.html | 공통 header(로그인 사용자·POST 로그아웃), legacy 연결 안내, 수집 form 운영자 게이팅 |
| backend/trading/static/trading/dashboard.css | user-bar·logout·legacy-claim 스타일 |
| backend/trading/test_auth.py (신규) | 인증·A/B 격리·legacy·CSRF·수집 권한·migration 보존 테스트 |
| backend/trading/tests.py | 기존 테스트를 로그인·user 범위로 이식(삭제·약화 없음) |
| .env.example / .env / docs/ENVIRONMENT.md / README.md | Google OAuth 변수 이름·빈 값·redirect URI·접근 제어 문서(실제 값 없음) |

로컬 `.env`에는 `GOOGLE_OAUTH_*`·`INITIAL_OWNER_GOOGLE_EMAIL`을 추가했으나 커밋하지 않았다(Git 제외). 실제 OAuth 값은 넣지 않았다.

## 완료 기준 대조

| 완료 기준 | 구현 위치 / 증거 | 판정 |
|---|---|---|
| 1. 최소 scope·.env 기반 설정, 비밀값 비노출 | settings `SOCIALACCOUNT_PROVIDERS`(scope openid/email/profile), 값 설정 계층만; `LoginScreenTests` | 충족 |
| 2. 사용자마다 계좌 1개, 원장·주문·대시보드·포트폴리오 분리 | owner OneToOne + ownership/accounts/orders user 범위; `AccountOwnershipTests` | 충족 |
| 3. legacy 보존·본인 1회 연결 | 0002 보존 migration + `claim_legacy_account`; `LegacyClaimTests`, `LegacyMigrationTests`, 실 dev DB 보존(아래) | 충족(실DB 확인) |
| 4. 비로그인 HTML/JSON·CSRF·타인 주문·비운영자 수집 차단 | login_required/401 helper, csrf_exempt 제거, 404/403; `LoginScreenTests`·`CsrfAndCollectPermissionTests`·`AccountOwnershipTests` | 충족 |
| 5. 공용 일봉 읽기·운영자만 수집 | `market_data_list` 로그인 공용, 수집 `can_manage_market_data` 게이트; `CsrfAndCollectPermissionTests` | 충족 |
| 6. 실제 돈·증권사 경로 없음·다음 거래일 시가 유지 | 저장 일봉만 읽기, 외부 호출은 Google OAuth·pykrx뿐; `test_next_day_open_execution_after_user_scoping` | 충족 |
| 7. 전체 테스트·check·migration dry-run·수동 OAuth 구분 | 아래 실행과 검증 | 충족 |

## 실행과 검증

### 자동 테스트 (Django test runner, OAuth·pykrx mock/미설정, 실제 네트워크·실제 자격증명 없음)

| 명령 | 결과 |
|---|---|
| `python manage.py check` | System check identified no issues |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test trading` | **Ran 83 tests … OK**(P1 수정으로 CSRF 강제 하 비로그인 401 회귀 1건 추가) |

`test_auth.py` 커버리지: OAuth 미설정 시 `/login/` 200 안전 안내(비밀값·provider 시작 URL 미노출), 비로그인 HTML 302→`/login/`, 비로그인 JSON 401(계좌 미생성), `/health` 공개; 두 사용자 계좌·주문·대시보드 격리와 타인 주문 ID 404, 사용자 범위 전환 뒤 다음 거래일 시가 체결·반복 체결 중복 방지; legacy 본인 1회 연결·멱등·행 보존, 비소유자 403·비노출, PRG; 로그인 사용자도 CSRF 없는 POST 403(HTML·JSON), 비운영자 수집 403·`fetch_ohlcv` 미호출·수집 기록 0, 로그인 사용자 공용 일봉 읽기; migration executor로 0001→0002 기존 계좌·원장·주문 보존·owner NULL.

> 명령은 로컬 `.venv`에서 실행했다(Docker Postgres 테스트 DB 사용). 새 테스트 DB는 auth/allauth/sites + trading 0001·0002 migration을 모두 적용한다.

### 실제 Docker PostgreSQL — 기존 데이터 legacy 보존(migrate 전후)

기존 dev `jumong` DB에 `migrate`를 적용해 기존 단일 계좌가 삭제·재계산 없이 owner NULL legacy로 보존됨을 확인했다(`down -v`·초기화 없음).

| 항목 | migrate 전 | migrate 후 |
|---|---|---|
| virtual_accounts | 1 | 1 |
| cash_ledger_entries | 2 | 2 |
| virtual_buy_orders | 3 | 3 |
| daily_prices / market_data_collection_runs | 2 / 4 | 2 / 4 |
| virtual_accounts.singleton 컬럼 | 있음 | 없음(제거) |
| 기존 계좌 owner_id | — | NULL(legacy, 미연결) |
| 원장 합계 | 9,996,996 | 9,996,996 |
| auth_user 테이블 | 없음 | 생성됨 |

### 실제 Docker Compose(db·web) 접근 경계 확인 (자동 테스트와 별도)

`docker compose up -d --build web` 후(로컬 `.env`의 Google OAuth 값은 비어 있음):

| 요청 | 결과 |
|---|---|
| `GET /login/` | HTTP 200 (OAuth 미설정 안전 안내, 비밀값·provider URL 없음) |
| `GET /`(비로그인) | HTTP 302 → `/login/?next=/` |
| `GET /virtual-account`(비로그인) | HTTP 401 `{"detail":"로그인이 필요합니다."}` |
| `POST /virtual-orders`(비로그인, CSRF 토큰 없음) | HTTP 401 `{"detail":"로그인이 필요합니다."}` — CSRF 403이 아님(P1-1 수정 재확인) |
| `GET /health` | HTTP 200 (공개) |

### 실제 Google OAuth 로그인 (미검증)

실제 Google 로그인 성공은 **검증하지 않았다.** Client ID·Secret은 사용자만 Google Cloud Console에서 발급·등록하고 로컬 `.env`에 넣는다(현재 비어 있음). Claude는 실제 OAuth 자격증명을 요청·출력·기록하지 않는다. 아래 "사용자 설정 필요" 절의 단계를 마친 뒤 사용자가 직접 1회 확인해야 한다.

## 사용자에게 필요한 Google Cloud Console 설정

1. Google Cloud Console → API 및 서비스 → OAuth 동의 화면(외부/테스트) 구성, 본인 Google 계정을 테스트 사용자로 추가.
2. 사용자 인증 정보 → OAuth 2.0 클라이언트 ID(애플리케이션 유형: **웹 애플리케이션**) 생성.
3. 승인된 리디렉션 URI에 `http://localhost:3000/accounts/google/login/callback/` 등록.
4. 로컬 `.env`에 `GOOGLE_OAUTH_CLIENT_ID`·`GOOGLE_OAUTH_CLIENT_SECRET`·`INITIAL_OWNER_GOOGLE_EMAIL`(본인 이메일) 입력.
5. `docker compose up -d --force-recreate web` 후 `http://localhost:3000/login/`에서 Google 로그인 → 초기 소유자면 `/setup`에서 `기존 가상 학습 기록 연결`을 1회 확인.

## 가정과 제한

- Google OAuth app은 DB `SocialApp`이 아니라 설정 기반 `SOCIALACCOUNT_PROVIDERS.APPS`로만 구성한다(두 값이 모두 있을 때만). 값·길이·마스킹을 어떤 output에도 넣지 않는다.
- `owner`는 nullable OneToOne이며 Postgres 유일 인덱스가 사용자당 계좌 1개를 보장한다(legacy NULL 1건과 공존). migration 0002는 역방향 SQL을 포함해 executor 테스트가 0001로 되돌릴 수 있다.
- 실제 Google OAuth 로그인은 미검증(사용자 설정 필요). 실제 KRX 네트워크 수집 성공도 이전 작업과 동일하게 미검증(환경 제약) — 저장 일봉 읽기와 권한 경계만 테스트했다.
- 사용자 KRX 자격증명은 입력·저장·표시 대상이 아니다. KRX는 서버 `.env`의 운영자 설정일 뿐이다.

## 미해결 항목과 다음 제안

- 실제 Google OAuth 로그인 수동 확인(사용자 Client ID·Secret 설정 후).
- T-011: 주문 입력·거래 내역·설정 등 실제 기능 화면(별도 작업).
- main/dev로의 병합·push·PR은 규칙에 따라 하지 않았다. Codex 검증 후 진행.

## 검토 대응 (P2 — 문서 정합성만)

Codex 재검토(`f5fd821`)의 P2 문서 정합성 지적을 **문서만** 수정했다. 서비스 코드·마이그레이션·의존성·테스트는 변경하지 않았다.

| 지적 | 조치 | 위치 |
|---|---|---|
| T-003 계좌 설명이 `단일 로컬 사용자` | `로그인 사용자별 독립 가상 학습 계좌`로 수정 | `README.md`(가상계좌·현금 원장 API) |
| T-010 접근 제어의 CSRF 서술이 부정확 | 비로그인 JSON 상태 변경은 CSRF보다 먼저 `401 {"detail":"로그인이 필요합니다."}`, 로그인 사용자의 토큰 없는 요청은 `403`이라는 경계를 명시 | `README.md`(로그인과 접근 제어) |
| `csrf_exempt가 제거됐다`는 실제 구현과 불일치 | 동일하게 `401 선행 / 로그인 403` 경계로 수정(외부 `csrf_exempt` 래퍼 + 내부 `csrf_protect` 구현 동작과 일치) | `docs/ENVIRONMENT.md`(접근 제어 T-010) |
| 가상 거래 정책의 `단일 로컬 가상계좌` | `로그인 사용자별 독립 가상계좌`로 수정 | `docs/ENVIRONMENT.md`(가상 거래 정책 변수) |

- `기존 단일 가상계좌 … 1회 연결`(README·ENVIRONMENT) 표현은 **migration 이전 legacy 계좌를 초기 소유자가 1회 연결**한다는 사실 서술이라 그대로 두었다.
- 실제 돈·실제 증권계좌·실제 주문·결제를 쓰지 않는 가상 투자 원칙은 모든 문구에서 유지했다.
- 문서 diff 확인: `git diff --stat` = `README.md`(+2/-2), `docs/ENVIRONMENT.md`(+2/-2), 총 2개 파일 4줄; `git diff --check` 공백 오류 없음. 코드·테스트·lock·마이그레이션 변경 없음.

## 최종 보고
- 커밋: `b9f97bc`(구현), `bdaa62f`(최초 인수인계), `f5fd821`(검토 P1 수정: 401-before-CSRF·lock·spec), P2 문서 정합성(이 커밋)
- 인수인계 파일: `docs/handoffs/T-010-claude-handoff.md`
