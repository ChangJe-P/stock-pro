---
task_id: T-009
branch: codex/ui
commit: 9c1e8dd
status: complete
---

# Claude Code 구현 인수인계

> 갱신(2026-10-01): Codex 검토 P1(양수 + 부호)·P2(1024/768·손실 상태 브라우저 확인) 대응. 구현 `176acce`, 최초 인수인계 `719ae46`, P1 수정 `9c1e8dd`. 아래 "Codex 검토 대응" 절 참조.

## Codex 검토 대응 (P1, P2)

| 지적 | 대응 | 근거 |
|---|---|---|
| P1 — 양수 손익·수익률에 `+` 부호가 없음(완료 기준 4의 색 외 부호 표현 미적용) | `dashboard.html`에서 state=positive일 때만 총 평가손익·총 수익률·보유 종목 평가손익·수익률에 `+` 접두. 음수는 기존 `-` 유지, 중립은 무부호. 계산 서비스·context 계약 불변 | `SignRenderTests` 3건: 양수 `+20000`·`+20.00%`·`+2.00%`, 음수 `-20000`·`-20.00%`(`+-` 금지), 중립 무부호 |
| P2 — 1024/768·손실 상태 브라우저 직접 확인 없음 | P1 수정 후 Compose `web`에서 1024px·768px(이익)·손실(파랑) 상태를 브라우저로 직접 확인(아래 수동 확인 표 갱신). 손실은 저장 종가를 임시로 낮춰 표시만 확인한 뒤 원복(계좌·주문·수집 미실행) | 아래 "실제 Docker Compose + 브라우저 수동 확인" |

## 작업 요약

- 구현한 내용: `/`(대시보드)와 `/setup`(시작·데이터 준비)의 Django Template과 static CSS만 개선했다. 공통 header navigation을 두고, 대시보드는 실제 데이터를 금융 화면 3영역(좌: 평가 기준, 중: 계좌 요약·보유 종목, 우: 최근 주문)으로 배치했다. `/setup`은 실제 3단계 학습 흐름(가상계좌 시작 → 일봉 수동 수집 → 대시보드 확인)을 시각적으로 정리했다. 국내 주식 관례대로 상승·이익은 빨강, 하락·손실은 파랑으로 상태색을 반전하고 `이익`/`손실`/`변동 없음` 텍스트·부호를 유지했다. 반응형(1440/1024/768/375)과 모바일 card형 표를 유지했다.
- 바꾸지 않은 것: `views.py`·서비스·models·migrations·API 경로·form action·CSRF·PRG·template context key·DB schema·Docker Compose·환경변수·의존성. JavaScript·CDN·외부 폰트/이미지/아이콘/CSS 라이브러리·새 framework를 추가하지 않았다.

## 변경·생성 파일

| 파일 | 작업 |
|---|---|
| backend/templates/trading/dashboard.html | 공통 header nav 추가, else 분기의 실제 데이터 영역을 `.dashboard-grid`(좌/중/우 3영역)로 감쌈. 기존 context 분기·빈/계산 불가 안내·`data-label` 유지 |
| backend/templates/trading/setup.html | 공통 nav 유지 + `학습 시작 순서`(3단계 흐름) 섹션 추가. 기존 form action·CSRF·오류·수집 결과 조건 유지 |
| backend/trading/static/trading/dashboard.css | 상태색 반전(--up 빨강/--down 파랑), desktop 3열 grid, ≤768 card형 표·2열 타일, ≤440 1열, `--maxw` 확대, focus 유지. 픽셀 값 하드코딩 테스트 없음 |
| backend/trading/tests.py | render 계약·읽기 전용 회귀 테스트 3건 추가 |
| docs/handoffs/T-009-claude-handoff.md | 본 문서 |

## 완료 기준 대조 (요구사항별 구현 위치)

| 완료 기준 | 구현 위치 | 판정 |
|---|---|---|
| 1. 가상 학습 장부 명시 + 실제 두 화면만 nav 연결 | 두 template의 header tagline/disclaimer + `.site-nav`(/, /setup만) | 충족 |
| 2. 대시보드가 실제 계좌·평가 기준·보유·최근 주문만 밀도 있게, 가짜 위젯 없음 | `.dashboard-grid` 3영역, 기존 context만 사용, 빈/계산 불가 안내 유지 | 충족 |
| 3. `/setup` 기존 초기화·수집 form·결과 유지 + 3단계 흐름 설명 | `flow-guide` 섹션 추가, form/CSRF/PRG/결과 분기 불변 | 충족 |
| 4. 상승/이익 빨강·손실/하락 파랑 + 텍스트·부호 병행 | CSS `--up`/`--down`, `.state-*`; template의 `이익/손실/변동 없음` + 양수 `+`·음수 `-` 부호(P1 수정); 브라우저에서 이익(빨강)·손실(파랑)·부호 확인 | 충족(P1 수정) |
| 5. 1440/1024/768/375 읽힘, 모바일 표 가로 스크롤 미의존 | grid `@media(min-width:1025px)`, 표 stack `@media(max-width:768px)`+`data-label`, 타일 2열/1열; 1440·1024·768·375 브라우저 직접 확인(P2) | 충족(수동 확인 완료) |
| 6. Django Template·static CSS·semantic만, 새 리소스 없음 | JS/CDN/외부 리소스 없음, 기존 CSS 1개 재구성 | 충족 |
| 7. context·URL·API·form/CSRF·GET 읽기 전용·PRG·계산/수집/주문·DB schema 불변 | view/service/model/migration/compose 미변경(아래 근거) | 충족 |
| 8. render 회귀·전체 테스트·check·migration dry-run과 수동 확인 구분 기록 | 아래 실행과 검증 | 충족 |

## 실행과 검증

### 먼저 실패한 render 테스트 → 이후 통과 (Task 1→2)

- `UiRefreshRenderTests`를 먼저 추가하고 실행해 **2건 실패** 확인: 대시보드에 공통 nav(`href="/setup"`) 없음, `/setup`에 3단계 흐름의 `대시보드 확인` 문구 없음. (읽기 전용 회귀 1건은 처음부터 통과.)
- template/CSS를 최소 변경한 뒤 재실행해 **전부 통과**.

### 자동 테스트 (로컬 .venv + Docker Postgres 테스트 DB, pykrx mock)

| 명령 | 결과 |
|---|---|
| `python manage.py check` | System check identified no issues |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test trading` | **Ran 67 tests … OK**(기존 61 + T-009 render 3 + 부호 회귀 3) |

기존 GET 읽기 전용·CSRF·PRG·수집 입력 검증·계좌 반복 초기화·JSON API 테스트는 삭제·약화하지 않았고 모두 통과한다.

> 참고: 위 명령은 로컬 `.venv`에서 실행했다(Compose `exec web` 대신). `web` 컨테이너는 아래 화면 확인에 사용했다.

### 실제 Docker Compose(web) + 브라우저 수동 확인 (자동 테스트와 별도)

template/CSS 변경 반영을 위해 `docker compose up -d --build web`로 재생성한 뒤, 기존 개발 DB의 계좌·보유·주문 데이터를 **읽기 전용으로만** 사용해 확인했다(계좌 생성·수집·체결을 새로 하지 않음).

| 폭 | 확인 결과 |
|---|---|
| 1440px `/` | 좌(평가 기준)·중(계좌 요약 타일 + 보유 종목 표)·우(최근 주문) 3영역 비교 배치. 총 평가손익·수익률·종목 손익이 **빨강(이익)**, 양수에 `+` 부호 표시 |
| 1440px `/setup` | 공통 nav + `학습 시작 순서` 3단계(가상계좌 시작/일봉 수동 수집/대시보드 확인) 가로 배치, 계좌·수집 form 유지 |
| 1024px `/` | 3열 grid가 단일 열로 전환(3열은 1025px 이상에서만). 계좌 요약·보유·주문 모두 읽힘. 양수 `+29 이익`·`+0.00%` 빨강 |
| 768px `/` | 계좌 요약 타일 **2열**, 보유·주문 표는 `data-label` card형(가로 스크롤 없음). 양수 빨강·`+` 부호 유지 |
| 375px `/` | 헤더 → 평가 기준 → 계좌 요약(1열 타일) → 보유 종목 → 최근 주문 순 단일 열. 표 card형, 가로 스크롤 없음 |
| 손실 상태 `/` (760px) | 저장 종가를 임시로 낮춰(원복함) 확인: 총 평가손익 `-304 손실`·총 수익률 `-0.00%`·종목 `-304 손실`·`-10.12%`가 **파랑**으로, 음수 `-` 부호로 표시 |

- 손실 상태는 저장된 일봉 종가(`005930` 2024-01-03)를 임시로 낮춰 화면 표시만 확인한 뒤 원래 값(1011)으로 **원복**했다. 계좌 생성·일봉 수집·주문 체결은 실행하지 않았다(가격 행 1건의 일시 수정·원복만).
- 1024/768/손실 상태 모두 브라우저로 직접 확인했다(위 표). 자동 테스트(부호·render 계약)와 구분해 기록한다.

## GET 읽기 전용·불변 근거

- `backend/trading/views.py`, 서비스, models, migrations, API urls, Docker Compose, requirements는 diff에 없다(UI-only). `makemigrations --check`=No changes.
- template은 기존 context key와 form `action`/`{% csrf_token %}`을 그대로 사용한다. `UiRefreshRenderTests.test_dashboard_still_read_only_on_render`가 GET `/`·`/setup`이 계좌·주문·원장·가격 행을 만들지 않고 pykrx를 호출하지 않음을 재확인한다.

## 가정과 제한

- 상태색은 T-009 결정(상승·이익 빨강, 하락·손실 파랑)이 기존 UI 참고 문서의 일반 색 예시보다 우선한다는 지침을 따랐다.
- KRW는 raw 정수로 표시한다(천 단위 구분 기호 humanize 앱 미도입, 범위 밖). 단위·기준일·출처는 함께 표시한다.
- 손실(파랑) 상태 확인은 저장 종가 1건을 일시 수정·원복해 수행했다(앱 흐름으로 데이터 생성 안 함).

## 미해결 항목과 다음 제안

- main/dev로의 병합·push·PR은 규칙에 따라 하지 않았다. Codex 재검증 후 진행.

## 최종 보고
- 커밋: `176acce`(구현), `719ae46`(최초 인수인계), `9c1e8dd`(P1 수정: 양수 + 부호)
- 인수인계 파일: `docs/handoffs/T-009-claude-handoff.md`
