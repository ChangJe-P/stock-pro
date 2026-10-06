---
id: T-010
title: Google 로그인과 사용자별 가상계좌 기반
status: ready_for_claude
branch: codex/auth
owner: Claude Code
reviewer: Codex
depends_on: T-003, T-004, T-005, T-007, T-008, T-009
---

# T-010 Google 로그인과 사용자별 가상계좌 기반

## 목표

Google 로그인 사용자마다 독립된 **가상** 학습 계좌·현금 원장·가상 매수 주문·포트폴리오를 제공한다. 기존 단일 가상계좌와 연결된 원장·주문은 삭제하거나 재계산하지 않고, 본인 Google 계정이 명시적으로 한 번 연결할 때만 가져간다.

Google 로그인은 신원 확인만 한다. 실제 증권계좌·실제 돈·결제·실제 주문·자동매매는 어떤 코드·환경변수·외부 요청에도 만들지 않는다. KRX는 공용 저장 일봉 수집용 로컬 운영자 인증일 뿐이며, 사용자에게 KRX 자격증명을 받거나 저장하지 않는다.

## 구현 전 필독

아래를 순서대로 읽는다. 충돌하면 이 작업 문서의 범위·완료 기준을 우선한다.

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/ENVIRONMENT.md`
4. `docs/superpowers/specs/2026-10-01-google-auth-virtual-account-design.md`
5. `docs/superpowers/plans/2026-10-01-google-auth-virtual-account.md`
6. `docs/tasks/T-003-virtual-account-ledger.md`
7. `docs/tasks/T-004-virtual-order-execution.md`
8. `docs/tasks/T-008-krx-authenticated-market-data.md`
9. `docs/tasks/T-010-google-auth-user-accounts.md`
10. `skills/user-owned-virtual-account/SKILL.md`
11. `C:\Users\박창제\.claude\skills\ui-ux-pro-max\SKILL.md`
12. `C:\Users\박창제\.claude\skills\frontend-design\SKILL.md`

현재 브랜치가 `codex/auth`인지 확인한다. OAuth 설정값, legacy 연결, 화면·데이터 표시 기준에 문서 밖의 결정이 필요하면 구현하지 말고 Codex에 질문한다.

## 범위

### 1. Google OAuth와 Django 세션

- `django-allauth[socialaccount]==65.19.6`만 새 런타임 의존성으로 추가하고, 실제 설치 결과를 `requirements.lock.txt`에 기록한다.
- Django 인증·콘텐츠 타입·세션·메시지 앱과 필요한 middleware/context processor/authentication backend를 최소로 추가한다.
- `/login/`은 자체 Django Template이며 Google 로그인 시작은 CSRF 토큰이 있는 POST form으로만 제공한다. 로그아웃도 POST+CSRF만 허용한다.
- Google OAuth provider는 설정 기반으로만 구성한다. DB `SocialApp`에 Client ID·Secret을 저장하지 않는다.
- `.env.example`, `docs/ENVIRONMENT.md`에는 아래 이름·안전한 설명·빈 값만 추가한다. 실제 값·예시 값·전체 `.env` 복사본은 넣지 않는다.
  - `GOOGLE_OAUTH_CLIENT_ID`
  - `GOOGLE_OAUTH_CLIENT_SECRET`
  - `INITIAL_OWNER_GOOGLE_EMAIL`
- Client ID와 Secret이 모두 없으면 `/login/`은 안전한 설정 안내만 보여주고 OAuth 시작을 하지 않는다. 값·길이·마스킹값·예외 원문은 어떤 output에도 넣지 않는다.
- Google 권한 범위는 `openid`, `email`, `profile`만 사용한다. refresh token 목적의 `offline` 접근, 결제·금융 scope, Google API 호출은 추가하지 않는다.

### 2. 사용자 소유 가상계좌와 legacy migration

- `VirtualAccount`에 Django 사용자와의 `OneToOneField` owner를 추가한다.
- 기존 `singleton` 필드, 유일 제약, 항상 참 check 제약을 migration으로 제거한다.
- 기존 단일 계좌는 migration 후 owner가 없는 legacy 계좌로 보존한다. 현금 원장·주문·가격·수집 실행 기록을 삭제·복제·재계산·초기화하지 않는다.
- 새 사용자는 로그인 후 명시적인 `가상계좌 시작` POST에서만 새 계좌를 만들며, 기존 `VIRTUAL_*` 정책의 `10,000,000원` 가상 현금 스냅샷을 사용한다.
- `INITIAL_OWNER_GOOGLE_EMAIL`과 대소문자·앞뒤 공백을 무시하고 일치하는 Google 사용자만 legacy 연결 안내를 볼 수 있다. 그 사용자가 CSRF 보호된 확인 POST를 보낸 경우에만, 트랜잭션·행 잠금 안에서 owner 없는 계좌 한 개를 1회 연결한다.
- 자동 연결은 금지한다. 다른 사용자는 legacy 계좌의 존재·ID·잔액·주문을 알 수 없고, 새 가상계좌를 만들 수 있다.
- migration executor 기반 테스트로 0001 상태의 기존 계좌·원장·주문이 0002 적용 뒤 보존되고 owner만 비어 있음을 확인한다.

### 3. 계좌·주문·포트폴리오 접근 제어

- 계좌·원장·주문 서비스가 `VirtualAccount.objects.first()` 또는 전역 주문 조회를 사용하지 않게 한다.
- `accounts.initialize_account(user)`, 계좌/원장 조회, `orders.create_order(user, ...)`, `orders.list_orders(user)`, `orders.execute_order(user, order_id)`처럼 로그인 사용자를 명시적으로 전달한다.
- dashboard/setup은 로그인 사용자의 계좌·최근 주문만 보여 준다. `portfolio.compute_portfolio(account)`의 읽기 전용 계산은 owner-scoped account를 받아 기존 규칙을 유지한다.
- 주문 생성·체결은 기존처럼 저장된 비조정 일봉만 읽고, 결정일보다 뒤인 첫 거래일 시가로만 체결한다. pykrx·HTTP·실제 증권사 호출을 시작하지 않는다.
- 다른 사용자의 order ID를 조회하거나 체결하면 존재 여부를 밝히지 않고 404로 처리한다.

### 4. HTML·JSON·KRX 수집 권한

- `/health`를 제외한 대시보드, setup, 가상계좌·원장·주문·일봉 조회 API는 로그인 필수다.
- 비로그인 HTML은 `/login/`으로 이동한다. 비로그인 JSON API는 정확히 `401 {"detail": "로그인이 필요합니다."}`를 반환한다.
- 계좌·주문·수집 JSON POST에서 기존 `csrf_exempt`를 제거하고 세션 CSRF 보호를 적용한다.
- KRX ID·비밀번호는 루트 `.env`와 settings에서만 읽고, 화면·DB·API·로그에는 노출하지 않는다.
- `INITIAL_OWNER_GOOGLE_EMAIL`과 일치하는 초기 소유자만 기존 수동 일봉 수집 POST를 실행할 수 있다. 다른 로그인 사용자는 저장된 공용 일봉을 읽을 수 있으나 수집 POST는 403이며 `fetch_ohlcv`가 호출되면 안 된다.

### 5. 최소 화면 흐름

- 로그인 전: 주몽이 실제 돈·실제 계좌·실제 주문과 무관한 가상 학습 서비스임을 명시한 Google 로그인 화면.
- 로그인 후 legacy 소유자: 대시보드 또는 setup에서 `기존 가상 학습 기록 연결`을 명시적으로 선택할 수 있는 안내.
- 로그인 후 새 사용자: 실제 동작하는 `가상계좌 시작` 안내와 기존 dashboard/setup만 제공.
- 로그인 후 공통 header: 로그인 사용자 표시, POST 로그아웃, 실제 존재하는 대시보드·데이터 준비 화면 링크만 표시.
- 주문·거래 내역·설정·차트·관심종목 탭은 T-011에서 실제 기능과 함께 만든다. 빈 탭·준비 중 버튼·가짜 차트·임의 시세를 만들지 않는다.

## 테스트와 검증

새 동작은 `backend/trading/test_auth.py`에 먼저 실패하는 테스트를 추가해 시작한다. 기존 `backend/trading/tests.py`를 삭제·약화하지 않는다.

필수 자동 검증:

1. OAuth 값 누락 시 안전한 로그인 화면, 비로그인 HTML redirect, 비로그인 JSON 401
2. 두 사용자 계좌·원장·주문·대시보드 격리, 타인 주문 ID 404
3. legacy 계좌의 명시적 1회 연결, 권한 없는 사용자 차단, 기존 행 보존
4. CSRF 없는 사용자 POST 거절, 기존 PRG 유지
5. 비운영자 수집 POST 403 및 외부 호출 없음, 로그인 사용자의 저장 일봉 읽기
6. 사용자 전환 후에도 다음 거래일 시가 체결·현금 부족·중복 체결 방지·외부 수집 미호출 유지

실행 명령:

```powershell
docker compose exec web python manage.py test trading
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
```

실제 Google OAuth 로그인은 사용자가 Google Cloud Console에서 본인 Client ID·Secret과 redirect URI를 설정한 뒤 수동으로 검증한다. Claude는 비밀값을 요청·출력·기록하지 않고, 미실행이면 인수인계에 미검증으로 남긴다.

## 제외 범위

- 실제 증권계좌, 실제 돈, 결제, 실제 주문, 자동매매, 투자 조언
- 사용자 KRX 자격증명 입력·저장, KRX 브라우저 로그인·쿠키/세션 파일, 다른 시장 데이터 제공처
- 비밀번호 로그인, Google 외 로그인, 다단계 역할·구독·결제
- T-011의 주문 입력 화면·거래 내역·설정·전체 탭 UI, 차트·관심종목·뉴스·AI 추천
- 데이터베이스 초기화·볼륨 삭제·legacy 기록 삭제·정산

## 완료 기준

1. Google 로그인은 최소 identity scope와 `.env` 기반 설정만 사용하며 비밀값이 코드·Git·DB·로그·응답에 없다.
2. 사용자마다 가상계좌가 하나뿐이고, 원장·주문·대시보드·포트폴리오가 완전히 분리된다.
3. 기존 legacy 계좌와 연결 행은 보존되며, 허용된 본인 이메일의 명시적 1회 연결만 가능하다.
4. 비로그인 HTML/JSON, CSRF, 타인 주문 ID, 비운영자 수집이 안전하게 차단된다.
5. 공용 일봉은 로그인 사용자가 읽을 수 있고, KRX 수집은 초기 소유자만 수동 실행한다.
6. 실제 돈·증권사·결제·실주문 경로가 추가되지 않고 기존 다음 거래일 시가 체결 원칙이 유지된다.
7. 전체 Django 테스트·check·migration dry-run 결과와 실제 OAuth 수동 확인 여부가 인수인계에 구분돼 있다.

## Claude Code 완료 보고

`docs/handoffs/T-010-claude-handoff.md`에 다음을 기록한다.

- 변경·생성 파일 전체 목록과 완료 기준별 구현 위치
- 새 의존성의 실제 lock 버전과 OAuth 설정값 비노출 근거
- migration 전후 legacy 계좌·원장·주문 보존 검증과 사용자 A/B 격리 결과
- 자동 테스트, check, migration dry-run, 실제 Google OAuth 수동 검증을 구분한 명령·결과
- 가정, 알려진 제한, 사용자에게 필요한 Google Cloud Console 설정, 미해결 항목

논리적인 커밋을 만들되 **push, PR 생성, 병합은 하지 않는다.** 완료 후 커밋 해시와 인수인계 경로를 Codex에 보고한다.
