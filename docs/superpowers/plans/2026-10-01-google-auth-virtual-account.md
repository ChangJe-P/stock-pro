# Google 로그인·사용자별 가상계좌 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google 로그인 사용자마다 독립된 가상 학습 계좌·주문·원장을 제공하고, 기존 단일 가상계좌를 본인만 1회 안전하게 연결한다.

**Architecture:** Django 세션과 `django-allauth` Google provider로 사용자 인증을 맡기고, `VirtualAccount.owner`를 Django 사용자와 1:1로 연결한다. 계좌·주문 서비스는 `request.user`가 아닌 계좌를 직접 인자로 받지 않고 사용자 인자를 받아 소유 계좌만 조회한다. 시장 일봉은 공용 읽기 데이터로 유지하되 수집 요청은 초기 소유자만 실행한다.

**Tech Stack:** Python 3.12, Django 5.2, PostgreSQL 16, Django Template, `django-allauth[socialaccount]==65.19.6`, Docker Compose

**Spec:** `docs/superpowers/specs/2026-10-01-google-auth-virtual-account-design.md`

## Global Constraints

- 실제 증권계좌·실제 돈·결제·실주문·자동매매·투자 자문은 어떤 코드·환경변수·외부 요청에도 추가하지 않는다.
- Google OAuth는 `openid`, `email`, `profile`만 요청하고, Client Secret·KRX 자격증명·DB 비밀번호는 루트 `.env`와 Django 설정 계층에서만 읽는다.
- 새 환경변수는 빈 값일 때 안전하게 로그인 또는 legacy 연결을 비활성화하며, 실제 값을 로그·응답·템플릿·테스트 fixture에 출력하지 않는다.
- 가상계좌 생성은 로그인 후 사용자의 명시적 POST만 가능하며, 최초 현금은 기존 `VIRTUAL_*` 정책의 `10,000,000원` 스냅샷이다.
- 일봉은 공용 읽기 데이터이고 pykrx 수집은 초기 소유자만 수동으로 요청할 수 있다. 사용자 KRX 자격증명 입력·저장·브라우저 로그인·쿠키 저장은 만들지 않는다.
- 비로그인 HTML은 Google 로그인 화면으로 이동시키고, 비로그인 JSON API는 `401 {"detail": "로그인이 필요합니다."}`로 끝낸다. 사용자 소유가 아닌 주문은 존재 여부를 드러내지 않고 404로 처리한다.
- 기존 `csrf_exempt` 사용자 계좌·주문·수집 POST는 제거하고, 세션 인증과 CSRF 보호를 적용한다. `/health`만 비로그인 공개 상태로 둔다.
- 코드 주석은 한국어로 작성하며, 새 프론트엔드 프레임워크·CSS 라이브러리·외부 CDN·가짜 금융 데이터는 추가하지 않는다.

## Review Focus

- 로그인하지 않은 브라우저·JSON 요청은 각각 로그인 이동과 401을 받고 DB를 쓰지 않아야 한다. → Task 4 테스트
- 서로 다른 두 사용자의 주문 ID를 추측해 체결·조회해도 상대 기록을 얻거나 원장을 바꿀 수 없어야 한다. → Task 3 테스트
- 기존 legacy 계좌는 허용 이메일의 명시적 연결 전까지 누구의 대시보드에도 표시되지 않아야 한다. → Task 2 테스트
- `INITIAL_OWNER_GOOGLE_EMAIL` 또는 OAuth 설정이 비어 있을 때 구성값·비밀값을 노출하거나 우회 로그인·수집을 허용하지 않아야 한다. → Task 1, Task 4 테스트
- 다음 거래일 시가 체결은 로그인 전환 뒤에도 외부 pykrx 호출 없이 저장된 일봉만 읽어야 한다. → Task 3 테스트

---

## File Structure

| 파일 | 책임 |
|---|---|
| `backend/requirements.txt`, `backend/requirements.lock.txt` | Google OAuth 의존성과 실제 설치 버전 고정 |
| `backend/jumong/settings.py` | Django 인증·세션·allauth·Google OAuth·초기 소유자 환경 설정 |
| `backend/jumong/urls.py` | 로그인·로그아웃·allauth callback·legacy 연결·기존 화면/API 경로 연결 |
| `backend/trading/models.py`, `backend/trading/migrations/0002_user_owned_virtual_accounts.py` | 계좌 소유자 1:1 관계와 기존 singleton 제거·legacy 데이터 보존 |
| `backend/trading/ownership.py` | 사용자별 계좌 조회·legacy 연결·초기 소유자 판정만 담당 |
| `backend/trading/accounts.py`, `backend/trading/orders.py` | 사용자별 가상계좌·원장·주문 처리. 가격·실거래 동작은 추가하지 않음 |
| `backend/trading/views.py` | 로그인 사용자 범위의 HTML·JSON 응답, CSRF·소유권·수집 권한 적용 |
| `backend/templates/trading/login.html`, `backend/templates/trading/setup.html`, `backend/templates/trading/dashboard.html` | Google 로그인, 기존 계좌 연결/생성, 로그인 사용자 기준 실제 화면 |
| `backend/trading/test_auth.py` | OAuth 설정, 인증, 사용자 간 격리, legacy migration·연결, CSRF 회귀 테스트 |
| `.env.example`, `docs/ENVIRONMENT.md`, `README.md` | Google OAuth 로컬 설정, callback 등록, 공개 API 보안 변경 안내 |

## Task 1: 인증 런타임과 안전한 설정

**Files:**
- Modify: `backend/requirements.txt`, `backend/requirements.lock.txt`
- Modify: `backend/jumong/settings.py`
- Modify: `backend/jumong/urls.py`
- Modify: `.env.example`, `docs/ENVIRONMENT.md`
- Create: `backend/trading/test_auth.py`

**Interfaces:**
- Produces: `settings.google_oauth_configured() -> bool` 또는 같은 역할의 설정 전용 판정 함수
- Produces: `/login/` Google 로그인 시작 화면, `/accounts/google/login/callback/` provider callback, `/logout/` POST 로그아웃 경로
- Consumes: 루트 `.env`의 `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`, `INITIAL_OWNER_GOOGLE_EMAIL`

- [ ] **Step 1: Google OAuth 설정이 없을 때 안전한 로그인 화면을 기대하는 테스트를 작성한다.**

`backend/trading/test_auth.py`에서 빈 OAuth 설정이면 `GET /login/`이 200이고 Google provider 시작 URL·비밀값을 렌더링하지 않으며, 인증이 필요한 HTML 경로는 `/login/`으로 이동하는지 작성한다.

- [ ] **Step 2: 새 테스트가 실패함을 확인한다.**

Run: `docker compose exec web python manage.py test trading.test_auth -v 2`

Expected: FAIL. 현재는 `/login/` 경로·인증 설정·테스트 대상이 없다.

- [ ] **Step 3: `django-allauth[socialaccount]==65.19.6`을 추가하고 Django 인증 설정을 최소로 구성한다.**

`django.contrib.auth`, `django.contrib.contenttypes`, `django.contrib.sessions`, `django.contrib.messages`, allauth account/socialaccount/Google provider, session·authentication·message middleware, request context processor, authentication backend, allauth URLs를 추가한다. Google app 자격증명은 DB `SocialApp`이 아니라 환경변수 기반 `SOCIALACCOUNT_PROVIDERS` 설정에만 넣고, 두 OAuth 값이 모두 있을 때만 provider app을 구성한다. scope는 `openid`, `email`, `profile`, `access_type`은 `online`, PKCE는 켠다.

`/login/`은 자체 Template로 만들고 Google provider 시작은 CSRF 토큰을 가진 POST form만 사용한다. 빈 설정에서는 안전한 설정 안내만 보인다. `LOGIN_URL`은 `/login/`, 로그인 성공 후 기본 이동은 `/`로 둔다. 로그아웃도 CSRF 보호 POST로만 처리한다.

- [ ] **Step 4: 설정·로그인 화면 테스트를 통과시킨다.**

Run: `docker compose exec web python manage.py test trading.test_auth -v 2`

Expected: PASS. 실제 Google 인증 요청은 발생하지 않는다.

- [ ] **Step 5: 환경 설명을 갱신하고 커밋한다.**

`.env.example`에는 이름과 빈 값만, `docs/ENVIRONMENT.md`에는 Google Cloud Console의 Web application redirect URI와 로컬 전용 보관 규칙만 기록한다. 실제 Client ID·Secret·이메일은 넣지 않는다.

```powershell
git add backend/requirements.txt backend/requirements.lock.txt backend/jumong/settings.py backend/jumong/urls.py backend/trading/test_auth.py .env.example docs/ENVIRONMENT.md
git commit -m "feat: add Google authentication configuration"
```

## Task 2: 사용자 소유 가상계좌와 legacy 기록 연결

**Files:**
- Modify: `backend/trading/models.py`
- Create: `backend/trading/migrations/0002_user_owned_virtual_accounts.py`
- Create: `backend/trading/ownership.py`
- Modify: `backend/trading/accounts.py`
- Modify: `backend/trading/test_auth.py`

**Interfaces:**
- Produces: `get_account_for_user(user, *, for_update: bool = False) -> VirtualAccount | None`
- Produces: `initialize_account(user) -> dict`, `claim_legacy_account(user) -> VirtualAccount`, `can_manage_market_data(user) -> bool`
- Consumes: authenticated Django user and `INITIAL_OWNER_GOOGLE_EMAIL`; `portfolio.compute_portfolio(account)` remains unchanged.

- [ ] **Step 1: 서로 다른 두 사용자가 각자 한 계좌만 만들고 기존 계좌가 owner 없이 유지되는 테스트를 작성한다.**

`TestCase`에서 `User.objects.create_user()` 두 명과 기존 0001 형태의 가상계좌·원장·주문을 준비한다. 첫 사용자의 계좌 초기화가 두 번째 사용자의 계좌를 반환하지 않는지, legacy 계좌가 명시적 연결 전까지 `owner is None`인지, 같은 사용자의 반복 초기화가 재설정·원장 추가를 하지 않는지 작성한다.

별도 `TransactionTestCase` migration 테스트는 migration executor로 `trading` 0001 상태에 singleton 계좌·원장·주문을 만든 뒤 0002로 이동해, 계좌 행과 연결 행은 유지되고 owner만 비어 있는지 확인한다.

- [ ] **Step 2: 새 모델·legacy 테스트가 실패함을 확인한다.**

Run: `docker compose exec web python manage.py test trading.test_auth -v 2`

Expected: FAIL. 현재 `VirtualAccount`에는 사용자 owner가 없고 단일 계좌 제약이 남아 있다.

- [ ] **Step 3: `VirtualAccount.owner` 1:1 관계와 데이터 보존 migration을 구현한다.**

`owner`는 Django 사용자에 대한 nullable `OneToOneField`로 추가한 뒤, 기존 `singleton` 컬럼·유일 제약·check 제약을 제거한다. 새 계좌는 `owner`가 반드시 있는 상태로 생성하고, migration으로 옛 계좌·현금 원장·주문을 삭제·복제·재계산하지 않는다.

`ownership.py`에서 이메일을 공백 제거·대소문자 무시로 비교한다. `claim_legacy_account(user)`는 허용 이메일, owner 없는 legacy 계좌 1개, 트랜잭션 행 잠금을 모두 확인한 뒤에만 owner를 설정한다. 조건이 맞지 않으면 기록 존재 여부를 타 사용자에게 알려주지 않는 안전한 오류로 끝낸다.

`accounts.initialize_account(user)`와 조회·원장 함수는 전역 첫 계좌 대신 해당 사용자 계좌만 사용한다.

- [ ] **Step 4: 데이터 모델·legacy 연결 테스트를 통과시킨다.**

Run: `docker compose exec web python manage.py test trading.test_auth -v 2`

Expected: PASS. 두 사용자 계좌는 분리되고 legacy 행의 주문·원장은 보존된다.

- [ ] **Step 5: migration 검사와 커밋을 수행한다.**

Run: `docker compose exec web python manage.py makemigrations --check --dry-run`

Expected: `No changes detected`.

```powershell
git add backend/trading/models.py backend/trading/migrations/0002_user_owned_virtual_accounts.py backend/trading/ownership.py backend/trading/accounts.py backend/trading/test_auth.py
git commit -m "feat: scope virtual accounts to users"
```

## Task 3: 기존 주문·원장·포트폴리오의 사용자 격리

**Files:**
- Modify: `backend/trading/orders.py`
- Modify: `backend/trading/views.py`
- Modify: `backend/trading/test_auth.py`
- Modify: `backend/trading/tests.py`

**Interfaces:**
- Produces: `create_order(user, ticker: str, quantity: int, decision_trade_date: date) -> dict`
- Produces: `execute_order(user, order_id: int) -> dict`, `list_orders(user) -> dict`
- Consumes: `get_account_for_user(user, for_update=True)` and the existing stored-price/next-trading-day-open functions.

- [ ] **Step 1: 계정 간 주문·원장·대시보드 격리의 실패 테스트를 작성한다.**

두 사용자에게 가격·주문을 준비한다. A가 B의 order ID를 조회·체결하면 404이고 B의 주문·현금 원장은 바뀌지 않는지, `GET /`은 로그인 사용자의 계좌·최근 주문만 보이는지, 체결 중 `market_data.fetch_ohlcv`가 호출되지 않는지 작성한다.

- [ ] **Step 2: 격리 테스트가 실패함을 확인한다.**

Run: `docker compose exec web python manage.py test trading.test_auth trading.tests.OrderTests -v 2`

Expected: FAIL. 현재 서비스와 화면이 `VirtualAccount.objects.first()` 및 전역 주문 조회를 사용한다.

- [ ] **Step 3: 모든 계좌·주문 호출을 사용자 범위로 바꾼다.**

`orders.py`의 생성·목록·체결 함수에 `user`를 첫 인자로 추가한다. 체결의 계좌 잠금은 해당 사용자 계좌만 잠그고 `VirtualBuyOrder` 조회에 `account` 조건을 넣는다. dashboard와 setup context도 로그인 사용자의 계좌·최근 주문만 조회한다. `portfolio.compute_portfolio(account)`의 읽기 전용 계산 규칙, stored `DailyPrice`, 다음 거래일 시가 원칙은 변경하지 않는다.

- [ ] **Step 4: 주문 격리·기존 주문 규칙 테스트를 통과시킨다.**

Run: `docker compose exec web python manage.py test trading.test_auth trading.tests -v 2`

Expected: PASS. 다음 거래일 시가·현금 부족·중복 체결 방지 회귀도 유지된다.

- [ ] **Step 5: 커밋한다.**

```powershell
git add backend/trading/orders.py backend/trading/views.py backend/trading/test_auth.py backend/trading/tests.py
git commit -m "feat: isolate virtual orders by user"
```

## Task 4: HTML·JSON 접근 제어와 안전한 초기 흐름

**Files:**
- Modify: `backend/trading/views.py`
- Create: `backend/templates/trading/login.html`
- Modify: `backend/templates/trading/dashboard.html`
- Modify: `backend/templates/trading/setup.html`
- Modify: `backend/trading/static/trading/dashboard.css`
- Modify: `backend/trading/test_auth.py`

**Interfaces:**
- Produces: `POST /setup/legacy-account/claim` (CSRF 보호, PRG), 사용자별 `/`, `/setup`
- Produces: API 인증 helper가 반환하는 JSON 401과 소유권 은닉 404
- Consumes: `claim_legacy_account(user)`, `initialize_account(user)`, `can_manage_market_data(user)`

- [ ] **Step 1: 인증되지 않은 화면·API 및 legacy 연결 form의 실패 테스트를 작성한다.**

비로그인 `GET /`·`GET /setup`은 `/login/` 이동, 비로그인 계좌·주문·시장 데이터 JSON API는 401 JSON, CSRF 없는 사용자 POST는 403인지 작성한다. 허용 이메일의 로그인 사용자는 legacy 연결 안내를 보고 POST 확인 뒤 303으로 대시보드에 돌아오는지, 다른 사용자는 그 안내·경로에서 연결할 수 없는지 작성한다.

- [ ] **Step 2: 새 접근 제어 테스트가 실패함을 확인한다.**

Run: `docker compose exec web python manage.py test trading.test_auth -v 2`

Expected: FAIL. 현재 HTML·JSON API는 공개이고 계좌 POST는 CSRF 예외다.

- [ ] **Step 3: 화면과 API에 로그인·CSRF·소유권 경계를 적용한다.**

HTML은 `login_required`와 `/login/`을 사용한다. API에는 JSON 401을 반환하는 작은 decorator/helper를 만들고 health에는 적용하지 않는다. 계좌·원장·주문·일봉 조회·수집 API의 기존 `csrf_exempt`를 제거한다. `setup`에는 실제로 동작하는 `기존 가상 학습 기록 연결` 또는 `가상계좌 시작` form만 표시하고, 로그인 사용자 이름·로그아웃 POST를 공통 header에 표시한다. 아직 구현하지 않은 주문·내역·설정 탭이나 가짜 차트는 만들지 않는다.

- [ ] **Step 4: 접근 제어와 화면 흐름 테스트를 통과시킨다.**

Run: `docker compose exec web python manage.py test trading.test_auth trading.tests -v 2`

Expected: PASS. GET는 쓰기 없이 로그인 사용자 데이터만 읽고, POST는 CSRF·PRG를 유지한다.

- [ ] **Step 5: 커밋한다.**

```powershell
git add backend/trading/views.py backend/templates/trading/login.html backend/templates/trading/dashboard.html backend/templates/trading/setup.html backend/trading/static/trading/dashboard.css backend/trading/test_auth.py
git commit -m "feat: protect user account screens"
```

## Task 5: 공용 일봉의 운영자 수집 권한과 문서 정리

**Files:**
- Modify: `backend/trading/views.py`
- Modify: `backend/trading/test_auth.py`
- Modify: `README.md`, `docs/ENVIRONMENT.md`

**Interfaces:**
- Produces: `can_manage_market_data(user) -> bool`를 이용한 수집 POST 403 경계
- Consumes: 기존 `market_data.collect_daily_prices(ticker, from_date, to_date)`; provider·KRX 설정·저장 로직은 변경하지 않는다.

- [ ] **Step 1: 운영자 외 수집 차단과 공용 읽기 테스트를 작성한다.**

초기 소유자 이외의 로그인 사용자가 HTML·JSON 수집 POST를 보내면 403이고 `fetch_ohlcv`가 호출되지 않는지 작성한다. 로그인 사용자의 저장 일봉 GET은 외부 호출 없이 기존 행을 읽는지, 초기 소유자의 수집 경로는 기존 입력 검증과 비밀값 비노출을 유지하는지 작성한다.

- [ ] **Step 2: 수집 권한 테스트가 실패함을 확인한다.**

Run: `docker compose exec web python manage.py test trading.test_auth -v 2`

Expected: FAIL. 현재 로그인 사용자·운영자 구분 없이 수집 경로가 호출된다.

- [ ] **Step 3: 수집 권한을 적용하고 운영 문서를 갱신한다.**

`can_manage_market_data(user)`가 true인 초기 소유자만 수집하도록 HTML·JSON POST에 적용한다. KRX 자격증명은 사용자·DB·response·log에 저장하지 않는다. README와 환경 문서에는 Google OAuth 설정 뒤에만 수동 실제 OAuth 확인을 하며, 모든 사용자는 공용 저장 일봉을 읽을 수 있다는 운영 원칙을 추가한다.

- [ ] **Step 4: 전체 검증과 수동 OAuth 경계를 기록한다.**

Run:

```powershell
docker compose exec web python manage.py test trading
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
```

Expected: 전체 테스트 통과, `System check identified no issues`, `No changes detected`.

Google Cloud Client ID·Secret을 실제 `.env`에 넣고 redirect URI를 등록한 뒤의 Google 로그인은 사용자가 직접 한 번 확인한다. Claude는 실제 OAuth 자격증명을 요구·출력·기록하지 않으며, 미실행이면 인수인계에 미검증으로 남긴다.

- [ ] **Step 5: 인수인계와 최종 커밋을 작성한다.**

`docs/handoffs/T-010-claude-handoff.md`에 변경 파일, 완료 기준별 위치, 자동 테스트·migration·manual OAuth 검증 구분, legacy migration 결과, 미해결 항목을 기록한다.

```powershell
git add backend/trading/views.py backend/trading/test_auth.py README.md docs/ENVIRONMENT.md docs/handoffs/T-010-claude-handoff.md
git commit -m "docs: hand off T-010 authentication foundation"
```

## Plan Self-Review

- **Spec coverage:** 실제 돈 배제, Google 최소 권한, 사용자별 계좌, explicit legacy 연결, KRX 운영자 수집, CSRF/API 경계, 이후 T-011 UI 분리를 Task 1~5에 모두 배정했다.
- **Step scan:** 각 task는 실패 테스트 → 최소 구현 → 통과 확인 → 커밋 순서이며, 함수 이름·입력·상태 코드·data ownership이 명시돼 있다.
- **Type consistency:** 모든 계좌·주문 서비스는 `user`를 첫 인자로 받고, portfolio는 기존처럼 owner-scoped `account`를 받는다. legacy 연결은 `claim_legacy_account(user)` 하나로 한정한다.
- **Review focus:** 다섯 가지 고위험 조건을 header와 Task 1~4/5 테스트에 연결했다.
- **Proportion:** T-011 화면 확장, 차트, 매도, Notion, 배포를 포함하지 않아 인증·소유권 전환 하나만 구현 가능한 크기로 유지했다.
