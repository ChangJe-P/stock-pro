---
task_id: T-005
branch: codex/django
base_branch: dev
reviewer: Codex
reviewed_commit: 80c7747
verdict: changes_requested
---

# T-005 Codex 검토: Django + Django Template 전환

## 결론

**수정 요청 — 현재 병합 보류.** Django 전환, DB migration, 기존 개발 DB 보존, 가상 주문 규칙은 확인했다. 그러나 JSON 객체가 아닌 정상 문법의 JSON 배열(`[]`)을 `POST /market-data/daily-prices/collect`로 보내면 기존 FastAPI의 422 JSON 대신 **500 HTML**이 반환된다. T-005의 "기존 JSON API의 핵심 오류 상태 코드·응답 의미 유지"를 깨므로 P1이다.

`trading.views._parse_json_body`가 JSON 파싱 성공 여부만 확인하고 dict 여부를 확인하지 않아, 호출부의 `body.get(...)`에서 `AttributeError`가 난다. 모든 JSON body endpoint가 공유하므로 그 함수에서 dict가 아니면 안전한 `ApiError(422, ...)`를 발생시키고, 배열 JSON 회귀 테스트를 추가해야 한다. 이 수정 뒤 재검증하면 된다.

## 대조 대상

- 작업 문서: `docs/tasks/T-005-django-template-migration.md`
- 인수인계: `docs/handoffs/T-005-claude-handoff.md` (`f75294f` 구현, `80c7747` 인수인계)
- 비교 범위: `dev...codex/django`, 51개 파일, 1,980줄 추가·7,845줄 삭제
- 커밋: `3629297`(Codex 기획) → `f75294f`(Claude 구현) → `80c7747`(Claude 인수인계)

## 완료 기준 판정

| 기준 | Codex 확인 근거 | 판정 |
|---|---|---|
| 1 | Django project·template·Compose 전환을 확인했다. 실제 PostgreSQL에서 `/`는 200이며, 대시보드 읽기 전용 테스트도 통과했다. | 충족 |
| 2 | URL 경로와 정상 GET·대부분의 입력 오류는 유지된다. 다만 JSON 배열은 500 HTML이 되어 기존 422 JSON 계약을 위반한다. | **미충족(P1)** |
| 3 | 5개 model의 `db_table`·호환 타입, `SeparateDatabaseAndState` migration, 서비스 코드의 요청 중 DDL 부재를 확인했다. | 충족 |
| 4 | Django 실제 PostgreSQL 테스트 DB에서 `trading.0001_initial`이 적용되어 19개 테스트가 통과했다. 기존 개발 DB에도 migration 적용 상태와 데이터 보존을 읽기 전용으로 확인했다. | 충족 |
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

결과: `trading.0001_initial`을 새 `test_jumong` DB에 적용한 뒤 **19 passed / OK**, 이후 테스트 DB를 정리했다.

- 시장 데이터 수집의 pykrx 호출은 mock이다. 실제 외부 네트워크·실계좌·실주문 호출은 없었다.
- health, 수집 설정 게이트·품질 검증·GET 무외부호출, 계좌·원장, 다음 거래일 시가·비용 올림·현금 부족·반복 체결, 읽기 전용 대시보드를 포함한다.

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
| 수집 endpoint에 JSON 배열 `[]` | **500 HTML** | **P1: 기존 422 JSON 계약 위반** |

## 리뷰 결과

- **P0:** 없음
- **P1:** `backend/trading/views.py`의 `_parse_json_body`가 dict가 아닌 JSON을 422로 거절하지 않는다. 공통 파서에서 객체 여부를 검증하고, JSON 배열 입력 회귀 테스트를 추가해야 한다.
- **P2:** Docker Compose `web` 컨테이너 전체 HTTP 기동은 Codex 환경에 Docker CLI가 없어 독립 실행하지 못했다. 다만 실제 PostgreSQL 테스트 DB·기존 개발 DB와 Django test client로 migration 및 읽기 경로는 확인했다.

## 범위·보안 점검

- `git diff --check dev...codex/django` 통과.
- 가상 현금·수동 가상 매수·저장 일봉만 유지하며, 실제 계좌·실제 주문·자동매매 호출은 추가되지 않았다.
- `.env`는 Git 추적 대상이 아니며, diff에 API 키·토큰·비밀번호·전체 연결 문자열이 없다.
- Compose는 `db`와 단일 Django `web`만 남기고 CORS와 Node frontend를 제거했다.

## 다음 행동

1. **클로드한테** P1 수정 요청을 전달한다: 공통 JSON 파서에서 dict 이외의 JSON을 422 JSON으로 처리하고, 배열 JSON 회귀 테스트를 추가한다.
2. Claude가 새 인수인계와 커밋을 남기면 Codex가 19개 테스트와 해당 오류 계약을 다시 검증한다.
3. 승인 뒤에만 `codex/django`를 push하고 PR·병합을 준비한다.
