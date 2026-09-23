---
task_id: T-005
branch: codex/django
base_branch: dev
reviewer: Codex
reviewed_commit: bac10a4
verdict: approved_with_unverified_compose
---

# T-005 Codex 검토: Django + Django Template 전환

## 결론

**승인 — 병합 가능.** 이전 P1은 `306125e`에서 공통 JSON 파서가 dict 이외의 JSON을 422 JSON으로 거절하도록 수정되고, 두 endpoint의 배열 JSON 회귀 테스트가 추가되며 해결됐다. Codex가 PostgreSQL 테스트 DB에서 21개 테스트와 실제 응답 형식을 독립 재실행해 확인했다.

Docker Compose `web` 컨테이너의 전체 HTTP 기동은 Codex 환경에 Docker CLI가 없어 직접 재현하지 못했다(P2). 다만 이 작업의 핵심 Django migration·실제 PostgreSQL 테스트 DB·기존 개발 DB 읽기 경로·JSON API 계약은 확인됐으며, P0·P1은 없다.

## 대조 대상

- 작업 문서: `docs/tasks/T-005-django-template-migration.md`
- 인수인계: `docs/handoffs/T-005-claude-handoff.md` (`f75294f` 구현, `80c7747` 최초 인수인계, `bac10a4` P1 대응 갱신)
- 비교 범위: `dev...codex/django`, 52개 파일, 2,117줄 추가·7,845줄 삭제
- 커밋: `3629297`(Codex 기획) → `f75294f`(Claude 구현) → `80c7747`(최초 인수인계) → `281817f`(Codex P1 검토) → `306125e`(P1 수정) → `bac10a4`(인수인계 갱신)

## 완료 기준 판정

| 기준 | Codex 확인 근거 | 판정 |
|---|---|---|
| 1 | Django project·template·Compose 전환을 확인했다. 실제 PostgreSQL에서 `/`는 200이며, 대시보드 읽기 전용 테스트도 통과했다. | 충족 |
| 2 | URL 경로와 정상 GET·입력 오류를 유지한다. `[]`은 공통 파서에서 422 JSON `detail`로 거절되며, 수집·주문 endpoint의 독립 응답과 회귀 테스트로 확인했다. | 충족 |
| 3 | 5개 model의 `db_table`·호환 타입, `SeparateDatabaseAndState` migration, 서비스 코드의 요청 중 DDL 부재를 확인했다. | 충족 |
| 4 | Django 실제 PostgreSQL 테스트 DB에서 `trading.0001_initial`이 적용되어 21개 테스트가 통과했다. 기존 개발 DB에도 migration 적용 상태와 데이터 보존을 읽기 전용으로 확인했다. | 충족 |
| 5 | `trade_date > decision_trade_date`, `adjusted=False`, 저장된 `open_price`만 사용한다. `Decimal(str(rate))`와 정수 올림을 유지하며 관련 테스트가 통과했다. | 충족 |
| 6 | `transaction.atomic()` 안에서 계좌·주문 `select_for_update()`와 원장 추가·상태 갱신을 처리한다. | 충족(코드·테스트 DB) |
| 7 | root view는 조회만 수행하며 테스트와 기존 개발 DB의 GET `/` 200으로 확인했다. | 충족 |
| 8 | Next.js·FastAPI·CORS·Node 의존성이 제거되고, 단일 Django `web` 서비스와 docs가 갱신됐다. | 충족 |
| 9 | `.env.example`에는 자리표시자만 있고, 설정은 Django settings 계층에서 읽는다. diff의 비밀값·연결 문자열·실계좌·외부 주문 호출 추가는 발견하지 못했다. | 충족 |
| 10 | Claude 인수인계는 mock·실DB·외부 네트워크를 구분했다. Codex도 아래 독립 결과를 구분해 재확인했다. | 충족 |

## 독립 실행 결과

### Django 설정·migration 상태

로컬 `.env` 값은 출력하지 않고 검증 프로세스에만 적용했다.

```powershell
python -X utf8 -c "... django.setup(); execute_from_command_line(['manage.py', 'check'])"
python -X utf8 -c "... django.setup(); execute_from_command_line(['manage.py', 'makemigrations', '--check', '--dry-run'])"
```

- `manage.py check`: **System check identified no issues (0 silenced)**
- `makemigrations --check --dry-run`: **No changes detected**
- 단, Compose 내부 호스트명 `db`는 Codex 호스트에서 이름 해석되지 않아, 실제 DB 검증 프로세스에 한해 로컬 공개 포트의 `localhost`를 사용했다. 설정 파일은 바꾸지 않았다.

### 자동 테스트 — 실제 PostgreSQL 테스트 DB, 외부 pykrx mock

```powershell
python -X utf8 -c "... execute_from_command_line(['manage.py', 'test', 'trading', '--verbosity', '2'])"
```

결과: `trading.0001_initial`을 새 `test_jumong` DB에 적용한 뒤 **21 passed / OK**, 이후 테스트 DB를 정리했다.

- 시장 데이터 수집의 pykrx 호출은 mock이다. 실제 외부 네트워크·실계좌·실주문 호출은 없었다.
- health, 수집 설정 게이트·품질 검증·GET 무외부호출, 계좌·원장, 다음 거래일 시가·비용 올림·현금 부족·반복 체결, 읽기 전용 대시보드, JSON 배열 422 계약 2건을 포함한다.

### 기존 개발 PostgreSQL — 읽기 전용 교차 확인

`trading.0001_initial`이 적용된 상태에서 기존 데이터를 변경하지 않고 조회했다.

| 항목 | Codex 확인값 |
|---|---:|
| `market_data_collection_runs` | 3행 |
| `daily_prices` | 2행 |
| `virtual_accounts` | 1행 |
| `cash_ledger_entries` | 2행 |
| `virtual_buy_orders` | 3행 |
| 현금 원장 합계 | 9,996,996 KRW |
| 주문 상태 | `filled`, `pending`, `rejected_insufficient_cash` 각 1건 |

실제 허용 호스트(`localhost`) 기준으로 `/health`, `/`, `/virtual-account`, `/virtual-account/cash-ledger`, `/virtual-orders`, `/market-data/daily-prices`의 GET은 모두 200이었다. 이 확인은 읽기 요청만 사용했으며 계좌 초기화·수집·체결을 실행하지 않았다.

### API 오류 계약 회귀 확인

| 요청 | 결과 | 판정 |
|---|---|---|
| 수집 endpoint에 malformed JSON | 422 JSON | 유지 |
| 주문 endpoint에 잘못된 ticker | 422 JSON | 유지 |
| 없는 주문 체결 | 404 JSON | 유지 |
| 수집 endpoint에 JSON 배열 `[]` | 422 JSON + `detail` | 유지 |
| 주문 endpoint에 JSON 배열 `[]` | 422 JSON + `detail` | 유지 |

## 리뷰 결과

- **P0:** 없음
- **P1:** 없음. `306125e`가 공통 파서의 dict 검증과 회귀 테스트로 이전 P1을 해결했고, Codex가 응답 형식까지 독립 확인했다.
- **P2:** Docker Compose `web` 컨테이너 전체 HTTP 기동은 Codex 환경에 Docker CLI가 없어 독립 실행하지 못했다. 다만 실제 PostgreSQL 테스트 DB·기존 개발 DB와 Django test client로 migration 및 읽기 경로는 확인했다.

## 범위·보안 점검

- `git diff --check dev...codex/django` 통과.
- 가상 현금·수동 가상 매수·저장 일봉만 유지하며, 실제 계좌·실제 주문·자동매매 호출은 추가되지 않았다.
- `.env`는 Git 추적 대상이 아니며, diff에 API 키·토큰·비밀번호·전체 연결 문자열이 없다.
- Compose는 `db`와 단일 Django `web`만 남기고 CORS와 Node frontend를 제거했다.

## 다음 행동

1. 사용자가 승인하면 `codex/django`를 원격에 push하고 T-005 PR을 준비한다.
2. Docker CLI를 쓸 수 있는 환경에서 PR 병합 전 또는 후 `docker compose up` 기반의 `web` 컨테이너 HTTP 확인을 한 번 남긴다.
