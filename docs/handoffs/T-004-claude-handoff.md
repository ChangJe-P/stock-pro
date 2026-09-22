---
task_id: T-004
branch: codex/orders
commit: d4c5074
status: complete
---

# Claude Code 구현 인수인계

## 작업 요약

- 구현한 내용: 단일 로컬 가상계좌의 학습용 **매수 주문**을 만들고, 결정 거래일보다 **엄격히 뒤인** 첫 저장 비조정 일봉 시가로 수동 체결하는 backend 기능을 추가했다. 체결 성공 시 주문 상태 `filled`와 음수 `buy_execution` 현금 원장 한 행을 한 트랜잭션에서 기록하고, 슬리피지·수수료는 T-003 계좌 스냅샷 값으로 정수·명시적 올림 규칙을 적용한다. `POST /virtual-orders`(생성), `POST /virtual-orders/{id}/execute`(수동 체결), `GET /virtual-orders`(조회)를 추가했다.
- 구현하지 않은 내용(제외 범위 준수): 매도·주문 취소/수정·일괄 실행·현금 예약, 보유 수량·평가액·실현/평가 손익·수익률, 실제 계좌·실주문·자동매매·투자 조언, 실시간/장중 가격·가격 수집 변경·pykrx 외 제공처·스케줄러·큐, frontend·로그인/다중 사용자·Notion·정책 변경 API.

## 변경·생성 파일

| 파일 | 변경 이유 |
|---|---|
| backend/app/virtual_orders.py (신규) | 주문 스키마(상태 CHECK), 체결 원장 유일 인덱스, 금액 계산(정수/Decimal), 계좌 잠금 체결, 생성·체결·조회 서비스와 APIRouter 3개 |
| backend/app/market_data.py | 저장 가격 조회 두 함수 추가: `stored_unadjusted_price_exists`(결정일 비조정 일봉 존재), `earliest_unadjusted_open_after`(결정일보다 뒤 첫 비조정 시가). 커서 기반, pykrx·HTTP 미호출 |
| backend/app/main.py | virtual_orders 라우터 include. `/health`·T-002·T-003 유지 |
| backend/tests/test_virtual_orders.py (신규) | 계산·입력검증·계좌없음·가격없음·성공·부족·반복·pending 유지·정렬 mock 테스트. 실 DB/pykrx/네트워크 없음 |
| README.md | 주문 생성·수동 체결 순서, 다음 거래일 시가 원칙, 비용 가정, 매수 전용·대기 현금 미예약·실제 투자 아님 명시 |

새 환경변수·의존성·마이그레이션 프레임워크·frontend 변경 없음. `cash_ledger_entries.execution_order_id` 컬럼과 유일 인덱스는 `ADD COLUMN IF NOT EXISTS`·`CREATE UNIQUE INDEX IF NOT EXISTS`로 재실행 안전하게 추가한다.

## 완료 기준 대조

| 완료 기준 | 구현 위치 또는 증거 | 판정 |
|---|---|---|
| 1. 계좌 있는 단일 사용자만 비조정 저장 일봉 근거로 pending 생성, 생성 시 현금 불변 | `create_order`(계좌 없으면 404, 결정일 가격 없으면 409, 현금 미변경); `test_create_order_*` + 실DB(create 후 cash 10,000,000 유지) | 충족(실DB 확인) |
| 2. 결정일보다 엄격히 뒤 첫 시가만 사용, 같은 날·종가·외부 수집 미사용 | `earliest_unadjusted_open_after`(`trade_date > decision`, `open_price`); `test_execute_fills_with_next_day_open` + 실DB(결정 01-02, 같은날 open 900 무시, 체결 01-03 open 1001) | 충족(실DB 확인) |
| 3. 체결 주문에 가격 출처·비조정·수집 실행 식별자 + 기준가·체결가·총액·수수료 보존 | `_apply_execution` 컬럼; 실DB(base_open 1001, exec 1001, gross 3003, fee 1, src pykrx/false/run-1) | 충족(실DB 확인) |
| 4. 슬리피지·매수 수수료를 정수·명시적 올림으로 적용 | `compute_execution`(정수 ceil + Decimal 수수료); `test_compute_*` | 충족 |
| 5. 충분 현금 체결은 상태+음수 buy_execution 원장을 한 트랜잭션에 정확히 1회 | `_mark_filled`(INSERT 원장 + UPDATE order, 같은 txn); `test_execute_fills_*` + 실DB(원장 -3004 1행, cash 9,996,996) | 충족(실DB 확인) |
| 6. 현금 부족은 원장 없이 종료, 가격 부재는 pending 유지, 어느 경우도 음수 현금 아님 | `_mark_rejected`(원장 없음), no-price 409 미변경; 실DB(rejected 후 cash 불변, no-next-day 후 status pending, cash sum≥0) | 충족(실DB 확인) |
| 7. 반복 체결은 종료 주문 결과만 반환, 원장 중복 없음 | execute_order의 status 분기 + 원장 유일 인덱스; `test_execute_terminated_*` + 실DB(재체결 후 cash 불변, 중복 INSERT는 UniqueViolation) | 충족(실DB 확인) |
| 8. 매도·취소·포지션·손익·실주문·자동실행·frontend·Notion 미추가 | 신규 코드는 매수 주문 생성/체결/조회에 한정 | 충족 |
| 9. 기존 포함 backend 자동 테스트 + 실DB 확인 구분 기록 | `pytest` 47 passed(mock) + 아래 실DB 절 | 충족 |
| 10. README·핸드오프에 사용법·증거·가정·제한 | README, 본 문서 | 충족 |

## 실행과 검증

### 자동 테스트 (mock, 실 DB·pykrx·네트워크 요청 없음)

| 명령 | 결과 |
|---|---|
| `pytest` (backend/.venv) | **47 passed**, warning 2건. 주문 엔드포인트는 저장소·가격 조회 함수와 `_connect`를 mock, 금액 계산은 순수 함수 테스트 |

내역: health 2 + market_data 12 + virtual_account 18 + virtual_orders 15. 기존 T-002/T-003/health 테스트 모두 통과.

### 실제 PostgreSQL 확인 (Docker Postgres localhost, 외부 요청 없음)

일봉을 직접 시드(결정일 2024-01-02 open 900, 다음날 2024-01-03 open 1001, 모두 비조정)한 뒤 서비스 함수를 실제 DB로 실행했다. pykrx·시장 데이터 수집·증권사는 호출하지 않았다.

| 항목 | 결과 |
|---|---|
| 주문 생성 | status=pending, 생성 후 현금 10,000,000 유지(불변) |
| 체결(성공) | exec_date=2024-01-03(결정일보다 뒤), base_open=1001, exec_price=1001, gross=3003, fee=1, 출처 pykrx/adjusted=false/run-1 |
| 같은 날 누수 방지 | 결정일(01-02) open 900이 아니라 다음날(01-03) open 1001로 체결 |
| 체결 후 현금 | 9,996,996 (=10,000,000-3004), 원장 `buy_execution` -3004 한 행 |
| 반복 체결 | status=filled 결과만 반환, 현금 9,996,996 유지(원장 미추가) |
| 현금 부족(수량 100000) | status=rejected_insufficient_cash, reason=insufficient_cash, 현금 불변, 원장 없음 |
| 다음 거래일 가격 부재(결정일 01-03) | HTTP 409, 주문 status=pending 유지 |
| 무결성 | 원장 [opening_balance +10,000,000, buy_execution -3004], cash sum 9,996,996 ≥ 0 |
| 원장 유일 제약 | filled 주문에 buy_execution 원장 강제 중복 INSERT → UniqueViolation으로 차단 |

### 실제 외부 네트워크 (해당 없음)

이 작업은 저장된 `daily_prices`만 읽으므로 외부 네트워크 요청이 없다. pykrx·HTTP를 호출하지 않으며 자동 테스트도 이를 시작하지 않는다.

## 가정과 제한

- 동시 체결은 직접 재현하지 않았다. 대신 (1) 체결 트랜잭션이 시작에서 `SELECT ... FOR UPDATE`로 가상계좌 행을 잠가 현금 확인·상태 갱신·원장 추가를 직렬화하고, (2) `cash_ledger_entries(execution_order_id)` 유일 인덱스가 주문당 원장 1행을 강제한다. 유일 인덱스 차단은 실DB에서 확인했다. 실제 동시성 재현은 미검증으로 남긴다.
- 매수 수수료율은 계좌 스냅샷의 `DOUBLE PRECISION`이므로 `Decimal(str(rate))`로 정확히 변환해 `Decimal` 산술로 수수료를 올림한다. 가격·수량·총액·수수료·현금은 정수(bigint)다.
- 대기 주문은 현금을 예약하지 않는다. 체결 가능 여부는 체결 시점의 원장 합계 현금으로 판단한다.
- 결정일·다음 거래일 판정은 저장된 `daily_prices`에만 의존한다. 서버는 현재 시각·장 시간·휴장일을 추정하지 않는다.
- rejected 주문에도 계산된 기준가·체결가·총액·수수료·가격 출처를 보존한다(원장은 없음). 부족 사유 확인용이며 완료 기준 3의 filled 보존 요구를 넘어서지 않는다.

## 미해결 항목과 다음 제안

- 실제 동시 체결(두 요청이 같은 현금 경합) 재현 테스트는 별도 도구가 필요해 남겨둔다. 현재는 행 잠금·유일 제약으로 방어하며 유일 제약 차단만 실DB로 확인했다.
- Docker Compose 전체 스택(backend 컨테이너) 기동 하의 HTTP 엔드투엔드 확인은 후속으로 남긴다(이번 실DB 확인은 서비스 함수 직접 호출).
- main/dev로의 병합·push는 규칙에 따라 하지 않았다. Codex 검증 후 진행.

## 최종 커밋
- 구현: `d4c5074`
- 인수인계: 본 파일(별도 커밋)
