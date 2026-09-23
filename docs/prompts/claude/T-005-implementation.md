# Claude Code 구현 요청: T-005 Django와 Django Template 전환

## 시작 전 필독

아래 파일을 순서대로 읽고, 충돌하면 T-005 작업 문서의 범위와 완료 기준을 따른다.

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/ENVIRONMENT.md`
4. `docs/tasks/T-005-django-template-migration.md`
5. `skills/market-data-collector/SKILL.md`
6. `skills/virtual-trading-account/SKILL.md`
7. `skills/virtual-order-execution/SKILL.md`

현재 브랜치가 `codex/django`인지 확인한 뒤 구현해줘. 이 작업은 기술 전환이며, 실제 계좌·실제 주문·자동매매를 절대 구현하거나 호출하지 마.

## 구현 요청

FastAPI backend와 Next.js frontend를 Django + Django Template 단일 웹 서비스로 전환해줘. `backend/`는 유지하고, Django project와 하나의 `trading` app을 그 안에 만든다.

- root `GET /`는 읽기 전용 Django Template dashboard를 렌더링한다. 계좌 요약·최근 주문을 표시할 수 있지만 외부 수집, 계좌 초기화, 주문 생성·체결을 자동으로 시작하면 안 된다.
- 기존 JSON API 경로와 의미를 보존한다: `/health`, `/market-data/daily-prices`, `/virtual-account`, `/virtual-orders`의 T-004까지의 세부 경로·상태 코드·응답 key를 유지한다.
- JSON POST API는 기존 비로그인 local API 호환을 위해 해당 view에만 CSRF 예외를 명시한다. Template form을 새로 만들지 말고, 향후 form 작업에서는 CSRF 토큰을 사용한다.
- Django REST Framework, Node.js, React, Next.js, SPA, 별도 설정 라이브러리를 추가하지 마. 필요한 새 런타임 의존성은 Django 하나뿐이다.

## DB와 도메인 규칙

- Django model은 `market_data_collection_runs`, `daily_prices`, `virtual_accounts`, `cash_ledger_entries`, `virtual_buy_orders`의 기존 테이블명과 호환 타입을 사용한다.
- 첫 migration은 새 DB에서는 테이블을 만들고, 기존 개발 DB에서는 기존 행을 보존하면서 Django state를 등록해야 한다. idempotent SQL과 `SeparateDatabaseAndState`를 사용해도 된다.
- 기존 테이블·volume을 삭제하거나 `DROP`, `TRUNCATE`, `docker compose down -v`를 실행하지 마. 불일치가 발견되면 임의로 고치지 말고 인수인계에 남겨줘.
- 요청 때마다 실행되던 FastAPI의 schema DDL은 제거한다. migration만 schema를 관리한다.
- 모든 KRW 금액은 `BigIntegerField`로 유지한다. 기존 `DOUBLE PRECISION` 정책 스냅샷은 호환을 위해 `FloatField`로 두되, 체결 수수료 계산은 `Decimal(str(rate))`와 명시적 올림을 계속 사용한다.
- `cash_ledger_entries.execution_order_id`와 `daily_prices.collection_run_id`를 새 외래키로 바꾸지 마. 현재 데이터 호환을 유지한다.

아래 투자 규칙은 반드시 유지한다.

- 시장 데이터 수집은 `MARKET_DATA_PROVIDER=pykrx`일 때만 pykrx를 호출한다. 직접 HTTP, 다른 제공처, 키·endpoint 사용은 금지한다.
- 조회 GET, 주문 생성, 주문 체결은 외부 가격 수집을 시작하지 않는다.
- 매수 체결은 `trade_date > decision_trade_date`인 가장 이른 저장 비조정 일봉의 시가만 사용한다. 같은 날 가격·종가는 사용하지 않는다.
- 성공 체결은 `transaction.atomic()`과 `select_for_update()`에서 계좌 현금 확인, 음수 `buy_execution` 원장 한 행 추가, 주문 `filled` 갱신을 한 번만 처리한다.
- 현금 부족은 원장 없이 `rejected_insufficient_cash`, 다음 거래일 가격 부재는 `pending` 유지와 409, 종료 주문 재호출은 기존 결과 반환이다.

## Docker·환경 전환

- Compose는 `db`와 단일 `web` 서비스로 전환한다. `web`은 Django를 실행하며 DB volume은 유지한다.
- 호스트 공개 포트는 기존 `FRONTEND_PORT`, 컨테이너 내부 Django 포트는 `BACKEND_PORT` 환경변수를 사용한다. 포트·호스트·비밀값을 코드에 직접 적지 마.
- 같은 origin이므로 FastAPI CORS 코드와 `CORS_ALLOWED_ORIGINS` 사용을 제거한다.
- `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`를 설정 계층·`.env.example`·환경 문서에 추가한다. `.env`의 실제 값, DB 비밀번호, 전체 연결 문자열은 코드·커밋·로그·문서에 넣지 마.
- Django의 모든 설정값은 `jumong/settings.py`에서 읽는다. 비밀값과 연결 문자열을 오류 응답에 포함하지 마.

## 제거 순서와 문서

1. Django 기동, migration, JSON API 동등성, root template 테스트를 먼저 통과시킨다.
2. 그 뒤에만 `frontend/`, FastAPI module, FastAPI/uvicorn/Next.js 및 실제로 쓰지 않는 의존성을 제거한다.
3. `README.md`, `docs/PROJECT_SPEC.md`, `docs/ENVIRONMENT.md`, `.env.example`을 Django 단일 서비스 기준으로 갱신한다.

기능 범위를 넘는 매도·포지션·손익·수익률·인증·Notion·스케줄러·새 UI form은 만들지 마.

## 테스트와 인수인계

- 기존 자동 테스트를 Django 기본 test runner로 이식하거나 동등하게 대체한다. 외부 pykrx·실제 증권사·실제 계좌 요청은 mock 처리한다.
- health, 시장 데이터 검증·upsert·GET 무외부호출, 단일 계좌·원장, 다음 거래일 시가·비용 올림·현금 부족·반복 체결, root template 렌더링을 테스트한다.
- 가능하면 Docker PostgreSQL에서 기존 테이블 행 수와 계좌 정책·원장 합계·주문 상태 보존을 확인한다. 자동 테스트·실제 DB·실외부 네트워크 결과를 섞어 쓰지 마.
- `docs/handoffs/CLAUDE_HANDOFF_TEMPLATE.md` 형식으로 `docs/handoffs/T-005-claude-handoff.md`를 작성한다. 변경·삭제 파일 전체, 완료 기준별 위치, 실행 명령·결과, mock/실DB/외부 네트워크 구분, 데이터 보존 검증, 가정·제한·미해결 항목을 남겨줘.
- 논리적인 커밋을 만들되, **push·PR 생성·병합은 하지 마.** 완료 후 최종 커밋 해시와 인수인계 파일 경로를 알려줘.
