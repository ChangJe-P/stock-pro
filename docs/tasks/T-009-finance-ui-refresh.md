---
id: T-009
title: 금융 정보 중심 Django 화면 개선
status: ready_for_claude
branch: codex/ui
owner: Claude Code
reviewer: Codex
depends_on: T-006, T-007, T-008
---

# T-009 금융 정보 중심 Django 화면 개선

## 목표

현재 동작하는 대시보드(`/`)와 시작·데이터 준비 화면(`/setup`)을, 주몽의 실제 가상투자 데이터를 더 빠르게 훑을 수 있는 밝고 밀도 있는 금융 화면으로 개선한다. 알파스퀘어는 **정보 우선순위와 금융 화면의 밀도만** 참고하며, 화면·문구·상표·이미지·아이콘·정확한 배치를 복제하지 않는다.

이번 작업은 화면 구조와 Django static CSS만 다룬다. 계산, 수집, 주문, 계좌 초기화, API, DB 스키마의 동작은 바꾸지 않는다.

## 화면 결정

### 공통

- 서비스명은 `주몽`으로 유지하고, `가상 학습 투자 장부` 및 실제 돈·주문과 무관한 상태를 화면에서 계속 명시한다.
- `/`와 `/setup`에 실제 존재하는 두 화면으로 이동하는 간결한 navigation을 둔다. 검색, 관심종목, 차트, 매수·매도, AI 추천처럼 아직 동작하지 않는 요소는 만들지 않는다.
- 밝은 중립 배경, 흰 패널, 얇은 구분선, 짙은 남색 텍스트, 절제된 빨간 강조색을 사용한다. 외부 이미지·로고·아이콘·폰트 없이 텍스트와 CSS만 사용한다.
- 국내 주식 화면의 관례에 맞춰 **상승·이익은 빨강**, **하락·손실은 파랑**으로 표시한다. 색상만 쓰지 않고 `이익`·`손실`·`변동 없음` 텍스트와 `+`·`-` 부호를 함께 남긴다. 이 색상 결정은 기존 UI 참고 문서의 일반 색상 예시보다 T-009에서 우선한다.
- 키보드 focus 표시, 충분한 대비, 논리적인 heading, `caption`·`scope`가 있는 표, 한글 system font stack을 유지한다.

### 대시보드 `/`

- desktop(1025px 이상)에서는 실제 데이터를 세 영역으로 배치해 금융 화면처럼 정보를 비교하기 쉽게 만든다.
  - 좌측: 평가 기준일·가격 출처·단위처럼 현재 평가를 해석하는 실제 정보
  - 중앙: 계좌 요약과 보유 종목 표
  - 우측: 실제 최근 매수 주문 또는 현재 상태 안내
- 보유 종목, 가격 기준일, 최근 주문이 없을 때는 빈 카드·가짜 차트·임의 수치를 만들지 않고, 기존의 이유와 다음 행동 안내를 유지한다.
- 1024px 이하는 보조 영역을 본문 아래로, 768px 이하는 계좌 요약을 2열 또는 1열로, 375px 이하는 `헤더 → 상태/기준일 → 계좌 요약 → 보유 종목 → 최근 주문` 순서의 한 열로 쌓는다.
- 모바일 표는 가로 스크롤에 의존하지 않는다. 현재 `data-label`을 재사용해 각 수치의 항목명을 표시한다.

### 시작·데이터 준비 `/setup`

- 같은 공통 header·navigation·색 토큰을 사용한다.
- 사용자가 이해할 수 있도록 실제 동작 순서를 `가상계좌 시작 → 일봉 수동 수집 → 대시보드 확인`으로 시각적으로 정리한다.
- 최초 가상 현금, 정책 버전, 입력 form, 수집 결과, 오류·안내의 현재 데이터와 문구를 유지한다. 새 입력, reset, 자동 수집, 주문 입력을 만들지 않는다.

## 구현 범위와 파일

| 파일 | 작업 |
|---|---|
| `backend/templates/trading/dashboard.html` | 공통 header/navigation, dashboard 정보 영역, semantic class를 정리한다. 기존 template context와 조건 분기를 유지한다. |
| `backend/templates/trading/setup.html` | 공통 header/navigation과 실제 3단계 흐름 안내를 정리한다. 기존 form action, CSRF token, 오류·수집 결과 조건을 유지한다. |
| `backend/trading/static/trading/dashboard.css` | CSS custom property, desktop grid, 모바일 table/card, focus와 상태 색상을 최소로 재구성한다. |
| `backend/trading/tests.py` | template render 계약과 읽기 전용 보장을 회귀 테스트한다. CSS의 픽셀 값을 문자열로 고정하는 테스트는 만들지 않는다. |
| `docs/handoffs/T-009-claude-handoff.md` | Claude가 구현·검증 후 작성한다. |

`backend/trading/views.py`, 서비스 계층, models, migrations, API 경로, Docker Compose, 의존성 파일은 이번 작업에서 변경하지 않는다.

## 구현 순서

### Task 1: 화면 render 계약을 먼저 고정

- [ ] `backend/trading/tests.py`에 대시보드와 `/setup`이 공통 navigation, 가상 학습 투자 안내, 기존 실제 데이터 영역을 렌더링하는 테스트를 먼저 작성한다.
- [ ] 새 테스트를 실행해, 새 UI semantic class 또는 navigation이 아직 없어 실패하는 것을 확인한다.
- [ ] 기존 GET 읽기 전용·CSRF·POST-Redirect-GET·수집 입력 검증·계좌 반복 초기화 테스트는 삭제하거나 약화하지 않는다.

### Task 2: Django Template과 CSS를 최소 변경

- [ ] `dashboard.html`과 `setup.html`에 공통적인 의미 구조와 class를 추가하되, view가 전달하는 context key와 기존 URL name·form action은 바꾸지 않는다.
- [ ] desktop에서 실제 평가 기준/계좌/주문 정보가 비교되도록 CSS grid를 적용하고, 현재 데이터가 없는 영역은 안내만 표시한다.
- [ ] `dashboard.css`에서 색, 간격, 경계선, 반응형 layout, focus, 상태 색을 정의한다. JavaScript, CDN, 외부 파일, 새 dependency는 추가하지 않는다.
- [ ] 새 render 테스트와 기존 전체 Django 테스트가 모두 통과하도록 최소 수정한다.

### Task 3: 반응형·읽기 전용 확인

- [ ] 1440px, 1024px, 768px, 375px에서 `/`와 `/setup`을 직접 확인한다. 표 항목명, form label, 상태 안내, 핵심 수치를 모두 읽을 수 있어야 한다.
- [ ] `GET /`과 `GET /setup`이 계좌 생성·주문 체결·원장 쓰기·가격 수집을 시작하지 않는 기존 자동 테스트를 다시 실행한다.
- [ ] 화면 확인 중 실제 데이터를 만들기 위해 계좌 생성이나 일봉 수집을 실행하지 않는다. 필요한 검증 데이터가 이미 있으면 이를 읽기 전용으로만 사용한다.

## 검증 명령

Claude는 다음을 순서대로 실행하고 실제 결과를 인수인계에 남긴다.

```powershell
docker compose exec web python manage.py test trading
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run
```

Docker를 실행할 수 없으면 로컬 가상환경의 동등한 명령을 실행하고, Compose 확인을 통과로 표현하지 않는다. 브라우저 수동 확인은 자동 테스트와 구분해 기록한다.

## 제외 범위

- 실제 또는 가상 주문 입력·수정·취소·매도, 실제 계좌, 자동매매
- 차트, 관심 종목, 종목 검색, AI 추천, 시장 뉴스, 실시간 시세, 자동 수집
- 계좌 reset, 시작 현금·거래 가정 변경 UI, Notion API
- FastAPI·Next.js 재도입, JavaScript, 새 frontend framework, CSS/icon library, 외부 CDN·폰트·이미지
- view/service/model/API/DB schema/migration/Compose/환경변수 변경

## 완료 기준

1. `/`와 `/setup`이 주몽의 가상 학습 투자 장부임을 명확히 보이고, 실제 존재하는 두 화면만 navigation으로 연결한다.
2. 대시보드는 기존 실제 계좌·평가 기준·보유 종목·최근 주문만 정보 밀도 있게 배치하며, 가짜 차트·시세·버튼·위젯을 만들지 않는다.
3. `/setup`은 기존 계좌 초기화·일봉 수집 form·수집 결과를 유지하면서 실제 3단계 학습 흐름을 설명한다.
4. 수익/상승은 빨강, 손실/하락은 파랑이며, 색 이외에 상태 텍스트와 부호로도 구분한다.
5. 1440px, 1024px, 768px, 375px에서 핵심 정보·form label·오류가 읽히고, 모바일 표가 가로 스크롤에만 의존하지 않는다.
6. Django Template, static CSS, semantic HTML만 사용하며 새 framework·dependency·외부 리소스를 추가하지 않는다.
7. template context, URL, API, form action/CSRF, GET 읽기 전용, PRG, 계산·수집·주문 규칙과 DB schema가 변하지 않는다.
8. render 회귀 테스트, 전체 Django 테스트, `check`, migration dry-run 결과와 화면 수동 확인 범위를 구분해 기록한다.

## Claude Code 완료 보고

`docs/handoffs/T-009-claude-handoff.md`에 다음을 남긴다.

- 변경·생성 파일 전체 목록과 완료 기준별 구현 위치
- 먼저 실패한 render 테스트와 이후 통과 결과, 전체 Django 테스트·check·migration dry-run 명령 및 결과
- 1440px·1024px·768px·375px에서 `/`·`/setup`을 확인한 범위와 사용한 데이터 상태
- GET 읽기 전용, form CSRF/PRG, 기존 JSON API·DB schema·외부 수집 미변경의 근거
- 가정, 알려진 제한, 미해결 항목

논리적인 커밋을 만들되 **push, PR 생성, 병합은 하지 않는다.** 완료 뒤 커밋 해시와 인수인계 경로를 보고한다.
