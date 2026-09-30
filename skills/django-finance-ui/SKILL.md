---
name: django-finance-ui
description: Build or review Jumong's Django Template finance screens using only existing virtual-investment data. Use for dashboard or setup UI work; never for charts, trading features, market-data collection, or frontend framework changes.
---

# 주몽 Django 금융 화면

## 적용 전 확인

- `AGENTS.md`, `docs/PROJECT_SPEC.md`, 현재 T-XXX 작업 문서, `docs/UI-DESIGN-REFERENCE.md`를 먼저 읽는다. 현재 작업 문서가 이 Skill보다 우선한다.
- UI 작업 전에는 다음 Claude Code Skill을 읽는다.
  - `C:\Users\박창제\.claude\skills\ui-ux-pro-max\SKILL.md`
  - `C:\Users\박창제\.claude\skills\frontend-design\SKILL.md`
- 화면 구성이나 context 값의 표시 기준이 불명확하면 추측하지 말고 Codex에 질문한다.

## 화면 경계

- Django Template, semantic HTML, Django static CSS만 사용한다. JavaScript, 새 frontend framework, CSS/icon library, CDN, 외부 폰트·이미지·차트 라이브러리를 추가하지 않는다.
- 현재 view가 전달하는 실제 계좌, 평가 기준, 보유 종목, 최근 주문, 계좌 시작·수동 일봉 수집 데이터만 재배치한다. 데이터가 없으면 빈 위젯·가짜 숫자·미구현 버튼 대신 이유와 다음 행동을 표시한다.
- `GET /`와 `GET /setup`은 읽기 전용이다. 화면 작업 때문에 계좌 생성, 주문 체결, 현금 원장 쓰기, pykrx 호출, 가격 수집을 시작하거나 view/service/model/API를 바꾸지 않는다.
- 가상 학습 투자 장부, 가격 출처·평가 기준일·단위와 계산 불가 사유를 숨기지 않는다. 실제 돈·실제 주문과 혼동되는 표현을 추가하지 않는다.

## 표현과 반응형

- 밝은 중립 배경, 흰 패널, 얇은 구분선, 남색 텍스트와 절제된 강조색으로 정보 밀도를 높인다. 참고 서비스의 브랜드·이미지·문구·정확한 layout은 복제하지 않는다.
- 해당 작업이 별도 색상 결정을 하지 않으면, 상승·이익은 빨강, 하락·손실은 파랑으로 표시한다. 상태 텍스트와 `+`·`-` 부호를 함께 표시해 색상만으로 의미를 전달하지 않는다.
- `header`, `nav`, `main`, `section`, heading, `table`, `caption`, `th scope`, 연결된 `label`을 유지한다. `:focus-visible`과 충분한 대비를 제공한다.
- 1440px, 1024px, 768px, 375px를 확인한다. 작은 화면의 표는 `data-label` 등을 사용해 항목명과 값을 함께 보이고, 가로 스크롤에만 의존하지 않는다.

## 검증과 인수인계

- template render 계약과 기존 GET 읽기 전용 보장을 자동 테스트로 유지한다. CSS의 세부 픽셀 값만 고정하는 테스트는 만들지 않는다.
- `manage.py test trading`, `manage.py check`, migration dry-run을 실행하고 자동 테스트와 브라우저 화면 확인을 구분한다.
- 인수인계에는 변경 파일, 실제 표시 데이터, 반응형 확인 범위, 테스트 결과, 제한 사항을 남긴다. push·PR·병합은 하지 않는다.
