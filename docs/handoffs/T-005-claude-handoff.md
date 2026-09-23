---
task_id: T-005
branch: codex/django
commit: 306125e
status: complete
---

# Claude Code 구현 인수인계

> 갱신(2026-09-23): Codex 검토 P1 대응. 전환 커밋 `f75294f`, 인수인계 `80c7747`, P1 수정 `306125e`. 아래 "Codex 검토 대응" 절 참조.

## Codex 검토 대응 (P1)

| 지적 | 대응 | 근거 |
|---|---|---|
| P1 — 공통 JSON 파서가 dict가 아닌 유효 JSON(예: `[]`)을 422로 거절하지 않아, 배열 body가 500 HTML이 됨(기존 422 JSON 계약 위반) | `trading.views._parse_json_body`에서 파싱 후 `isinstance(dict)`가 아니면 `ApiError(422, "요청 본문은 JSON 객체여야 합니다.")`를 발생시킴. 모든 JSON body endpoint가 공유하므로 collect·orders 모두 안전한 422 JSON을 반환 | `JsonBodyContractTests.test_collect_rejects_json_array_body`, `test_orders_rejects_json_array_body` — `[]` body에 422와 `detail` 확인 |

## 작업 요약

- 구현한 내용: FastAPI backend와 Next.js frontend를 **Django + Django Template 단일 웹 서비스**로 전환했다. `backend/`를 Django 프로젝트 루트로 유지하고 `jumong/` project와 단일 `trading/` app을 만들었다. 기존 5개 PostgreSQL 테이블을 같은 이름·호환 타입의 Django model로 채택하고, JSON API 경로·상태 코드·응답 의미를 보존했다. root `GET /`는 읽기 전용 대시보드를 렌더링한다. 스키마는 migration만 관리하며 요청 중 DDL을 실행하지 않는다.
- 구현하지 않은 내용(제외 범위 준수): 매도·포지션·손익·수익률, 실제 계좌·주문·자동매매, 실시간·장중 가격·새 제공처·스케줄러, 로그인·다중 사용자·Notion, DRF·SPA·React/Next.js 유지·신규 UI form, DB 초기화·볼륨 삭제.

## 변경·생성 파일

### 생성
| 파일 | 내용 |
|---|---|
| backend/manage.py | Django 관리 진입점 |
| backend/jumong/{settings,urls,wsgi,asgi,__init__}.py | 설정 계층·URL·엔트리. CORS 없음, DJANGO_SECRET_KEY/ALLOWED_HOSTS 추가 |
| backend/trading/models.py | 5개 테이블 매핑(BigInteger 금액, JSONField, FloatField 수수료율) |
| backend/trading/migrations/0001_initial.py | SeparateDatabaseAndState + idempotent SQL(새 DB 생성, 기존 DB 보존) |
| backend/trading/config.py | 시장 데이터 제공처 판정, 가상 정책 검증(값 노출 없는 오류) |
| backend/trading/market_data.py | pykrx 수집·검증·해시·upsert·저장 가격 조회(외부 수집 없음) |
| backend/trading/accounts.py | 단일 계좌 초기화·조회·현금 원장(합계 기반 현금) |
| backend/trading/orders.py | 매수 주문 생성·체결(atomic+select_for_update), 정수/Decimal 비용 |
| backend/trading/views.py | JSON API views(경로·상태·detail 유지, POST는 CSRF 예외) + health + 읽기 전용 대시보드 |
| backend/trading/errors.py | 안전한 detail을 담는 ApiError |
| backend/trading/tests.py | Django test runner 테스트(외부 pykrx mock) |
| backend/templates/trading/dashboard.html | 읽기 전용 대시보드(semantic HTML, JS/CSS 프레임워크 없음) |

### 수정
| 파일 | 변경 |
|---|---|
| backend/Dockerfile | uvicorn → `migrate` 후 Django runserver(BACKEND_PORT) |
| backend/requirements.txt / requirements.lock.txt | Django/psycopg/pykrx만(FastAPI·uvicorn·pydantic-settings·httpx·pytest 제거) |
| docker-compose.yml | `frontend`+`backend` → 단일 `web`(FRONTEND_PORT:BACKEND_PORT), `db` 유지 |
| .env.example | CORS 제거, DJANGO_SECRET_KEY·DJANGO_ALLOWED_HOSTS 추가 |
| docs/PROJECT_SPEC.md, docs/ENVIRONMENT.md, README.md | Django 단일 서비스 기준으로 갱신 |

### 삭제(Django 동등성 검증 후)
- frontend/ 전체(package.json, tsconfig, next.config.mjs, app/layout.tsx, app/page.tsx, .eslintrc.json, Dockerfile, .dockerignore, package-lock.json)
- backend/app/ 전체(FastAPI: __init__.py, config.py, db.py, main.py, market_data.py, virtual_account.py, virtual_orders.py)
- backend/tests/ 전체(pytest: conftest.py, test_health.py, test_market_data.py, test_virtual_account.py, test_virtual_orders.py)
- backend/pytest.ini

로컬 `.env`에 `DJANGO_SECRET_KEY`·`DJANGO_ALLOWED_HOSTS`를 추가했으나 커밋하지 않았다(Git 제외). 비밀값·연결 문자열은 코드·로그·응답·문서에 없다.

## 완료 기준 대조

| 완료 기준 | 근거 | 판정 |
|---|---|---|
| 1. Django가 PostgreSQL과 기동하고 root template 렌더링 | `manage.py check` 이상 없음, 실DB 대상 `GET /` 200·대시보드 렌더 확인 | 충족(실DB 확인) |
| 2. 기존 JSON API 경로·상태 코드·응답 의미 유지 | jumong/urls.py 경로 동일, views가 기존 detail·422·200/404/409/503 유지. 비객체 JSON body(예: `[]`)도 422 JSON으로 처리(P1 수정); Django 테스트 21건 | 충족 |
| 3. 5개 테이블을 같은 이름·호환 타입 model로 사용, 요청 중 DDL 없음 | models.py db_table, 서비스 코드에 DDL 없음(migration만) | 충족 |
| 4. 새 DB·기존 DB 채택 절차 문서화·확인 | 0001_initial(SeparateDatabaseAndState+idempotent SQL); 새 테스트 DB 자동 생성 + 기존 dev DB migrate 보존 확인(아래) | 충족(양쪽 실DB 확인) |
| 5. 다음 거래일 첫 비조정 시가·pykrx 단일 경계·정수/Decimal·원장 중복 방지 유지 | orders.compute_execution/earliest_unadjusted_open_after, market_data 게이트, uq_cash_ledger_execution_order; 관련 테스트 통과 | 충족 |
| 6. 체결의 현금 확인·원장·상태 갱신이 atomic+행 잠금 | orders.execute_order: `transaction.atomic()`+`select_for_update()` | 충족 |
| 7. root template 읽기 전용(수집·초기화·체결 미시작) | views.dashboard는 조회만, 테스트에서 계좌 미생성 확인 | 충족 |
| 8. Next.js·FastAPI·CORS·불필요 Node 의존성은 동등성 검증 후 제거 | 테스트·migration·엔드투엔드 확인 후 삭제(위 삭제 목록) | 충족 |
| 9. .env에 Django 비밀 설정, Git엔 .env.example만, 비밀값 미노출 | .gitignore로 .env 제외, settings.py는 환경변수만 읽음 | 충족 |
| 10. 자동 테스트와 실 Docker PostgreSQL 결과 구분 인수인계 | 아래 "실행과 검증" | 충족 |

## 실행과 검증

### 자동 테스트 (Django test runner, 외부 pykrx mock, 실제 네트워크 없음)

테스트는 Django 테스트 DB(실제 PostgreSQL에 `test_jumong` 자동 생성·삭제)를 사용한다. 외부 증권사·pykrx·실계좌 요청 없음(pykrx는 `patch`로 mock).

| 명령 | 결과 |
|---|---|
| `python manage.py check` | System check identified no issues |
| `python manage.py makemigrations --check --dry-run` | No changes detected (model↔migration state 일치) |
| `python manage.py test trading` | **Ran 21 tests … OK** (health, 시장 데이터 검증·수집·GET 무외부호출, 정책 검증, 단일 계좌·원장, 다음 거래일 시가·비용 올림·현금 부족·반복 체결, 대시보드 읽기 전용, 비객체 JSON body 422 회귀 2건) |

### 실제 PostgreSQL 확인 — 새 테스트 DB migration

- Django 테스트 DB에서 0001_initial의 idempotent SQL이 5개 테이블·제약·유일 인덱스를 생성했고 전 테스트가 통과했다(새 DB 채택 경로 확인).

### 실제 PostgreSQL 확인 — 기존 개발 DB 데이터 보존

기존 dev `jumong` DB(로컬 Docker)에서 `python manage.py migrate` 적용 전후 비교. 기존 테이블을 DROP/TRUNCATE하지 않았고 volume을 삭제하지 않았다.

| 항목 | migrate 전 | migrate 후 |
|---|---|---|
| market_data_collection_runs | 3 | 3 |
| daily_prices | 2 | 2 |
| virtual_accounts | 1 | 1 |
| cash_ledger_entries | 2 | 2 |
| virtual_buy_orders | 3 | 3 |
| 계좌 정책 스냅샷 | id 1, v1, initial 10,000,000 | 동일 |
| 원장 합계 | 9,996,996 | 9,996,996 |
| 주문 상태 | — | filled 1 / pending 1 / rejected 1 |
| django_migrations | 없음 | 1 (trading.0001 기록) |

- 엔드투엔드(실 dev DB, Django test Client): `/health` 200 connected, `/`(대시보드) 200, `/virtual-account` 200 available 9,996,996 v1, `/virtual-orders` 200 3건, `/market-data/daily-prices` 200 2건, `/virtual-account/cash-ledger` opening_balance+buy_execution. 대시보드 조회가 계좌·주문·수집을 새로 만들지 않음을 확인.

### 실제 외부 네트워크 (해당 없음)

이 작업은 저장된 데이터만 읽거나 pykrx를 mock한다. 자동 테스트는 외부 네트워크 요청을 보내지 않는다. 실제 pykrx 공개 응답은 이전 작업들에서 현재 환경상 빈 응답으로 확인됐으며, 이 전환의 검증 대상이 아니다.

## 가정과 제한

- Django 개발 서버(`runserver`)로 web을 실행한다(MVP 로컬 기준). 운영용 WSGI 서버(gunicorn 등)는 별도 의존성이므로 이번 범위에서 추가하지 않았다.
- Django 테스트 DB 생성을 위해 `POSTGRES_USER`가 DB 생성 권한을 가져야 한다(postgres 이미지의 기본 사용자는 superuser라 충족).
- migration state의 제약 이름 일부(예: singleton check)는 기존 DB의 인라인 제약 이름과 다를 수 있으나, 실제 DDL은 idempotent SQL이 담당하므로 기존 스키마와 충돌하지 않는다. `makemigrations --check`로 state 일치를 확인했다.
- 수수료율은 계좌 스냅샷의 Float를 `Decimal(str(rate))`로 변환해 정수 올림한다. 금액·수량·현금은 정수(bigint)다.
- 동시 체결은 직접 재현하지 않았다. 계좌 행 `select_for_update()` 잠금과 `uq_cash_ledger_execution_order` 유일 인덱스로 방어하며, 유일 제약은 이전 작업에서 실DB로 확인했다.
- CSRF: JSON POST view에만 `@csrf_exempt`를 명시했다. 향후 Template POST form은 CSRF 토큰을 사용한다.

## 미해결 항목과 다음 제안

- Docker Compose 전체 스택(`web` 컨테이너) 기동 하의 HTTP 엔드투엔드 확인은 후속으로 남긴다. 이번 실DB 확인은 로컬 venv의 Django(test client·runserver 동등 경로)와 dev DB로 수행했다.
- 운영 배포 시 `runserver` 대신 WSGI 서버 채택과 정적 파일 처리(현재 화면은 정적 자산 없음)를 별도 작업으로 검토한다.
- main/dev로의 병합·push·PR 생성은 규칙에 따라 하지 않았다. Codex 검증 후 진행.

## 최종 보고
- 커밋: `f75294f`(전환), `80c7747`(최초 인수인계), `306125e`(P1 수정: 비객체 JSON body 422)
- 인수인계 파일: `docs/handoffs/T-005-claude-handoff.md`
