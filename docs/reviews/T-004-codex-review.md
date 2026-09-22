---
task_id: T-004
branch: codex/orders
base_branch: dev
reviewer: Codex
reviewed_commit: 65bc806
verdict: approved_with_unverified_real_db
---

# T-004 Codex 검토: 가상 매수 주문·다음 거래일 시가 체결

## 결론

**승인 — 병합 가능.** P0·P1은 발견하지 못했다. T-004 범위의 자동 테스트는 Codex 환경에서 독립적으로 47건 모두 통과했다.

다만 실제 PostgreSQL 재검증은 현재 Codex 호스트에서 Docker DB에 연결할 수 없어 **미확인**이다. Claude 인수인계의 실제 DB 결과는 별도 주장으로 남기며, Codex 독립 통과로 표현하지 않는다. T-004의 완료 기준 9는 실제 DB 확인을 "가능하면" 수행하도록 했으므로 이 상태는 병합 차단 사유가 아니다.

## 대조 대상

- 작업 문서: `docs/tasks/T-004-virtual-order-execution.md`
- 인수인계: `docs/handoffs/T-004-claude-handoff.md` (`d4c5074` 구현, `65bc806` 인수인계)
- 비교 범위: `dev...codex/orders`, 9개 파일, 966 추가 줄
- 커밋: `5a57ca9`(Codex 기획) → `d4c5074`(Claude 구현) → `65bc806`(Claude 인수인계)

## 완료 기준 판정

| 기준 | Codex 확인 근거 | 판정 |
|---|---|---|
| 1 | `create_order`가 계좌·결정일 비조정 가격을 확인하고 `pending`만 추가한다. 입력·계좌 없음·가격 없음·현금 미차감 mock 테스트 통과 | 충족 |
| 2 | `earliest_unadjusted_open_after`는 `trade_date > decision_trade_date`, `adjusted = false`, `ORDER BY trade_date ASC`와 `open_price`만 사용한다. 외부 수집 호출 경로 없음 | 충족 |
| 3 | 주문 테이블과 `_apply_execution`이 기준가·체결가·총액·수수료·출처·조정 여부·수집 실행 ID를 기록한다 | 충족 |
| 4 | `compute_execution`이 정수 올림 나눗셈과 `Decimal(..., ROUND_CEILING)`을 사용한다. 슬리피지·수수료 테스트 통과 | 충족 |
| 5 | 계좌 행 잠금 후 현금 합계를 확인하고, 성공 시 주문 갱신과 음수 `buy_execution` 원장 추가를 같은 연결의 트랜잭션에서 처리한다. 주문별 원장 유일 인덱스가 있다 | 충족(코드·mock), 실제 DB 미확인 |
| 6 | 가격 부재는 409으로 pending을 유지하고, 현금 부족은 원장 없이 `rejected_insufficient_cash`로 종료한다. 해당 테스트 통과 | 충족(코드·mock), 실제 DB 미확인 |
| 7 | 종료 주문은 기존 결과만 반환하며, `execution_order_id` 유일 인덱스로 원장 중복을 막는다. 반복 실행 테스트 통과 | 충족(코드·mock), 실제 DB 미확인 |
| 8 | 매수 생성·단건 수동 체결·조회만 추가됐다. 매도·취소·포지션·손익·실제 주문·자동 실행·frontend·Notion 변경 없음 | 충족 |
| 9 | backend 전체 자동 테스트 47건을 독립 재실행했다. 실제 PostgreSQL은 현재 연결 불가로 미확인 | 부분 충족 |
| 10 | README와 인수인계에 API 순서·다음 거래일 시가 규칙·비용 가정·범위·검증 한계가 기록됐다 | 충족 |

## 독립 실행 결과

### 자동 테스트

backend 전용 가상환경의 의존성을 사용해 아래 명령을 실행했다.

```powershell
& "C:\Users\박창제\AppData\Local\Programs\Python\Python314\python.exe" -X utf8 -c "... pytest.main(['tests'])"
```

결과: **47 passed, 2 warnings in 5.38s**

- health: 2
- T-002 시장 데이터: 12
- T-003 가상계좌: 18
- T-004 가상 주문: 15

경고 2건은 FastAPI/Starlette 테스트 클라이언트의 deprecation 경고이며, 이번 기능의 실패는 아니다.

### 실제 PostgreSQL

- 읽기 전용 연결을 시도했다.
- 기본 컨테이너 호스트 `db`는 Codex 호스트에서 이름 해석에 실패했다.
- 검증 프로세스에 한해 `localhost`를 적용해 재시도했으나 5432 포트 연결 시간이 초과됐다.
- DB 조회·데이터 변경·정리 작업은 수행하지 못했다.

따라서 인수인계의 실제 DB 체결·원장·유일 제약 결과는 Codex가 독립 확인하지 못했다. Docker DB가 실행되는 환경에서 병합 후 또는 다음 검증 시 재확인하면 된다.

### 실제 외부 네트워크

미실행이며 T-004의 검증 대상도 아니다. 변경 코드는 저장된 `daily_prices`를 읽는 쿼리만 추가했고, pykrx·HTTP·시장 데이터 수집을 호출하지 않는다.

## 리뷰 결과

- **P0:** 없음
- **P1:** 없음
- **P2:** 실제 PostgreSQL 독립 재검증 미확인. 현재 Docker DB 접근 불가로 인한 환경 제한이며, T-004의 "가능하면" 기준에 대한 후속 확인 항목이다.

## 범위·보안 점검

- `git diff --check dev...codex/orders` 통과.
- 새 환경변수·의존성·마이그레이션 프레임워크·frontend 변경 없음.
- 주문 가격 조회는 T-002의 저장 일봉만 읽고 같은 날 가격을 배제한다.
- 연결 문자열·API 키·토큰·계좌 정보는 diff와 문서에 추가되지 않았다.

## 다음 행동

1. 사용자가 승인하면 `codex/orders`를 원격에 push하고 T-004 PR을 생성한다.
2. PR 병합 뒤에는 T-005를 바로 확장하지 않고, 사용자가 결정한 Django + Django Template 전환 기획을 별도 작업으로 준비한다.
