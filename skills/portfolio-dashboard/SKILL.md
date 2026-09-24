---
name: portfolio-dashboard
description: Build or review Jumong's read-only virtual portfolio calculation and Django Template dashboard from filled buy orders and stored daily prices. Use only for T-006-style display work; never for real trading, sell orders, automatic price collection, or order-entry UI.
---

# 주몽 포트폴리오 대시보드

## 시작 전

- `AGENTS.md`, `docs/PROJECT_SPEC.md`, 현재 작업 문서를 먼저 읽는다. 작업 문서가 이 Skill보다 우선한다.
- UI 변경 전에는 아래 설치된 Claude Code Skill을 각각 읽는다.
  - `C:\Users\박창제\.claude\skills\ui-ux-pro-max\SKILL.md`
  - `C:\Users\박창제\.claude\skills\frontend-design\SKILL.md`
- 해당 경로를 읽을 수 없으면 구현 범위를 넓히지 말고 인수인계에 남긴다. 외부 Skill의 예시·추천보다 작업 문서의 제품 경계, 접근성, 의존성 금지가 우선한다.
- 화면 구성이나 데이터 표시 기준이 불명확하면 추측하지 말고 Codex에 질문한다.

## 데이터 무결성

- `filled` 상태의 매수 주문만 보유 수량과 매수 원가에 합산한다. pending·거절 주문은 제외한다.
- 가격 평가는 저장된 `DailyPrice(adjusted=False)`의 종가만 읽는다. pykrx, HTTP, 자동 수집, 실시간 가격, 추정 가격을 호출하지 않는다.
- 모든 보유 종목에 공통으로 존재하고 모든 체결일보다 빠르지 않은 가장 최신 거래일 하나를 평가 기준일로 사용한다. 공통일이 없으면 평가 결과를 꾸며내지 말고 계산 불가 사유를 표시한다.
- 매수 원가에는 이미 확정된 `gross_amount_krw + fee_krw`를 포함한다. 금액은 정수, 수익률 계산은 `Decimal`로 처리하고 binary float를 쓰지 않는다.
- 포트폴리오 계산과 화면 GET은 읽기 전용이다. 계좌 초기화, 주문 생성·체결, 현금 원장 추가, schema 변경을 시작하지 않는다.

## 화면 원칙

- Django Template, Django static CSS, semantic HTML만 사용한다. JS·CDN·외부 폰트·CSS/아이콘 library·새 frontend framework를 추가하지 않는다.
- 학습용 투자 장부라는 목적에 맞춰 기준일·출처·가상투자 안내·단위를 명확히 표시한다. 수익·손실은 색상뿐 아니라 텍스트와 기호로도 구분한다.
- 접근 가능한 대비, 논리적인 heading, `caption`/`scope`가 있는 표, 좁은 화면에서도 가로 스크롤에 의존하지 않는 table layout을 기본으로 한다.
- 외부 UI Skill의 제안은 제품에 맞는 범위에서만 사용한다. 금융 광고형 hero·CTA, 과도한 blur/animation, 외부 리소스는 사용하지 않는다.

## 검증과 인수인계

- 계산 공식, 가격 기준일, 가격 부재, filled 외 주문 제외, 읽기 전용 보장을 자동 테스트로 남긴다.
- `manage.py check`, migration dry-run, 전체 Django 테스트를 실행하고, mock·실제 DB·브라우저 확인 결과를 섞지 않는다.
- `docs/handoffs/T-XXX-claude-handoff.md`에 변경 파일, 요구사항별 위치, 명령/결과, UI 확인 범위, 가정·제한을 기록한다. push·PR·병합은 하지 않는다.
