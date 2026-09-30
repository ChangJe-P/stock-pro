# Claude Code 구현 요청: T-007 가상투자 시작과 일봉 수동 준비 화면

## 시작 전 필독

아래 파일을 순서대로 읽고, 충돌하면 T-007 작업 문서의 범위와 완료 기준을 따른다.

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/ENVIRONMENT.md`
4. `docs/tasks/T-007-onboarding-data-setup.md`
5. `skills/virtual-trading-account/SKILL.md`
6. `skills/market-data-collector/SKILL.md`
7. `skills/onboarding-data-setup/SKILL.md`
8. `docs/UI-DESIGN-REFERENCE.md`
9. `docs/prompts/claude/UI-DESIGN-REFERENCE.md`
10. `C:\Users\박창제\.claude\skills\ui-ux-pro-max\SKILL.md`
11. `C:\Users\박창제\.claude\skills\frontend-design\SKILL.md`

현재 브랜치가 `codex/onboarding`인지 먼저 확인해줘. UI/UX Skill을 반드시 읽되, T-007의 제품 경계·데이터 무결성·의존성 금지가 우선이야.

화면 구성, 오류 상태, 수집 결과의 표시 기준이 잘 이해되지 않거나 문서에 없는 결정을 해야 한다면, 추측해서 구현하지 말고 **Codex에 먼저 질문해줘.**

## 구현 요청

T-007 작업 문서의 완료 기준을 만족하도록 Django Template 기반의 시작·데이터 준비 화면을 구현해줘.

- `GET /setup`은 읽기 전용으로 유지하고, `POST /setup/account/initialize`, `POST /setup/market-data/collect`에만 각각 계좌 최초 생성과 일봉 수집을 둬.
- 기존 `accounts.initialize_account()`과 `market_data.collect_daily_prices()`를 재사용해. 기존 JSON API의 경로·상태 코드·응답 계약은 바꾸지 마.
- 시작 가상 현금 10,000,000원은 `VIRTUAL_INITIAL_CASH_KRW` 설정과 계좌 정책 스냅샷에서만 읽어. 코드·template에 숫자를 직접 적지 말고, 기존 계좌·원장·정책은 재설정하지 마.
- Django Template form에 `{% csrf_token %}`을 사용해. 계좌 초기화와 수집 성공에는 POST-Redirect-GET을 사용하고, 수집 결과는 기존 실행 기록을 읽어 표시해. GET이나 새로고침이 외부 수집·주문 체결·원장 쓰기를 시작하면 안 돼.
- ticker·날짜·기간 검증, 설정 오류·외부 조회 실패의 안전한 처리는 T-002의 기존 규칙을 재사용해. 입력 오류는 422 HTML 응답으로 표시하고 pykrx를 호출하지 마.
- `docs/UI-DESIGN-REFERENCE.md`의 금융 대시보드 원칙을 사용하되, 실제 데이터가 없는 차트·관심 종목·주문·AI 위젯을 만들지 마. Django static CSS와 semantic HTML만 사용해.
- 계좌 reset, 시작 현금 변경 UI, 매수·매도 주문 UI, 자동 수집, 스케줄러, 다른 데이터 제공처, 새 API·테이블·migration·의존성은 이번 범위에서 제외해.

## 테스트와 인수인계

- `GET /setup` 및 기존 대시보드 GET이 읽기 전용이고 pykrx·계좌 생성·원장 쓰기를 시작하지 않음을 테스트해.
- 계좌 없음/있음, 첫 초기화/반복 초기화 비재설정, 정책 설정 오류, CSRF 보호 form을 테스트해.
- 수집 form의 ticker·날짜·기간 오류 422과 외부 호출 미발생, 성공 수집 mock·PRG·수집 실행 결과 표시, 설정 오류·외부 조회 실패·DB 오류를 테스트해.
- `python manage.py check`, `python manage.py makemigrations --check --dry-run`, 전체 Django 테스트를 실행해.
- Docker가 실행 가능하면 Compose의 `db`·`web`에서 시작 화면을 실제로 확인해. 실제 pykrx 네트워크 확인이 실패하거나 실행하지 못하면 통과로 쓰지 말고 별도 제한으로 남겨.
- `docs/handoffs/T-007-claude-handoff.md`에 변경 파일, 완료 기준별 위치, 실행 명령·결과, mock/실제 DB/Compose/실네트워크 구분, 가정·제한을 기록해.
- 논리적인 커밋을 만들되 **push, PR 생성, 병합은 하지 마.** 완료 후 커밋 해시와 인수인계 경로를 알려줘.
