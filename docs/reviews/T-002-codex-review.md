---
task_id: T-002
branch: codex/data
reviewer: Codex
review_status: changes_requested
---

# T-002 Codex 검증 결과

## 병합 판단

**수정 후 가능**. 자동 테스트와 작업 범위는 대체로 맞지만, 수집 실행의 감사 기록이 완료 기준을 충족하지 못하는 P1 두 건이 있다.

## 완료 기준별 판정

| 기준 | 판정 | 근거 |
|---|---|---|
| 1. pykrx 설정 게이트 | 충족 | `market_data_configured`와 `_require_configured`, mock 테스트가 비설정 시 fetch 미호출을 확인한다. |
| 2. pykrx 일봉 수집·저장 | 부분 충족 | mock·실DB 적재 증거는 있으나, 실제 pykrx 공개 응답은 현재 빈 DataFrame이라 실데이터 적재는 미확인이다. |
| 3. 실행별 출처·기준시각·해시·행수·상태 기록 | 부분 충족 | 정상·부분 수집은 기록하지만, 외부 조회 실패는 실행기록 없이 502로 끝난다(P1). |
| 4. 재수집 upsert | 충족 | 유일 제약과 `ON CONFLICT DO UPDATE`를 확인했고, 인수인계의 실DB 재수집 증거와 일치한다. |
| 5. 입력·기간·품질 검증과 제외 사유 | 부분 충족 | API 응답에는 제외 행·사유가 있으나 실행기록에는 `excluded_rows=N`만 저장돼 사유가 남지 않는다(P1). |
| 6. GET 오름차순·수집 미시작 | 충족 | SQL의 `ORDER BY trade_date ASC`와 mock 테스트의 fetch 미호출을 확인했다. |
| 7. 제외 범위 준수 | 충족 | `dev...codex/data` diff에 frontend·주문·계좌·KIS·스케줄러 변경이 없다. |
| 8. `/health` 유지 | 충족 | 전체 pytest에 기존 health 테스트 2건이 포함돼 통과했다. |
| 9. mock 테스트와 실제 네트워크 구분 | 충족 | 자동 테스트는 mock이고, 실제 pykrx 조회 실패를 별도 미검증으로 기록했다. |
| 10. 문서·인수인계 | 충족 | README, 환경 문서, 인수인계가 변경됐다. |

## 발견 사항

### P1 — 제외 사유가 수집 실행 기록에 저장되지 않음

`backend/app/market_data.py:171-178`은 제외 행이 있을 때 `failure_reason`을 `excluded_rows=N`으로만 만들고, `:225-237`은 그 값만 `market_data_collection_runs`에 저장한다. 응답의 `excluded`에는 이유가 있지만 DB 실행기록에는 이유별 정보가 없다. 작업 명세의 “제외 건수와 이유를 실행 기록에 남김”을 충족하도록 안전한 이유별 건수를 실행기록에 저장하고 테스트를 추가해야 한다.

### P1 — 외부 조회 실패 실행이 `market_data_collection_runs`에 남지 않음

`backend/app/market_data.py:287-299`에서 `fetch_ohlcv` 예외는 즉시 502를 반환한다. 따라서 `store_collection`에 도달하지 않아 실행 식별자·기준시각·실패 상태·안전한 사유가 저장되지 않는다. 외부 조회 실패도 DB가 정상일 때는 실패 실행으로 남기고, 이에 대한 mock 테스트를 추가해야 한다.

### P2 — GET 정렬 테스트가 정렬 결과를 단언하지 않음

`backend/tests/test_market_data.py:136-154`는 조회 함수가 반환한 두 행의 개수만 확인한다. 실제 SQL에는 정렬이 있으나, 테스트가 거래일 순서를 단언하지 않아 완료 기준 6의 회귀를 잡지 못한다. 반환 날짜가 오름차순인지 단언을 추가하면 된다.

## 독립 실행 결과

| 항목 | 결과 |
|---|---|
| `backend/.venv/Scripts/python.exe -m pytest -q` | 11 passed, deprecation warning 2건 |
| `git diff --check dev...HEAD` | 오류 없음 |
| 실제 pykrx `005930` 2024-01-02~05 조회(저장 없음) | KRX 응답 파싱 오류 뒤 `rows=0, columns=[]`; 인수인계의 실네트워크 미검증 기록과 일치 |
| 실제 Docker PostgreSQL 재적재 | 미확인. 현재 Codex 실행 환경에서 Docker CLI를 찾지 못했다. |

## 수정 후 재검증 범위

- 제외 사유가 실행기록에 남는지와 외부 조회 실패 실행이 `failure` 상태로 남는지 mock 테스트로 확인한다.
- 전체 pytest를 재실행한다.
- Docker 접근 가능한 환경에서 재수집 upsert를 다시 확인한다.
- 실제 pykrx 응답이 가능한 환경에서는 한 종목·기간을 저장 없이 먼저 조회하고, 정상 응답일 때만 수집 API 적재를 확인한다.
