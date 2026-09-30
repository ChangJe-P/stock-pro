---
name: onboarding-data-setup
description: Build or review Jumong's Django Template start screen for one-time virtual-account initialization and explicit single-ticker daily-price collection. Use only for T-007-style onboarding; never for account resets, automatic collection, orders, or real trading.
---

# 주몽 가상투자 시작·데이터 준비

## 시작 전

- `AGENTS.md`, `docs/PROJECT_SPEC.md`, `docs/ENVIRONMENT.md`, 현재 T-XXX 작업 문서를 먼저 읽는다. 작업 문서가 이 Skill보다 우선한다.
- UI를 변경하기 전 `docs/UI-DESIGN-REFERENCE.md`, `C:\Users\박창제\.claude\skills\ui-ux-pro-max\SKILL.md`, `C:\Users\박창제\.claude\skills\frontend-design\SKILL.md`를 읽는다.
- 화면 구성·데이터 표시·오류 문구가 불명확하면 추측해 구현하지 말고 Codex에 질문한다.

## 계좌 안전 규칙

- 최초 가상 현금과 거래 가정은 backend 설정 계층에서만 읽고, 계좌 생성 때 정책 스냅샷으로 저장한다.
- 기존 `accounts.initialize_account()`을 재사용한다. 계좌가 있으면 현금·원장·정책을 재설정하거나 새 행을 만들지 않는다.
- 시작 현금 수정 form, 계좌 reset, 원장 수정·삭제, 여러 계좌 기능은 만들지 않는다.
- `GET /setup`과 `GET /`는 읽기 전용이다. 계좌 생성, 주문 체결, 원장 쓰기, 외부 수집을 시작하지 않는다.

## 일봉 수집 규칙

- 수집은 사용자가 CSRF 보호된 form을 제출한 `POST`에서만 시작한다.
- 기존 `market_data.collect_daily_prices()`과 T-002 검증 규칙을 재사용한다. ticker·기간 검증을 새 규칙으로 중복 구현하지 않는다.
- pykrx 외 제공처, 직접 HTTP, 자동 재시도·스케줄러·큐·실시간 가격을 추가하지 않는다.
- 성공 후에는 PRG 방식으로 기존 수집 실행 기록을 읽어 결과를 보여 준다. 결과에는 출처·비조정 여부·기준 시각·상태·행 수·제외 사유를 표시한다.
- 설정 오류·입력 오류·외부 조회 실패는 비밀값과 연결 문자열 없이 구분해 표시한다.

## 화면·검증

- Django Template, semantic HTML, Django static CSS만 사용한다. 새 frontend framework, JS 의존성, CDN, 외부 폰트·이미지·CSS/아이콘 library를 추가하지 않는다.
- 가상투자·수동 수집·가격 출처·기준 시각·단위를 화면에 명확히 보인다. 빈 위젯·가짜 시세·미래 기능 버튼은 만들지 않는다.
- 375px, 768px, 1024px, 1440px에서 form·오류·수집 결과가 읽히도록 확인한다.
- GET 읽기 전용, CSRF 보호, 계좌 반복 초기화 비재설정, 입력 오류에서 외부 호출 없음, 성공 수집의 PRG와 결과 표시를 자동 테스트로 남긴다.
- `manage.py check`, migration dry-run, 전체 Django 테스트를 실행한다. mock·실제 DB·Compose·실제 pykrx 네트워크 결과를 섞지 않는다.
