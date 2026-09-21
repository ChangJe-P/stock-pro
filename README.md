# 주몽 (Jumong)

국내 주식 초보자를 위한 가상투자·주식 학습 웹 프로젝트입니다. 실제 시장 일봉 데이터를 사용하되 가상 현금만 사용하며, 실제 계좌와 주문은 연결하지 않습니다.

## 구성

| 서비스 | 기술 | 컨테이너 내부 포트 | 호스트 노출 포트 |
|---|---|---|---|
| frontend | Next.js (TypeScript), node:22 | 3000 | `FRONTEND_PORT` (기본 3000) |
| backend | FastAPI (Python), python:3.12 | 8000 | `BACKEND_PORT` (기본 8000) |
| db | PostgreSQL 16 | 5432 | `POSTGRES_PORT` (기본 5432) |

포트·호스트·DB 자격 증명은 모두 `.env`에서 읽습니다. 코드나 Docker Compose 파일에 직접 적지 않습니다.

## 사전 준비

1. Docker Desktop(Compose v2 포함)을 설치합니다.
2. 저장소 루트에서 `.env.example`을 `.env`로 복사합니다.

   ```bash
   cp .env.example .env
   ```

3. `.env`의 `POSTGRES_PASSWORD`를 로컬 개발용 비밀번호로 바꿉니다. `.env`는 Git에 커밋하지 않습니다.
4. 시장 데이터 수집은 `MARKET_DATA_PROVIDER=pykrx`일 때만 동작합니다(`.env.example` 기본값). pykrx는 키·주소가 필요 없으므로 나머지 `MARKET_DATA_`·`NOTION_` 변수는 빈 값으로 둡니다. 이 값들이 비어 있어도 개발 환경은 정상 기동됩니다.

## 실행

저장소 루트에서 실행합니다.

```bash
docker compose up -d --build
```

- backend는 db가 healthcheck를 통과한 뒤에만 시작합니다.
- backend 상태 확인: `http://localhost:${BACKEND_PORT}/health` (기본 http://localhost:8000/health)
  - 정상: HTTP 200, `{"status":"ok","database":"connected", ...}`
  - DB 미준비: HTTP 503, `{"status":"unhealthy","database":"unavailable", ...}`
- frontend 루트 화면: `http://localhost:${FRONTEND_PORT}` (기본 http://localhost:3000)

## 종료

```bash
docker compose down
```

DB 데이터(영속 볼륨)까지 삭제하려면:

```bash
docker compose down -v
```

## 시장 데이터 수집 API (T-002)

국내 주식 **일봉 OHLCV**를 `pykrx` 공개 조회로 한 종목·기간씩 수집해 PostgreSQL에 저장하고 조회하는 backend 전용 API입니다. 이후 가상 주문의 다음 거래일 시가 체결·수익률 계산의 입력값으로 쓰입니다.

- **목적/한계**: 학습용 참고 데이터입니다. **투자 조언이나 수익 보장을 제공하지 않습니다.** 수집 가격은 수집 시점의 **비조정(adjusted=False)** 값이며, 배당·액면분할 등 기업행동은 반영하지 않습니다. 전 종목 일괄 수집·스케줄러·실시간 시세는 제공하지 않습니다.
- **실행 전 설정**: `MARKET_DATA_PROVIDER=pykrx`가 필요합니다. 비어 있거나 다른 값이면 수집은 외부 요청 없이 `503` 설정 오류로 끝납니다.

### 수집 — `POST /market-data/daily-prices/collect`

본문(JSON)으로 한 종목·기간을 수집·저장합니다. GET 조회는 외부 수집을 시작하지 않습니다.

```bash
curl -X POST http://localhost:8000/market-data/daily-prices/collect \
  -H "Content-Type: application/json" \
  -d '{"ticker":"005930","from_date":"2024-01-02","to_date":"2024-01-05"}'
```

- `ticker`: 숫자 6자리, 날짜: ISO `YYYY-MM-DD`, `from_date <= to_date` (위반 시 `422`).
- 응답: 종목·요청 기간·출처·비조정 여부·수집 기준 시각·원본 SHA-256 해시·반환/삽입/갱신/제외 행 수·상태와 제외 사유.
- 같은 `(종목, 거래일)` 재수집 시 중복 없이 기존 행을 갱신합니다. 0/음수 가격·잘못된 OHLC 관계·기간 밖 날짜·중복 거래일은 제외하고 그 사유·건수를 실행 기록에 남깁니다.

### 조회 — `GET /market-data/daily-prices`

```bash
curl "http://localhost:8000/market-data/daily-prices?ticker=005930&from_date=2024-01-02&to_date=2024-01-05"
```

저장된 데이터를 거래일 오름차순으로 반환하며 외부 수집을 하지 않습니다.

## 가상계좌·현금 원장 API (T-003)

단일 로컬 사용자의 **가상 학습 계좌**와 추가 전용(append-only) 현금 원장을 만드는 backend 전용 API입니다. 모든 금액은 KRW 정수이며, 현재 현금은 원장 금액의 합으로 계산합니다.

- **가상 현금 경계**: 최초 현금·수수료·세금·슬리피지는 **실제 돈·실제 증권사 값이 아닌** 학습용 시뮬레이션 정책(v1) 가정입니다. 실제 계좌·계좌번호·로그인·주문·체결·손익 계산은 포함하지 않습니다. 투자 조언이 아닙니다.
- **정책 스냅샷**: 값은 `VIRTUAL_*` 환경변수(설정 계층)에서만 읽어 계좌 최초 생성 시 스냅샷으로 저장합니다. 이후 값을 바꿔도 **기존 계좌에는 소급 적용되지 않습니다.** 설정 누락·형식·범위 오류는 값 노출 없이 안전하게 실패합니다.
- **v1 가정과 제한**: 시작 현금 10,000,000 KRW, 매수·매도 수수료율 0.015%, 매도 세금율 0%, 슬리피지 0 bps. 자세한 규칙은 docs/ENVIRONMENT.md 참조.

### 초기화 — `POST /virtual-account/initialize`

계좌가 없으면 설정 스냅샷으로 계좌 한 개와 `opening_balance` 원장 한 개를 원자적으로 생성합니다. 이미 있으면 **재설정·행 추가 없이** 기존 계좌를 반환합니다.

```bash
curl -X POST http://localhost:8000/virtual-account/initialize
```

### 계좌 조회 — `GET /virtual-account`

```bash
curl http://localhost:8000/virtual-account
```

계좌 식별자·생성 시각·정책 버전·정책 스냅샷·최초 현금·원장 합계로 계산한 `available_cash_krw`를 반환합니다. 계좌가 없으면 404입니다.

### 현금 원장 조회 — `GET /virtual-account/cash-ledger`

```bash
curl http://localhost:8000/virtual-account/cash-ledger
```

원장 행을 생성 시각 오름차순으로 반환합니다(수정·삭제 경로 없음). 계좌가 없으면 404입니다.

## 가상 매수 주문·다음 거래일 시가 체결 API (T-004)

학습용 **매수 주문**을 기록하고, 주문을 결정한 거래일보다 **엄격히 뒤인** 첫 저장 일봉 시가로 수동 체결하는 backend 전용 API입니다. **실제 투자가 아니며** 실제 계좌·주문·자동매매와 무관합니다.

- **매수 전용**: 이 단계는 `buy`만 지원합니다. 매도·취소·수정·수량 변경·포지션·손익은 포함하지 않습니다.
- **다음 거래일 시가 원칙**: 체결은 `daily_prices`에서 `trade_date > decision_trade_date`인 **가장 이른** 비조정 일봉의 `open_price`만 사용합니다. 같은 날 가격·종가는 쓰지 않아 미래 데이터 누수를 막습니다. 가격 조회·체결은 pykrx·외부 수집을 호출하지 않고 **저장된 데이터만** 읽습니다.
- **대기 주문은 현금을 예약하지 않음**: 주문 생성은 현금을 차감하지 않습니다. 체결 시점의 원장 합계 현금을 기준으로 판단합니다.
- **비용 가정**: 슬리피지·수수료는 T-003 계좌의 정책 스냅샷(v1)에서 읽어 정수·명시적 올림으로 적용합니다.
  - `execution_price_krw = ceil(open_price × (10000 + slippage_bps) / 10000)`
  - `gross = execution_price × quantity`, `fee = ceil(gross × buy_fee_rate)`, `cash_delta = -(gross + fee)`

### 1) 주문 생성 — `POST /virtual-orders`

먼저 대상 종목·결정 거래일의 일봉이 저장돼 있어야 합니다(없으면 외부 수집 없이 409). 계좌가 없으면 404, 형식 오류는 422입니다.

```bash
curl -X POST http://localhost:8000/virtual-orders \
  -H "Content-Type: application/json" \
  -d '{"ticker":"005930","quantity":3,"decision_trade_date":"2024-01-02"}'
```

성공 시 `pending` 주문을 만들고 현금 원장은 추가하지 않습니다.

### 2) 수동 체결 — `POST /virtual-orders/{order_id}/execute`

지정한 `pending` 주문 한 건만 체결을 시도합니다.

```bash
curl -X POST http://localhost:8000/virtual-orders/1/execute
```

- 다음 거래일 시가가 아직 없으면 주문을 바꾸지 않고 `409`(pending 유지)입니다.
- 가격이 있고 현금이 충분하면 `filled`와 음수 `buy_execution` 현금 원장 한 행을 원자적으로 기록합니다.
- 현금이 부족하면 `rejected_insufficient_cash`로 종료하며 원장을 만들지 않습니다.
- 이미 종료된 주문(`filled`/`rejected_insufficient_cash`)을 다시 체결하면 기존 결과만 반환합니다.

### 3) 주문 조회 — `GET /virtual-orders`

```bash
curl http://localhost:8000/virtual-orders
```

주문을 `created_at`·`id` 오름차순으로 반환하며 외부 수집·체결·상태 변경을 시작하지 않습니다.

## 테스트·검증

### backend (pytest)

```bash
cd backend
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux:        source .venv/bin/activate
pip install -r requirements.txt
pytest
```

실제 설치된 backend 의존성 버전은 `backend/requirements.lock.txt`에 기록되어 있습니다.

### frontend (타입·린트 검증)

```bash
cd frontend
npm install
npm run typecheck
npm run lint
```

## DBeaver 연결

`docker compose up` 이후 호스트에서 아래 값으로 접속합니다. 모두 `.env` 값과 일치합니다.

| 항목 | 값 |
|---|---|
| Host | localhost |
| Port | `POSTGRES_PORT` (기본 5432) |
| Database | `POSTGRES_DB` (기본 jumong) |
| Username | `POSTGRES_USER` (기본 jumong_app) |
| Password | `.env`의 `POSTGRES_PASSWORD` |

컨테이너 사이에서 backend는 `POSTGRES_HOST`(기본 `db`)로 접속하고, 호스트의 DBeaver는 `localhost`로 접속합니다.

## 작업 흐름

1. Codex가 작업 명세, Skill, 기능 브랜치를 준비합니다.
2. Claude Code가 현재 작업 문서를 읽고 구현과 테스트를 진행합니다.
3. Claude Code가 인수인계 문서를 작성합니다.
4. Codex가 Git diff와 테스트 증거를 검증합니다.

## 시작 문서

- 프로젝트 방향: docs/PROJECT_SPEC.md
- 현재 작업: docs/tasks/T-001-project-foundation.md
- Claude Code 프롬프트: docs/prompts/claude/T-001-implementation.md
- Codex 검증 프롬프트: docs/prompts/codex/T-001-review.md
- 시장 데이터 수집 Skill: skills/market-data-collector/SKILL.md
- 환경변수·비밀값 규칙: docs/ENVIRONMENT.md
