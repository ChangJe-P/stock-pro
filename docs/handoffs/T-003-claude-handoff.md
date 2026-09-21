---
task_id: T-003
branch: codex/trading
commit: 2171898
status: complete
---

# Claude Code 구현 인수인계

## 작업 요약

- 구현한 내용: 단일 로컬 사용자용 **가상 학습 계좌**와 추가 전용 **현금 원장** 기반을 backend에 추가했다. 최초 가상 현금·거래 비용 가정(정책 v1)은 설정 계층에서만 읽어 계좌 최초 생성 시 스냅샷으로 저장한다. `POST /virtual-account/initialize`(원자적 1회 생성, 반복 시 비재설정), `GET /virtual-account`(정책 스냅샷 + 원장 합계 `available_cash_krw`), `GET /virtual-account/cash-ledger`(생성 시각 오름차순) 세 API를 추가했다. 모든 금액은 KRW 정수(bigint)다.
- 구현하지 않은 내용(제외 범위 준수): 실제 증권 계좌·계좌번호·로그인·잔고·실주문·자동매매, 매수/매도 주문·다음 거래일 체결·보유 수량·손익/수익률, 실제 수수료·세금 동기화, 실시간 시세·가격 수집 변경, frontend·Notion·다중 사용자, 정책 수정·계좌 재설정·원장 수정/삭제 API, 제공처 추상화·주문 엔진.

## 변경·생성 파일

| 파일 | 변경 이유 |
|---|---|
| backend/app/config.py | 가상 거래 정책 6개 값을 `str | None`로 선언(기본값 하드코딩 안 함) + `VirtualPolicy`·`VirtualPolicyError`·`load_virtual_policy`(누락·형식·범위 검증)·`get_virtual_policy` 추가 |
| backend/app/virtual_account.py (신규) | 재실행 안전 스키마(단일계좌 UNIQUE, 추가 전용 원장), 초기화·조회·원장 조회 서비스, 저장소 함수, APIRouter 3개 |
| backend/app/main.py | virtual_account 라우터 include. `/health`·T-002 유지 |
| backend/tests/test_virtual_account.py (신규) | 설정 검증(순수) + 엔드포인트(레포·커넥션 mock) 테스트. 실 DB/시장 데이터/증권사 요청 없음 |
| .env.example | `VIRTUAL_*` 6개 변수와 학습용 가정·비소급 주석 추가 |
| docs/ENVIRONMENT.md | 가상 거래 정책 변수 절 추가(목적·범위·안전 오류·비소급) |
| README.md | 가상계좌·원장 API 사용법, 가상 현금 경계, v1 가정·제한 추가 |

로컬 `.env`에도 `VIRTUAL_*` 값을 넣었으나 커밋하지 않았다(Git 제외). 새 의존성 없음 → `requirements.lock.txt` 변경 없음.

## 완료 기준 대조

| 완료 기준 | 구현 위치 또는 증거 | 판정 |
|---|---|---|
| 1. 정책 값 설정 계층에서만 읽고 누락·형식·범위 오류 안전 처리 | `config.load_virtual_policy`; `test_valid_policy_*`, `test_invalid_policy_raises_without_leaking_value`(10개 파라미터), `test_initialize_config_error_does_not_touch_db` | 충족 |
| 2. 최초 초기화가 계좌+opening_balance를 원자적으로 1회 생성 | `_create_account_with_opening`(같은 트랜잭션); `test_first_initialize_creates_account_and_opening` + 실DB(accounts=1, ledger=1, opening_balance 10,000,000) | 충족(실DB 확인) |
| 3. 반복 초기화가 계좌·스냅샷·현금 변경/행 추가 안 함 | initialize의 select-first 분기; `test_repeat_initialize_does_not_reset_or_add` + 실DB(init2 후에도 accounts=1, ledger=1, available 동일) | 충족(실DB 확인) |
| 4. 계좌 조회가 원장 합계 available_cash_krw + 정책 스냅샷 반환 | `get_account`·`_sum_cash`·`_account_response`; `test_get_account_returns_snapshot_and_cash` + 실DB(available=10,000,000) | 충족(실DB 확인) |
| 5. 원장 조회 생성 시각 오름차순, 수정·삭제 경로 없음 | `_list_ledger`(ORDER BY created_at ASC, id ASC), update/delete API 없음; `test_cash_ledger_returns_ascending` | 충족 |
| 6. 실계좌·주문·체결·보유·손익·가격수집·frontend·Notion 미추가 | 신규 코드는 계좌 초기화/조회에 한정, frontend·market_data 무변경 | 충족 |
| 7. health·T-002 포함 backend 테스트 통과 | `pytest` 32 passed(health 2 + market_data 12 + virtual_account 18) | 충족 |
| 8. README·환경문서·핸드오프 기록 | README/ENVIRONMENT/본 문서 | 충족 |

## 실행과 검증

### 자동 테스트 (mock, 실 DB·시장 데이터·증권사 요청 없음)

| 명령 | 결과 |
|---|---|
| `pytest` (backend/.venv) | **32 passed**, warning 2건. 가상계좌 엔드포인트는 저장소 함수(`_select_account` 등)와 `_connect`를 mock, 설정 검증은 순수 함수 테스트 |

### 실제 PostgreSQL 확인 (Docker Postgres localhost, 외부 요청 없음)

깨끗한 스키마에서 서비스 함수를 실제 DB로 실행했다(시장 데이터·증권사 미접촉).

| 항목 | 결과 |
|---|---|
| 최초 초기화 | account_id=1, policy=v1, available=10,000,000, 스냅샷(cash 10,000,000 / buy 0.00015 / sell 0.00015 / tax 0 / slip 0) |
| 반복 초기화 | 동일 account_id=1, available=10,000,000 (재설정·추가 없음) |
| 계좌 조회 | available_cash_krw=10,000,000 (원장 합계) |
| 원장 조회 | `[('opening_balance', 10000000)]` 한 건, 오름차순 |
| 무결성 | virtual_accounts=1, cash_ledger_entries=1, amount_krw 타입 `bigint` |
| 단일계좌 DB 보장 | 두 번째 계좌 강제 INSERT → `UniqueViolation`으로 차단 |

## 가정과 제한

- 정책 v1 값(현금 10,000,000 / 수수료 0.015% / 세금 0% / 슬리피지 0)은 학습용 시뮬레이션 가정이며 실제 증권사·법정 값이 아니다. T-004 전에 실제 값처럼 표현하지 않는다.
- 정책 값은 `str`로 받아 `load_virtual_policy`에서 검증한다. 이렇게 하면 형식 오류가 import 시점에 앱을 죽이지 않고, 오류 메시지에 값 자체·비밀값을 넣지 않는다(변수 이름과 규칙만 표기).
- 수수료·세금·슬리피지는 스냅샷 저장만 하며 이번 작업에서 체결·손익에 사용하지 않는다(T-004 이후).
- 계좌 수수료율은 `DOUBLE PRECISION`으로 저장한다(비율은 금액이 아님). 현금·원장 금액은 `bigint` 정수다.
- 단일 계좌는 `virtual_accounts.singleton`(항상 TRUE, UNIQUE)로 DB 수준 보장한다. 동시 초기화 경합 시 두 번째 생성은 UNIQUE로 막고 기존 계좌를 반환한다.
- 스키마는 마이그레이션 프레임워크 없이 `CREATE TABLE IF NOT EXISTS`로 재실행 안전하게 초기화한다(T-002와 동일).

## 미해결 항목과 다음 제안

- 이번 실DB 확인은 서비스 함수 직접 호출로 수행했다. Docker Compose 전체 스택(backend 컨테이너) 기동 하의 HTTP 엔드투엔드 확인은 후속으로 남긴다.
- 정책 변경(v2 등) 시 기존 계좌 스냅샷 비소급 규칙과 신규 정책 적용 경로는 별도 승인 작업으로 설계한다.
- main/dev로의 병합·push는 규칙에 따라 하지 않았다. Codex 검증 후 진행.
