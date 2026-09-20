---
task_id: T-002
branch: codex/data
reviewer: Codex
reviewed_commit: 8a9013c
review_status: changes_requested
---

# T-002 Codex 재검증 결과

## 병합 판단

**수정 후 가능**. 이전 P1 2건과 P2 1건은 코드와 mock 테스트로 해소됐지만, 중복 거래일 검증이 특정 순서의 잘못된 데이터에서 누락되는 P1을 새로 확인했다.

## 이전 리뷰 대응 확인

| 이전 지적 | 판정 | 독립 근거 |
|---|---|---|
| 제외 사유가 실행 기록에 없음 | 충족 | `excluded_reasons` JSONB와 `summarize_excluded`를 확인했고, `test_collect_records_excluded_reasons`가 실행 INSERT 파라미터를 단언한다. |
| 외부 조회 실패 실행이 기록되지 않음 | 충족 | `record_failed_fetch`가 `failed`/`external_fetch_failed` 기록을 남기며, 관련 mock 테스트가 통과한다. |
| GET 정렬 테스트 미흡 | 충족 | 조회 응답의 날짜 오름차순을 단언하는 테스트가 추가됐다. |

## 완료 기준별 판정

| 기준 | 판정 | 근거 |
|---|---|---|
| 1. pykrx 설정 게이트 | 충족 | 비설정 시 fetch 미호출 테스트가 통과한다. |
| 2. pykrx 일봉 수집·저장 | 부분 충족 | mock·Claude의 실DB 증거는 있으나, Codex 환경의 실제 pykrx 응답은 빈 DataFrame이라 실데이터 적재는 미확인이다. |
| 3. 실행별 실행기록 | 충족 | 정상·부분·외부 실패 경로의 실행기록 코드와 mock 테스트를 확인했다. |
| 4. 재수집 upsert | 충족 | 유일 제약과 `ON CONFLICT DO UPDATE`를 확인했다. 실DB 증거는 인수인계에만 있다. |
| 5. 입력·기간·품질 검증 | 부분 충족 | 일반 중복은 검사하지만, 첫 중복 행이 잘못된 값이면 다음 유효 행을 중복으로 기록하지 않는다(P1). |
| 6. GET 오름차순·수집 미시작 | 충족 | `ORDER BY trade_date ASC`와 순서 단언 테스트를 확인했다. |
| 7. 제외 범위 준수 | 충족 | `dev...codex/data` diff에 frontend·주문·계좌·KIS·스케줄러 변경이 없다. |
| 8. `/health` 유지 | 충족 | 전체 pytest의 health 테스트가 통과한다. |
| 9. mock 테스트와 실제 네트워크 구분 | 충족 | 자동 테스트 13건은 mock이고, 실제 pykrx 빈 응답을 별도 미검증으로 기록했다. |
| 10. 문서·인수인계 | 충족 | README, 환경 문서, 인수인계가 갱신됐다. |

## 발견 사항

### P1 — 첫 중복 행이 잘못된 값이면 중복 거래일이 기록되지 않음

`backend/app/market_data.py:133-161`은 행의 가격·컬럼 검증을 통과한 경우에만 `seen_dates`에 거래일을 추가한다. 따라서 같은 날짜의 첫 행이 0 가격 등으로 제외되면, 두 번째 유효 행은 `duplicate_date`가 아닌 정상 행으로 저장된다. Codex가 같은 날짜에 `0` 가격 행 뒤 정상 행을 넣어 실행한 결과는 `valid=1`, 제외 사유는 `['non_positive_price']`였고 `duplicate_date`는 남지 않았다.

원본 응답의 중복 거래일을 숨기지 않도록, 행 품질과 무관하게 날짜 중복을 먼저 추적하고 이유별 건수에도 `duplicate_date`가 남게 수정해야 한다. 이 경계 사례를 테스트로 추가해야 한다.

## 독립 실행 결과

| 항목 | 결과 |
|---|---|
| `backend/.venv/Scripts/python.exe -m pytest -q` | 13 passed, deprecation warning 2건 |
| `git diff --check dev...HEAD` | 오류 없음 |
| 중복·잘못된 가격 경계 사례 | `valid=1`, `reasons=['non_positive_price']`; P1 재현 |
| 실제 pykrx `005930` 2024-01-02~05 조회(저장 없음) | 응답 파싱 오류 뒤 `rows=0, columns=[]`; 실데이터 적재 미확인 |
| 실제 Docker PostgreSQL 재검증 | 미확인. 현재 Codex 실행 환경에서 Docker CLI를 찾지 못했다. |

## 수정 후 재검증 범위

- 첫 행이 잘못된 중복 거래일도 `duplicate_date`로 기록되는 테스트를 추가한다.
- 전체 pytest를 다시 실행한다.
- Docker 접근 가능한 환경에서 리뷰 대응 JSONB 컬럼과 실패 실행 기록을 다시 확인한다.
- 실제 pykrx 응답이 가능한 환경에서는 한 종목·기간의 실데이터 수집·저장을 확인한다.
