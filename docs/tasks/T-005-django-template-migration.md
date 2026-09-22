---
id: T-005
title: Django와 Django Template 전환
status: planned_not_started
branch: codex/django
owner: Claude Code
reviewer: Codex
depends_on: T-001, T-002, T-003, T-004
---

# T-005 Django와 Django Template 전환

## 목표

현재의 FastAPI backend와 Next.js frontend를 하나의 Django 웹 애플리케이션과 Django Template으로 전환한다. 기존 PostgreSQL 데이터와 가상투자 규칙은 보존하고, JSON API의 경로·상태 코드·핵심 응답 의미도 유지한다.

이 작업은 기능 확장이 아니라 기술 전환이다. 실제 계좌·실제 주문·자동매매는 어떤 단계에서도 만들거나 호출하지 않는다.

## 현재 기준선

- 기준 브랜치: T-004가 병합된 `dev`의 `b77951f`
- 현재 backend: FastAPI, psycopg 직접 SQL, 실행 시 `CREATE TABLE IF NOT EXISTS`
- 현재 frontend: Next.js 15/React 19이며 루트 안내 화면만 제공
- 현재 DB 테이블: `market_data_collection_runs`, `daily_prices`, `virtual_accounts`, `cash_ledger_entries`, `virtual_buy_orders`
- 유지할 규칙: pykrx 단일 일봉 제공처, 비조정 일봉, 다음 거래일 시가 체결, KRW 정수 금액, 현금 원장, 중복 체결 방지

## 전환 원칙

- `backend/`를 Django 프로젝트 루트로 계속 사용한다. 별도 Node.js frontend나 Django REST Framework를 추가하지 않는다.
- 웹 화면과 JSON API는 같은 Django 서비스·같은 origin에서 제공한다. CORS 미들웨어는 제거한다.
- 기존 테이블명과 데이터 타입을 그대로 매핑한다. 특히 금액은 `BigIntegerField`, 수집 제외 사유는 `JSONField`, 수수료율은 기존 `DOUBLE PRECISION`과 호환되는 `FloatField`를 사용한다.
- Django migration이 스키마의 유일한 관리 주체가 된다. 요청마다 실행되는 기존 SQL schema bootstrap은 제거한다.
- 이미 존재하는 로컬 DB와 새 DB 모두에서 동작해야 한다. 기존 테이블이 있을 때는 데이터를 삭제하거나 재생성하지 않는다.
- 현재 JSON API는 JSON body만 받으며 로그인·세션 인증이 없다. 호환을 위해 해당 API에 한해 CSRF 예외를 명시적으로 두고, 향후 로그인 도입 작업에서 CSRF 보호를 다시 적용한다. Template의 향후 POST form은 CSRF 토큰을 사용한다.

## 고정 설계

### 서비스와 포트

`docker-compose.yml`은 `db`와 `web` 두 서비스만 둔다.

- `web`은 기존 `backend/` 이미지에서 Django를 실행한다.
- 컨테이너 내부 포트는 `.env`의 `BACKEND_PORT`, 브라우저 공개 포트는 기존 `FRONTEND_PORT`를 사용한다. 따라서 화면은 기본적으로 `http://localhost:3000`, JSON API도 같은 origin의 `/health`, `/market-data/...` 경로에서 접근한다.
- `CORS_ALLOWED_ORIGINS`와 Node.js/Next.js 관련 설정·컨테이너는 제거한다.
- Django `SECRET_KEY`와 `ALLOWED_HOSTS`는 새 환경변수로 추가한다. 값은 `.env`에만 두고, `.env.example`에는 안전한 자리표시자만 둔다.

### Django 구성

최소 구조는 하나의 프로젝트와 하나의 도메인 앱으로 둔다.

```text
backend/
  manage.py
  jumong/                 # Django settings, URL, ASGI/WSGI
  trading/                # 모델, 서비스, JSON views, Template views, migrations, tests
  templates/trading/      # Django Template
```

- root `GET /`는 읽기 전용 dashboard template을 렌더링한다. 가상투자 경계 문구, 계좌 요약과 최근 주문을 표시할 수 있으나 수집·주문 생성·체결을 자동으로 시작하지 않는다.
- JSON API는 기존 경로를 유지한다. Django 내부의 서비스 함수와 template view가 필요한 읽기 기능을 공유할 수는 있으나, 한 번만 쓰이는 계층·클래스는 만들지 않는다.
- 신규 API, DRF, SPA, WebSocket, 사용자 인증·다중 사용자, 주문 form UI는 이번 범위에 넣지 않는다.

### DB 채택과 보존

첫 Django migration은 다음 두 경우를 모두 처리한다.

1. 새 DB: 현재 스키마와 호환되는 테이블·제약·인덱스를 생성한다.
2. 기존 DB: `CREATE TABLE IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, 유일 인덱스 확인으로 기존 행을 보존하고 Django model state만 등록한다.

이를 위해 migration 안에서 idempotent SQL과 `SeparateDatabaseAndState`를 사용한다. 기존 테이블을 `DROP`, `TRUNCATE`, volume 삭제로 초기화하지 않는다. 데이터 보존이 불가능한 스키마 불일치가 나오면 임의로 수정하지 말고 Codex에 보고한다.

| 기존 테이블 | Django model | 보존할 핵심 제약 |
|---|---|---|
| `market_data_collection_runs` | `MarketDataCollectionRun` | `run_id` PK, JSON 제외 사유 |
| `daily_prices` | `DailyPrice` | `(ticker, trade_date)` 유일, 비조정 가격 메타데이터 |
| `virtual_accounts` | `VirtualAccount` | 단일 계좌 singleton 유일성, 정책 스냅샷 |
| `cash_ledger_entries` | `CashLedgerEntry` | 추가 전용 원장, nullable `execution_order_id` 유일 인덱스 |
| `virtual_buy_orders` | `VirtualBuyOrder` | 수량 양수, 주문 상태 제약, 체결 근거 보존 |

`cash_ledger_entries.execution_order_id`와 `daily_prices.collection_run_id`는 현재 DB에 외래키가 아니므로, 이번 전환에서 외래키로 바꾸지 않는다. 이는 데이터 모델 개선이 아니라 전환 작업이기 때문이다.

## 단계별 구현 계획

### 1. 기준선과 Django 기동

- 변경 전 기존 backend 테스트를 실행하고 결과를 기록한다. 실행하지 못한 검증은 통과로 쓰지 않는다.
- `Django`만 새 런타임 의존성으로 추가한다. Django REST Framework, 별도 환경변수 라이브러리, JavaScript UI 라이브러리는 추가하지 않는다.
- `jumong/settings.py`를 유일한 Django 설정 계층으로 만든다. 비밀값·DB 접속 정보·허용 호스트는 환경변수로만 읽고 로그·응답에 노출하지 않는다.
- Django health endpoint는 기존처럼 DB 연결 성공 시 200, 실패 시 503과 `status`, `app_env`, `database` 의미를 유지한다.
- 같은 origin 구성으로 바뀌므로 FastAPI CORS 미들웨어와 CORS 환경변수 사용을 제거한다.

### 2. 모델과 안전한 migration

- 위 다섯 테이블을 정확한 `db_table` 이름으로 model에 매핑한다.
- 새 DB와 기존 DB를 모두 채택할 수 있는 첫 migration을 작성한다. 재실행 안전한 DDL 외에 요청 처리 중 DDL을 실행하지 않는다.
- migration 전후에 각 테이블의 행 수, 기존 계좌의 정책 스냅샷, 원장 합계, 주문의 상태·체결 금액을 비교할 수 있는 검증 절차를 준비한다.
- 기존 개발 DB가 없거나 접근할 수 없는 경우에는 새 테스트 DB migration 결과만 기록하고, 실제 기존 데이터 보존 검증은 미확인으로 남긴다.

### 3. 도메인 로직과 JSON API 이식

아래 경로와 관찰 가능한 동작을 유지한다.

| 경로 | 유지할 동작 |
|---|---|
| `GET /health` | DB 상태를 200 또는 503으로 정직하게 반환 |
| `POST /market-data/daily-prices/collect` | `MARKET_DATA_PROVIDER=pykrx`일 때만 pykrx 수집·검증·실행 기록 저장 |
| `GET /market-data/daily-prices` | 저장 가격을 거래일 오름차순 조회, 외부 요청 없음 |
| `POST /virtual-account/initialize` | 단일 계좌와 opening balance를 한 번만 원자적으로 생성 |
| `GET /virtual-account` | 정책 스냅샷과 원장 합계 기반 가용 현금 조회 |
| `GET /virtual-account/cash-ledger` | 추가 전용 원장 오름차순 조회 |
| `POST /virtual-orders` | 결정일 비조정 일봉이 있을 때만 pending 매수 주문 생성 |
| `POST /virtual-orders/{order_id}/execute` | 다음 거래일 첫 비조정 시가·정수/Decimal 비용 규칙으로 수동 체결 |
| `GET /virtual-orders` | 외부 수집·체결 없이 주문 오름차순 조회 |

- 오류 body는 기존처럼 안전한 `detail` 메시지를 사용하고, 입력 검증은 422를 유지한다.
- `transaction.atomic()`과 `select_for_update()`로 계좌 잠금·주문 잠금·원장 추가·주문 상태 갱신을 한 트랜잭션에 둔다.
- 체결 가격은 `trade_date > decision_trade_date`인 가장 이른 저장 비조정 일봉의 시가만 사용한다. 같은 날 가격·종가·외부 수집은 금지한다.
- 매수 체결 비용은 현재와 같은 정수 올림·`Decimal` 규칙을 사용하고, 반복 체결은 기존 결과만 반환해 원장을 중복하지 않는다.

### 4. Django Template과 컨테이너 전환

- root template은 읽기 전용으로 렌더링한다. account 또는 DB가 없을 때도 외부 수집·계좌 초기화 없이 안내 문구를 표시한다.
- template은 semantic HTML, 제목 계층, 표의 caption·header를 사용한다. CSS framework와 JavaScript 의존성은 넣지 않는다.
- `docker-compose.yml`에서 `frontend`와 FastAPI `backend` 서비스를 단일 `web` 서비스로 바꾼다. PostgreSQL volume과 서비스 이름 `db`는 유지한다.
- Django로 모든 테스트·Docker 기동·핵심 경로 확인이 끝난 뒤에만 `frontend/`, `backend/app/`, FastAPI·Next.js 의존성 파일을 제거한다. 제거는 같은 작업 브랜치에서 하고, 삭제 목록을 인수인계에 기록한다.

### 5. 문서·검증·인수인계

- `docs/PROJECT_SPEC.md`, `docs/ENVIRONMENT.md`, `.env.example`, `README.md`를 Django 단일 서비스 기준으로 갱신한다.
- 모든 Python 테스트는 Django 기본 test runner로 실행한다. 외부 pykrx와 실제 계좌·주문 API는 mock 처리한다.
- 최소 테스트는 health, 시장 데이터 검증·upsert·GET 무외부호출, 계좌 단일화·원장, 다음 거래일 시가·비용 올림·현금 부족·반복 체결, root template 렌더링을 포함한다.
- 가능하면 Docker PostgreSQL에서 기존 데이터 보존과 주문 체결 원장 일관성을 별도로 확인한다. mock 테스트와 실제 DB 결과를 섞지 않는다.
- `docs/handoffs/T-005-claude-handoff.md`에 변경 파일, 완료 기준별 위치, 실행 명령·결과, mock/실DB/외부 네트워크 구분, 삭제 목록, 가정·제한을 남긴다.

## 제외 범위

- 매도, 보유 수량, 평가액, 손익·수익률, 손실 한도 경고
- 실제 증권 계좌, 실제 주문, 자동매매, 투자 조언
- 실시간·장중 가격, 새 데이터 제공처, 스케줄러·큐
- 로그인, 다중 사용자, 권한, Notion 내보내기
- Django REST Framework, SPA 재구현, React/Next.js 유지, 신규 UI form
- 데이터베이스 초기화·volume 삭제·기존 거래 데이터 삭제

## 완료 기준

1. `codex/django`에서 Django가 PostgreSQL과 함께 기동하고 root template을 렌더링한다.
2. 기존 JSON API 경로와 핵심 성공·오류 상태 코드 및 응답 의미가 유지된다.
3. 기존 다섯 테이블을 Django model이 같은 이름·호환 타입으로 사용하며, 요청 처리 중 schema DDL을 실행하지 않는다.
4. 새 DB migration과 기존 DB 채택 절차가 모두 문서화되고, 실제로 확인한 범위를 구분해 기록한다.
5. 다음 거래일 첫 비조정 시가 규칙, pykrx 단일 수집 경계, 정수 금액·Decimal 비용 계산, 원장 중복 방지가 유지된다.
6. 체결의 현금 확인·원장 추가·주문 상태 갱신은 `transaction.atomic()`과 행 잠금으로 원자적으로 처리된다.
7. root template은 읽기 전용이며 외부 수집·계좌 초기화·주문 체결을 시작하지 않는다.
8. Next.js·FastAPI·CORS·불필요한 Node 의존성은 Django 동등성 검증 후에만 제거된다.
9. `.env`에는 Django 비밀 설정이 남아 있지만 Git에는 `.env.example`만 저장되고, 비밀값·연결 문자열은 코드·로그·문서에 없다.
10. 자동 테스트 결과와 실제 Docker PostgreSQL 결과를 구분한 인수인계가 있다.

## Claude Code 완료 보고

`docs/handoffs/CLAUDE_HANDOFF_TEMPLATE.md` 형식으로 `docs/handoffs/T-005-claude-handoff.md`를 작성한다. 기존 DB 데이터가 있던 경우와 새 테스트 DB의 결과를 구분하고, 실제 DB를 검증하지 못했다면 그 사실을 명시한다. push, PR 생성, 병합은 하지 않는다.
