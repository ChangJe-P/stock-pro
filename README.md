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
4. 시장 데이터·Notion 변수는 제공처가 정해지기 전까지 빈 값으로 둡니다. 이 값들이 비어 있어도 개발 환경은 정상 기동됩니다.

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
