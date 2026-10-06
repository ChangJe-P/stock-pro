# Claude Code 구현 요청: T-010 Google 로그인과 사용자별 가상계좌 기반

## 시작 전 필독

아래 파일을 순서대로 읽고, 충돌하면 T-010 작업 문서의 범위와 완료 기준을 따른다.

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

현재 브랜치가 `codex/auth`인지 확인해. 화면, OAuth 설정, legacy 이전, 권한 기준에서 문서에 없는 결정을 해야 하거나 잘 이해되지 않는 부분이 있으면 추측하지 말고 **Codex에 먼저 질문해.**

## 구현 요청

`docs/tasks/T-010-google-auth-user-accounts.md`의 완료 기준을 만족하도록 구현해.

- Google 로그인은 `django-allauth[socialaccount]==65.19.6`과 Django 세션을 사용하고, Google identity 최소 scope(`openid`, `email`, `profile`)만 요청해. 직접 OAuth 토큰 교환·custom token 저장·DB `SocialApp` 자격증명 저장을 만들지 마.
- Client ID·Secret·초기 소유자 이메일은 `.env`와 settings 계층에서만 읽어. 값이 비어 있으면 안전하게 비활성화하고, 값·길이·마스킹값·예외 원문을 template·response·로그·DB에 남기지 마.
- 실제 돈·실제 계좌·결제·증권사 API·실주문·자동매매는 어떤 코드·환경변수·외부 HTTP 요청에도 추가하지 마. KRX는 저장용 일봉 가격 데이터에만 사용하고, 사용자에게 KRX ID·비밀번호를 받거나 저장하지 마.
- `VirtualAccount`를 사용자와 1:1로 전환하고, 계좌·원장·주문·dashboard가 로그인한 사용자 것만 읽도록 바꿔. `objects.first()`나 전역 주문 조회로 사용자 데이터를 찾지 마. 타 사용자 주문 ID는 404로 처리해.
- 기존 단일 계좌는 삭제·복제·재계산하지 마. `INITIAL_OWNER_GOOGLE_EMAIL` 일치 사용자만 확인 POST로 1회 연결하도록 하고, 자동 이전이나 다른 사용자에 대한 존재 노출을 만들지 마.
- 비로그인 HTML은 `/login/`으로, 비로그인 JSON API는 정확히 401 JSON으로 처리해. 계좌·주문·수집 POST에서 `csrf_exempt`를 제거하고 CSRF·PRG를 지켜.
- 일봉은 공용 읽기 데이터로 유지해. 초기 소유자만 기존 수동 수집을 실행하고, 다른 로그인 사용자의 수집 POST는 403·외부 호출 없음이어야 해.
- 로그인 화면과 header는 실제 기능만 보여줘. 구현되지 않은 주문·내역·설정·차트·관심종목 탭, 가짜 시세, 준비 중 버튼을 만들지 마. semantic HTML·Django Template·static CSS만 사용해.

## 테스트와 인수인계

- `backend/trading/test_auth.py`에 인증·A/B 격리·legacy 1회 연결·CSRF·수집 권한·다음 거래일 시가 체결 회귀의 실패 테스트를 먼저 추가하고, 실패 원인을 확인한 뒤 최소 구현으로 통과시켜.
- 기존 테스트를 삭제·약화하지 마. `docker compose exec web python manage.py test trading`, `check`, `makemigrations --check --dry-run`을 실행하고 실제 결과를 기록해.
- Google Cloud Client ID·Secret이 없는 환경의 자동 테스트와, 사용자가 나중에 직접 수행할 실제 OAuth 로그인 검증을 분리해. 비밀값을 요구·출력·기록하지 마.
- `docs/handoffs/T-010-claude-handoff.md`에 변경 파일, 완료 기준별 위치, migration/legacy 보존 증거, 테스트 결과, 수동 OAuth 미검증 여부, 사용자에게 필요한 설정, 제한 사항을 남겨.
- 논리적인 커밋은 만들 수 있지만 **push, PR 생성, 병합은 하지 마.** 완료 후 커밋 해시와 인수인계 경로를 보고해.
