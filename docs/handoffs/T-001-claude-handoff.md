---
task_id: T-001
branch: codex/setup
commit: 41c610b
status: complete
---

# Claude Code 구현 인수인계

## 작업 요약

- 구현한 내용: Next.js(TS) frontend, FastAPI backend, PostgreSQL 16을 Docker Compose로 함께 실행하는 로컬 개발 기반. backend `GET /health`는 DB 연결을 확인해 정상 시 200, DB 미준비 시 503을 반환한다. 설정값은 `.env`에서만 읽고 코드·Compose에 하드코딩하지 않는다.
- 구현하지 않은 내용: 실제·가상 주문, 주가 API, 데이터 수집, Notion API, 로그인/다중 사용자, AWS 배포 (모두 T-001 제외 범위).

## 변경·생성 파일

| 파일 | 변경 이유 |
|---|---|
| docker-compose.yml | db/backend/frontend 3서비스 오케스트레이션, DB healthcheck + depends_on, `.env` 변수 치환 |
| backend/app/config.py | pydantic-settings 기반 설정 계층. 필수 DB 값 누락 시 명시적 오류, 외부 연동 값은 비어도 기동 허용 |
| backend/app/db.py | psycopg로 `SELECT 1` 연결 확인. 실패해도 연결 문자열/비밀값을 로그에 남기지 않음 |
| backend/app/main.py | FastAPI 앱, CORS, `GET /health` (DB 실패 시 503) |
| backend/app/__init__.py | 패키지 초기화 |
| backend/requirements.txt | 의존성 허용 범위(최신 버전 추측 고정 아님) |
| backend/requirements.lock.txt | 실제 설치된 버전 기록 (`pip freeze`) |
| backend/tests/test_health.py | /health 200/503 동작 테스트 (DB는 monkeypatch로 대체) |
| backend/tests/conftest.py | 테스트용 더미 환경변수(실제 비밀값 아님) |
| backend/pytest.ini | pytest testpaths 설정 |
| backend/Dockerfile, backend/.dockerignore | backend 실행 이미지 |
| frontend/app/page.tsx | 루트 화면. 서비스명(주몽)과 frontend 상태 표시 |
| frontend/app/layout.tsx | 루트 레이아웃 |
| frontend/package.json, package-lock.json | 의존성 및 dev/build/lint/typecheck 스크립트, 실제 설치 lockfile |
| frontend/tsconfig.json, next.config.mjs, .eslintrc.json | Next.js/TS/lint 설정 |
| frontend/Dockerfile, frontend/.dockerignore | frontend 실행 이미지 |
| README.md | 실행/종료/테스트/DBeaver 연결 절차, 서비스·포트 표 |
| .gitignore | next-env.d.ts, *.tsbuildinfo 추가 |

## 완료 기준 대조

| 완료 기준 | 구현 위치 또는 증거 | 판정 |
|---|---|---|
| 1. .env.example로 환경 파일 준비 | .env.example → .env 복사, README 사전 준비 절차 | 충족 |
| 2. Compose로 3서비스 시작 | `docker compose up -d --build` 후 db(healthy)/backend/frontend 모두 Up | 충족 |
| 3. GET /health 200 + 상태 JSON | `{"status":"ok","app_env":"development","database":"connected"}` HTTP 200 | 충족 |
| 4. DB 실패를 정상으로 보고하지 않음 | db 중지 후 /health → HTTP 503 `{"status":"unhealthy","database":"unavailable"}`; 단위 테스트로도 검증 | 충족 |
| 5. frontend 루트 화면 실행 | http://localhost:3000 HTTP 200, "주몽" / "정상 실행 중" 렌더 확인 | 충족 |
| 6. README 실행·종료·테스트·DBeaver 절차 일치 | README.md, DBeaver 값은 .env와 일치, DB 포트 노출됨 | 충족 |
| 7. 환경변수/키 누락을 값 노출 없이 명시적 처리 | 외부 연동 변수 빈 값으로 정상 기동, backend 로그에 비밀번호 미검출(grep 0건), DB 실패 로그는 일반 메시지 | 충족 |
| 8. 테스트·린트·타입 검증 통과 | pytest 2 passed, npm run typecheck 무오류, npm run lint 무경고/오류 | 충족 |
| 9. 인수인계 문서 작성 | 본 문서 | 충족 |

## 실행과 검증

| 명령 | 결과 |
|---|---|
| `pytest` (backend, .venv) | 2 passed (health 200 / health 503) |
| `pip freeze` → requirements.lock.txt | fastapi 0.141.1, uvicorn 0.53.0, pydantic-settings 2.15.0, psycopg 3.3.5, httpx 0.28.1, pytest 8.4.2 |
| `npm install` (frontend) | 304 packages, package-lock.json 생성 |
| `npm run typecheck` | 오류 없음 |
| `npm run lint` | ✔ No ESLint warnings or errors (next lint deprecated 경고만) |
| `docker compose config` | 유효, `.env` 치환 정상 |
| `docker compose up -d --build` | db healthy 후 backend/frontend 기동 |
| `curl http://localhost:8000/health` | HTTP 200, database connected |
| `docker compose stop db` 후 `curl .../health` | HTTP 503, database unavailable |
| `docker compose start db` 후 `curl .../health` | HTTP 200 복구 |
| `curl http://localhost:3000` | HTTP 200, "주몽"/"정상 실행 중" 포함 |
| `docker compose logs backend \| grep jumong1234` | 0건 (비밀번호 로그 미노출) |
| `docker compose down` | 컨테이너·네트워크 정리 (postgres-data 볼륨은 유지) |

## 가정과 제한

- Python 런타임은 컨테이너에서 python:3.12-slim, node는 node:22-slim을 사용한다. 로컬 검증은 Python 3.14, Node 24로도 통과했다.
- 의존성은 허용 범위로 두고 실제 설치 버전을 lockfile(`backend/requirements.lock.txt`, `frontend/package-lock.json`)에 남겼다.
- DB 포트(`POSTGRES_PORT`)를 호스트에 노출해 DBeaver 접속을 지원한다(완료 기준 6). 로컬 개발 전용이다.
- frontend 루트 화면은 정적 문구로 frontend 상태만 표시하며, backend /health를 호출하지 않는다(T-001 범위 내 최소 화면).
- `next lint`는 Next.js에서 deprecated 경고를 내지만 현재 정상 동작한다. 린터 마이그레이션은 별도 작업 대상.
- 테스트 fixture(conftest.py)의 DB 값은 실제 비밀값이 아닌 로컬 테스트용 더미이며 실제 연결에 쓰이지 않는다(check_database monkeypatch).

## 미해결 항목과 다음 제안

- `next lint` → ESLint CLI 마이그레이션(Next.js 16 대비)은 후속 작업으로 분리 권장.
- backend에 대한 실제 DB 통합 테스트(컨테이너 DB 대상)는 T-001 범위 밖으로 두었다. 데이터 계층 작업 시 추가 권장.
- main/dev로의 병합·push는 규칙에 따라 수행하지 않았다. Codex 검증 후 진행.
