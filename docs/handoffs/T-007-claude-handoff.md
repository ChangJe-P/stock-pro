---
task_id: T-007
branch: codex/onboarding
commit: b97e6f1
status: complete
---

# Claude Code 구현 인수인계

## 작업 요약

- 구현한 내용: Django Template 기반의 시작·데이터 준비 화면을 추가했다. `GET /setup`은 읽기 전용으로 가상 학습 계좌 상태와(있으면) 최근 수집 실행 결과를 보여 준다. `POST /setup/account/initialize`는 기존 one-time 계좌 초기화를 재사용해 최초 계좌만 만들고, `POST /setup/market-data/collect`는 사용자가 입력한 한 종목·기간의 일봉을 기존 pykrx 수집 함수로 한 번 수집한다. 두 POST 모두 CSRF 보호 form이며 성공 시 303 PRG로 이동한다. 기존 JSON API 경로·상태·응답과 대시보드 `GET /`는 변경하지 않았다.
- 구현하지 않은 내용(제외 범위 준수): 계좌 재설정·시작 현금 변경 UI, 매수·매도 주문/체결 화면, 자동 수집·스케줄러·다른 제공처, 관심 종목·차트·가짜 시세·AI 위젯, 새 공개 JSON API·DB 테이블·migration·의존성.

## 변경·생성 파일

| 파일 | 내용 |
|---|---|
| backend/trading/views.py (수정) | `setup`(GET 읽기 전용), `setup_account_initialize`(POST, CSRF), `setup_market_data_collect`(POST, CSRF) + 공통 `_setup_context`. 기존 검증 헬퍼(`_require_ticker`/`_require_date`)·서비스 재사용 |
| backend/jumong/urls.py (수정) | `/setup`, `/setup/account/initialize`, `/setup/market-data/collect` 경로 추가(기존 경로 불변) |
| backend/templates/trading/setup.html (신규) | semantic HTML 시작·데이터 준비 화면(계좌 상태, CSRF form, 수집 form, 수집 결과) |
| backend/trading/static/trading/dashboard.css (수정) | nav·key-value·form·버튼·stacked 표 스타일을 기존 토큰으로 최소 확장 |
| backend/trading/tests.py (수정) | T-007 화면·흐름 테스트 12건 추가 |

새 migration·모델·공개 API·의존성 없음. `makemigrations --check`=No changes.

## 완료 기준 대조 (요구사항별 구현 위치)

| 완료 기준 | 구현 위치 | 판정 |
|---|---|---|
| 1. GET /setup 읽기 전용, pykrx·쓰기 없음 | `views.setup`/`_setup_context`(조회만); `test_get_setup_is_read_only` | 충족 |
| 2. 계좌 없음: 검증 정책의 시작현금·버전 + CSRF 생성 form | `_setup_context`(load_virtual_policy), setup.html; `test_get_setup_no_account_shows_start_cash_and_form` | 충족 |
| 3. 생성 POST는 one-time 재사용, 반복 POST 비재설정 | `setup_account_initialize`→`accounts.initialize_account`; `test_post_initialize_creates_account_and_redirects_303`, `test_repeat_initialize_does_not_reset` | 충족 |
| 4. 계좌 있음: 최초/가용 현금·버전, 재설정 경로 없음 | setup.html 분기; `test_get_setup_with_account_hides_reset` | 충족 |
| 5. 수집 form 서버 검증, 잘못된 입력 422·외부 미호출 | `setup_market_data_collect`(T-002 헬퍼); `test_collect_bad_input_is_422_without_external_call`, `test_csrf_protected_forms` | 충족 |
| 6. 유효 POST만 수집 1회 호출, 성공 PRG로 결과 표시 | `collect_daily_prices` 1회 + 303 `?collection_run=`; `test_collect_success_prg_and_result_display` | 충족 |
| 7. 결과에 출처·비조정·기준시각·상태·행수·제외사유 표시 | setup.html 수집 결과 표; 실DB 브라우저 확인 | 충족 |
| 8. 설정 오류·조회 실패·DB 오류 안전 처리(비밀값 없음) | ApiError 상태 재렌더(503/502), `_setup_context` db_error; `test_collect_config_error_is_safe`, `test_collect_fetch_failure_is_safe` | 충족 |
| 9. 기존 JSON API·/health·대시보드 읽기 전용·T-001~T-006 유지 | urls 기존 경로 불변, csrf_exempt 불변; 전체 51 테스트 통과 | 충족 |
| 10. check·migration dry-run·전체 테스트, 검증 구분 기록 | 아래 실행과 검증 | 충족 |

## 실행과 검증

### 자동 테스트 (Django test runner, 외부 pykrx mock, 실 네트워크 없음)

Django 테스트 DB(실제 PostgreSQL `test_jumong` 생성·삭제). pykrx는 `patch`로 mock, 실계좌·실주문·실네트워크 없음.

| 명령 | 결과 |
|---|---|
| `python manage.py check` | System check identified no issues |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test trading` | **Ran 51 tests … OK**(기존 39 + T-007 12) |

T-007 신규 테스트: GET /setup 읽기 전용(행 수 불변·fetch 미호출), 계좌 없음 시작현금·form, 첫 초기화 303·계좌 생성, 반복 초기화 비재설정, 계좌 있음 재설정 숨김, 정책 오류 버튼 숨김, CSRF 보호(403), 수집 입력 오류 422·외부 미호출, 수집 성공 PRG·결과 표시, 설정 오류 503, 조회 실패 502(메시지에 원 예외 미노출), 없는 run_id 안전 안내.

### 실제 Docker Compose(db·web) + 브라우저 확인 (자동 테스트와 별도)

로컬 Docker에서 `docker compose up -d --build`로 `db`·`web`을 기동해 실제로 확인했다(읽기 GET만, 계좌 생성·수집 POST는 실행하지 않음).

- `GET /setup` HTTP 200, `GET /health` 200. 기존 개발 DB에 계좌가 있어 계좌 상태 표시(최초 10,000,000 / 가용 9,996,996 / 정책 v1), 재설정 버튼 없음. 수집 form(종목·시작일·종료일 label·help)과 CSRF 토큰 렌더 확인.
- `GET /setup?collection_run=<기존 run_id>`로 수집 결과 표 확인: 종목 000660, 요청 기간 2024-01-01~2024-01-05, 출처 pykrx, 비조정(adjusted=False), 수집 기준 시각, 상태 partial — all_rows_excluded, 반환 2·삽입 0·갱신 0·제외 2, 제외 사유 duplicate_date 1·non_positive_price 1. GET이 외부 수집을 시작하지 않고 저장 기록만 표시함을 확인.
- 반응형: 데스크톱과 375px 에뮬레이션에서 확인. 375px에서 계좌·form·결과가 한 열로 쌓이고, 결과 key-value 표는 각 항목 label을 보존한 stacked 카드로 바뀌며 가로 스크롤이 없음. static CSS 실제 제공.

### 실제 pykrx 네트워크 (미검증)

실제 pykrx 네트워크 수집(폼 제출 → 실제 KRX 조회)은 이 확인에서 실행하지 않았다. 이전 작업들에서 현재 환경의 pykrx 공개 응답이 빈 결과였고, 브라우저 확인은 읽기 GET과 기존 저장 실행 기록으로만 수행했다. **실제 네트워크 수집 성공은 통과로 기록하지 않는다.** 코드 경로(설정 확인→pykrx 1회→검증→저장→PRG)는 mock 테스트와 실DB 저장 기록 표시로 확인했다.

## 가정과 제한

- 시작 가상 현금·정책 버전은 계좌가 없을 때 `load_virtual_policy()`(설정 계층), 계좌가 있으면 `VirtualAccount` 스냅샷에서만 읽는다. 화면·서비스 코드에 금액 숫자를 하드코딩하지 않았다.
- KRW 금액은 raw 정수로 표시한다(천 단위 구분 기호 humanize 앱은 범위 확대를 피해 추가하지 않음). 단위(KRW/주)와 기준 시각·출처를 함께 표시한다.
- 설정 오류(503)·외부 조회 실패(502)·입력 오류(422)는 같은 화면에 재렌더하며 상태 코드로 구분한다. 성공만 303 PRG로 이동한다.
- `collection_run` 파라미터는 임의 문자열도 안전하게 처리한다(일치하는 실행 기록이 없으면 안내만, DB 쓰기 없음).
- setup POST view는 CSRF 보호를 사용하며, 기존 JSON POST API의 `csrf_exempt` 동작은 바꾸지 않았다.

## 미해결 항목과 다음 제안

- 실제 pykrx 네트워크 수집 성공 확인은 접근 가능한 환경에서 폼 제출로 재검증 필요(현재 미검증).
- 천 단위 구분 표시(가독성)는 필요 시 `django.contrib.humanize`로 별도 논의.
- main/dev로의 병합·push·PR은 규칙에 따라 하지 않았다. Codex 검증 후 진행.

## 최종 보고
- 커밋: `b97e6f1`(구현), 본 인수인계는 별도 커밋
- 인수인계 파일: `docs/handoffs/T-007-claude-handoff.md`
