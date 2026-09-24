---
task_id: T-006
branch: codex/portfolio
commit: 087ea96
status: complete
---

# Claude Code 구현 인수인계

> 갱신(2026-09-24): Codex 검토 P1 대응. 구현 `5a3bbf8`, 최초 인수인계 `1e53371`, P1 수정 `087ea96`. 아래 "Codex 검토 대응" 절 참조.

## Codex 검토 대응 (P1)

| 지적 | 대응 | 근거 |
|---|---|---|
| P1 — 0원·음수 체결 금액을 유효한 체결로 취급해 종목 원가가 0이 되고 `_pct` 0 나눗셈으로 `GET /`가 500 | `_is_complete`에 `gross_amount_krw > 0`·`fee_krw >= 0` 검증 추가(None뿐 아니라 무효 값도 불완전). `compute_portfolio`에서 계산된 종목 원가가 0 이하면 `REASON_INCOMPLETE_FILL`, 최초 가상 현금이 0 이하면 `REASON_INVALID_ACCOUNT_DATA`로 계산 불가(빈 보유 포함). 0 보정·추정 없음. template에 invalid_account_data 안내 분기 추가 | `PortfolioInvalidDataTests` 6건: 0/음수 gross·음수 fee·무효 초기현금(보유/빈)에서 예외 없이 계산 불가 반환, `GET /`가 200과 "계산할 수 없습니다" 안내, 읽기 전용(주문·원장·일봉 행 수 불변) |

## 작업 요약

- 구현한 내용: 체결(`filled`)된 가상 매수 주문과 저장된 비조정 일봉만 재사용해 보유 종목·평가 결과를 계산하는 읽기 전용 모듈(`trading/portfolio.py`)을 추가하고, 기존 `GET /` Django Template 대시보드를 이 계산 결과·기준일·출처·최근 주문을 표시하도록 개선했다. Django app static CSS 한 개와 최소 staticfiles 설정을 추가했다. 새 테이블·migration·공개 JSON API·주문/수집 form은 만들지 않았다.
- 구현하지 않은 내용(제외 범위 준수): 매도·실현손익·실제 계좌/주문·자동매매, 실시간·자동 가격 수집·pykrx 호출, 주문/계좌/수집 form, Notion·인증·다중 사용자, 차트·이력 저장, 새 frontend/CSS/JS/icon library·외부 폰트, 새 migration·DB 테이블·공개 API.

## 변경·생성 파일

| 파일 | 내용 |
|---|---|
| backend/trading/portfolio.py (신규, P1 수정) | 읽기 전용 포트폴리오 계산(보유 합산, 공통 평가 기준일 선택, 정수/Decimal 금액·수익률, 계산 불가 사유). P1: 무효 금액·원가 0 이하·무효 초기현금 안전 처리 |
| backend/templates/trading/dashboard.html (수정) | semantic HTML 대시보드: 기준일·출처, 요약 타일, 보유 종목 표, 최근 주문 표, 빈/오류/계산 불가 안내. `{% load static %}`로 CSS 연결 |
| backend/trading/static/trading/dashboard.css (신규) | 색·간격·테두리 토큰(custom property), 접근 대비, 375px stacked table, focus 유지 |
| backend/trading/views.py (수정) | `dashboard`가 `portfolio.compute_portfolio` 사용. db 오류·계좌 없음·보유 없음·계산 불가 구별 |
| backend/jumong/settings.py (수정) | `django.contrib.staticfiles` 추가, `STATIC_URL` 최소 설정 |
| backend/trading/tests.py (수정) | T-006 포트폴리오 계산·읽기 전용·template 렌더 테스트 12건 추가 |

새 migration 없음(모델·테이블 추가 없음), 새 공개 API 없음, 기존 JSON API 경로·응답 불변.

## 완료 기준 대조

| 완료 기준 | 구현 위치 또는 증거 | 판정 |
|---|---|---|
| 1. filled만 종목별 합산, pending·거절 제외 | `portfolio._aggregate_holdings`(status="filled" 필터); `test_pending_and_rejected_excluded` | 충족 |
| 2. 모든 종목 공통·최신 비조정 종가와 기준일, 기준일은 모든 체결일 이후 | `_pick_valuation_date`(교집합 ∩ `d >= latest_execution`의 max); `test_multiple_tickers_common_latest_date`(체결일 이전 후보 제외) | 충족 |
| 3. 평가금액·손익·수익률·가용현금·총자산·총손익·총수익률 정수/Decimal, 매수 수수료 원가 포함 | `compute_portfolio` 금액 정수·`_pct` Decimal 2자리, 원가=gross+fee; 무효 금액(0/음수)·원가 0 이하·초기현금 0 이하는 계산 불가로 안전 처리(P1 수정); `test_single_holding_valuation`, `test_cost_includes_fee`, `PortfolioInvalidDataTests` | 충족(P1 수정) |
| 4. 공통일 부재·불완전/무효 체결 시 외부요청·추정·0보정 없이 계산 불가+사유 | `REASON_NO_COMMON_DATE`, `REASON_INCOMPLETE_FILL`, `REASON_INVALID_ACCOUNT_DATA`; `test_no_common_date_is_unavailable`, `test_incomplete_fill_is_unavailable`, `PortfolioInvalidDataTests` | 충족(P1 수정) |
| 5. GET / 읽기 전용, 계산·기준일·출처·보유·최근주문 표시, 빈/DB/계좌 구별 | `views.dashboard` + template 분기; `DashboardRenderTests` 4건 | 충족 |
| 6. static CSS·semantic HTML만, 외부 font/CSS/JS·새 framework 없음 | dashboard.css 1개, `{% load static %}`, system font stack; JS/CDN 없음 | 충족 |
| 7. 375px~desktop 반응형, 모바일 표 가로 스크롤 미의존, 색상만으로 손익 전달 안 함 | CSS `@media(max-width:640px)` stacked + `data-label`; 손익 텍스트(이익/손실/변동 없음)+state 클래스; 브라우저 375px 확인 | 충족(브라우저 확인) |
| 8. 새 migration·테이블·공개 API·자동 수집·form 없음, 기존 JSON API 불변 | 모델 미변경(`makemigrations --check`=No changes), urls 미변경 | 충족 |
| 9. 기존 테스트 유지 + T-006 테스트 추가 | 전체 39 passed(기존 21 + T-006 계산 12 + P1 회귀 6) | 충족 |
| 10. 인수인계 작성 | 본 문서 | 충족 |

## 실행과 검증

### 자동 테스트 (Django test runner, 외부 pykrx mock, 실 네트워크 없음)

Django 테스트 DB(실제 PostgreSQL에 `test_jumong` 생성·삭제)를 사용한다. pykrx·실계좌·실주문 호출 없음.

| 명령 | 결과 |
|---|---|
| `python manage.py check` | System check identified no issues |
| `python manage.py makemigrations --check --dry-run` | No changes detected(새 migration 없음) |
| `python manage.py test trading` | **Ran 39 tests … OK**(기존 21 + T-006 계산 12 + P1 회귀 6) |

T-006 신규 테스트: 단일/복수 종목 평가, 매수 수수료 포함 원가, pending·거절 제외, 최신 공통 기준일·체결일 이전 배제, 공통일 부재 계산 불가, 불완전 체결 계산 불가, 빈 보유, GET / 읽기 전용(주문·원장·일봉 행 수 불변, 외부 fetch 미호출), template 안전 렌더(계좌 없음·빈 보유·계산 불가·DB 오류). P1 회귀(`PortfolioInvalidDataTests`): 0/음수 gross·음수 fee·무효 초기현금(보유/빈)에서 예외 없이 계산 불가, GET / 200·안내·읽기 전용.

### 실제 Docker PostgreSQL + 브라우저 확인 (자동 테스트와 별도)

로컬 Docker `db`(기존 개발 데이터)에 Django `runserver`를 붙여 `GET /`를 실제로 확인했다. 데이터를 변경하지 않았다(읽기 요청만).

- 렌더 데이터: 평가 기준일 2024-01-03, 출처 pykrx, 가용 현금 9,996,996, 총 평가금액 3,033, 총자산 10,000,029, 총 평가손익 +29(이익), 총 수익률 0.00%. 보유 005930: 수량 3, 매수 원가 3,004, 기준 종가 1,011, 평가금액 3,033, 평가손익 +29(이익), 수익률 0.97%. `filled` 1건만 반영되고 pending(수량 1)·rejected(수량 100000)는 보유에서 제외됨을 확인.
- 반응형: 데스크톱 폭과 모바일 375px 에뮬레이션에서 확인. 375px에서 요약 타일이 단일 열로 쌓이고, 보유 종목·최근 주문 표가 각 값 label을 보존한 stacked layout으로 바뀌며 가로 스크롤이 없음. static CSS가 실제 제공됨(개발 staticfiles).

### 실제 외부 네트워크 (해당 없음)

포트폴리오 계산·화면 GET은 저장 데이터만 읽고 pykrx·HTTP를 호출하지 않는다. 자동 테스트도 외부 네트워크 요청을 보내지 않는다.

## 요구사항별 구현 위치(요약)

- filled 합산·수수료 포함 원가: `portfolio._aggregate_holdings`, `_is_complete`
- 공통 평가 기준일: `portfolio._pick_valuation_date`
- 금액/수익률 규칙: `compute_portfolio`(정수), `_pct`(Decimal, ROUND_HALF_UP, 2자리), `_state`
- 계산 불가/빈 상태: `_unavailable_summary`, `_empty_summary`, template 분기
- 읽기 전용 GET: `views.dashboard`
- CSS/semantic/반응형: `dashboard.css`, `dashboard.html`

## 가정과 제한

- 매수 원가·평가는 계좌에 저장된 정책·체결 값과 저장 일봉만 사용한다. 매도 수수료·세금은 적용하지 않는다(매수 수수료는 이미 원가 포함).
- 불완전 체결(수량/체결금액/수수료/체결일 누락)이 하나라도 있으면 포트폴리오 평가 전체를 `계산 불가`로 두고, 보유 수량·원가는 완전한 체결에서만 합산해 표시한다.
- 금액은 raw 정수로 표시한다(천 단위 구분 기호 humanize 앱은 범위 확대를 피해 추가하지 않음). 단위(KRW/주/%)와 기준일을 함께 표시한다.
- static은 개발 Compose용 최소 설정이다. production `STATIC_ROOT`·CDN·collectstatic 설계는 범위 밖.
- 브라우저 확인은 로컬 Docker DB + `runserver` + 375px 에뮬레이션으로 수행했다. 768/1024/1440px는 동일 컨테이너 max-width와 비-stacked 표로 데스크톱 확인에 포함된다. 실제 물리 기기 확인은 하지 않았다.

## 미해결 항목과 다음 제안

- 실제 Docker Compose `web` 컨테이너 전체 기동 하의 HTTP 확인은 후속으로 남긴다(이번 UI 확인은 로컬 `runserver` + Docker `db`).
- 천 단위 구분 표시(가독성)는 필요 시 `django.contrib.humanize`로 별도 논의.
- main/dev로의 병합·push·PR은 규칙에 따라 하지 않았다. Codex 검증 후 진행.

## 최종 보고
- 커밋: `5a3bbf8`(구현), `1e53371`(최초 인수인계), `087ea96`(P1 수정: 무효 금액·계좌 데이터 계산 불가)
- 인수인계 파일: `docs/handoffs/T-006-claude-handoff.md`
