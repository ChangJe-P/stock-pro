# Claude Code 구현 요청: T-006 가상 포트폴리오와 대시보드

## 시작 전 필독

아래 파일을 순서대로 읽고, 충돌하면 T-006 작업 문서의 범위와 완료 기준을 따른다.

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/ENVIRONMENT.md`
4. `docs/tasks/T-006-portfolio-dashboard.md`
5. `skills/virtual-trading-account/SKILL.md`
6. `skills/virtual-order-execution/SKILL.md`
7. `skills/portfolio-dashboard/SKILL.md`
8. `C:\Users\박창제\.claude\skills\ui-ux-pro-max\SKILL.md`
9. `C:\Users\박창제\.claude\skills\frontend-design\SKILL.md`

현재 브랜치가 `codex/portfolio`인지 확인한 뒤 구현해줘. UI/UX Skill은 반드시 읽되, 이 작업 문서의 범위·접근성·의존성 금지가 우선이야.

화면 구성이나 데이터 표시 기준이 잘 이해되지 않거나 이 문서에 없는 결정이 필요하면, 추측해서 구현하지 말고 **Codex에 질문해줘.**

## 구현 요청

체결된 가상 매수 주문과 저장된 일봉을 재사용해, 읽기 전용 Django 대시보드에 보유 종목과 평가 결과를 표시해줘.

- 새 `virtual_positions` 테이블, migration, 새 공개 JSON API를 만들지 마. `VirtualBuyOrder(status="filled")`를 종목별로 합산하는 읽기 전용 계산 모듈을 추가하고 `GET /`에서만 사용해줘.
- 기존 `accounts.available_cash(account)`을 재사용해. 계산·화면 GET이 계좌 초기화, 주문 생성·체결, 원장 쓰기, pykrx·HTTP 가격 수집을 시작하면 안 돼.
- `filled` 주문의 `quantity`, `gross_amount_krw + fee_krw`로 보유 수량·매수 원가를 계산해. pending·`rejected_insufficient_cash` 주문은 제외해.
- 저장된 `DailyPrice(adjusted=False)`의 `close_price`만 사용해. 모든 보유 종목에 공통으로 있고 모든 체결일보다 빠르지 않은 가장 최신 거래일을 한 개의 평가 기준일로 선택해줘. 같은 계좌에 서로 다른 날짜의 가격을 섞지 마.
- 공통 기준일이 없거나 filled 주문의 필수 체결값이 불완전하면 가격을 수집·추정·0 보정하지 말고, 평가금액·평가손익·수익률·총자산을 계산 불가로 표시해. 보유 수량과 매수 원가는 가능한 경우 보여주고, 필요한 일봉을 수동으로 수집해야 한다는 안전한 안내를 보여줘.
- 계산 가능할 때 보유 종목마다 보유 수량, 매수 원가(매수 수수료 포함), 기준 종가·출처, 평가금액, 평가손익, 수익률을 표시해. 계좌 요약에는 가용 현금, 총 평가금액, 총자산, 총 평가손익, 총 수익률을 표시해.
- KRW는 정수로, 수익률 중간 계산은 `Decimal`로 처리해. 수익률은 소수 둘째 자리까지 표시하고 binary float를 쓰지 마. 매도 수수료·세금은 적용하지 마.
- 보유 종목이 없을 때는 평가 기준일 없이 빈 상태를 명확히 보여줘. 계좌 없음과 DB 연결 실패도 기존 대시보드의 안내와 구별해 안전하게 유지해.

## UI 요청

- 기존 `backend/templates/trading/dashboard.html`을 Django Template으로 유지하고, Django app static CSS 파일 한 개를 추가해 `{% load static %}`로 연결해줘. 현재 설정에 없으므로 Django 내장 `django.contrib.staticfiles`와 `STATIC_URL`을 최소로 설정해 개발 Compose에서 CSS가 실제로 제공되게 해줘. 새 패키지나 production static 배포 설계는 추가하지 마.
- semantic HTML만 사용해. `header`, `main`, `section`, heading, table `caption`, `th scope`, empty/error 안내를 활용해줘.
- JS, CDN, 외부 폰트·이미지, Bootstrap·Tailwind·React·Next.js·icon library·새 CSS library를 추가하지 마. 한글 system font stack과 Django static CSS만 사용해.
- 주몽은 금융 광고 사이트가 아니라 학습용 투자 장부야. 밝은 배경, 접근 가능한 navy/blue, 수익 emerald, 손실 red 계열을 CSS custom property로 정의해 절제되게 사용해. 큰 hero·CTA·영상·과도한 blur/shadow/animation은 만들지 마.
- 수익·손실·변동 없음은 색만으로 표현하지 말고 텍스트 상태를 보여줘. 가상투자·읽기 전용, 가격 기준일, 가격 출처, KRW/주/% 단위를 명확히 보여줘.
- 화면은 375px, 768px, 1024px, 1440px에서 읽을 수 있어야 해. 모바일에서는 보유 종목·최근 주문 표의 각 값을 label이 있는 stacked layout으로 바꿔 가로 스크롤에 의존하지 않게 해줘.
- 포트폴리오 이력 데이터가 없으므로 차트는 만들지 마. 주문 입력 form·계좌 초기화 form·데이터 수집 form도 만들지 마.

## 테스트와 인수인계

- 계산 모듈의 단일/복수 종목, 수수료 포함 원가, pending·거절 제외, 공통 기준일, 체결일 이전 날짜 배제, 공통일 부재, 불완전 체결 데이터를 테스트해줘.
- 포트폴리오 계산과 `GET /`가 외부 가격 수집·주문 체결·원장 쓰기를 시작하지 않음을 테스트해줘.
- 계좌 없음, 보유 종목 없음, DB 오류, 계산 불가 상태에서 template이 안전하게 렌더링되는지 테스트해줘.
- `python manage.py check`, `python manage.py makemigrations --check --dry-run`, 전체 Django 테스트를 실행해. 실제 DB·Compose·브라우저로 확인한 항목은 자동 테스트와 구분하고, 실행하지 못한 항목을 통과로 쓰지 마.
- Docker가 로컬에서 실행 가능하면 desktop과 좁은 모바일 폭 화면을 실제로 확인해. 불가능하면 미검증으로 인수인계에 남겨줘.
- `docs/handoffs/T-006-claude-handoff.md`에 변경·생성 파일 전체 목록, 요구사항별 구현 위치, 실행 명령/결과, 테스트 범위, UI 확인, 가정·제한·미해결 항목을 작성해줘.
- 논리적인 커밋을 만들되 **push, PR 생성, 병합은 하지 마.** 완료 후 커밋 해시와 인수인계 경로를 알려줘.
