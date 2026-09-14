---
id: T-001
title: Docker 기반 주몽 개발 환경 구성
status: ready_for_claude
branch: codex/setup
owner: Claude Code
reviewer: Codex
---

# T-001 Docker 기반 주몽 개발 환경 구성

## 목표

Next.js frontend, FastAPI backend, PostgreSQL을 Docker Compose로 함께 실행할 수 있는 로컬 개발 기반을 만든다.

## 구현 범위

- frontend: TypeScript 기반 Next.js 최소 화면. 루트 화면에서 서비스명과 frontend 상태를 확인할 수 있어야 한다.
- backend: FastAPI 애플리케이션과 GET /health 엔드포인트. 정상 시 HTTP 200과 상태 JSON을 반환한다.
- database: PostgreSQL 컨테이너, 영속 볼륨, backend 연결 설정.
- orchestration: 프로젝트 루트의 Docker Compose 설정으로 세 서비스를 실행한다.
- configuration: .env.example, 비밀값을 제외한 환경변수 설명, .gitignore.
- verification: backend 단위 또는 API 테스트와 frontend의 타입 또는 린트 검증을 추가한다.
- documentation: README에 최초 실행, 종료, 테스트 명령, DBeaver 연결 정보를 작성한다.

## 제외 범위

- 실제·가상 주문, 주가 API, 데이터 수집, 백테스트, Notion API
- 로그인, 다중 사용자, AWS 배포
- Docker Compose 이외의 오케스트레이션 도구

## 구현 제약

- AGENTS.md의 제품·Git·인수인계 규칙을 지킨다.
- API 키나 DB 비밀번호는 .env.example에 예시 변수명만 둔다.
- 컨테이너 포트, 서비스명, 이미지·런타임 버전은 README와 환경 예시에 일관되게 기록한다.
- backend는 환경변수로 database URL을 받는다.
- database가 준비되기 전에 backend가 성공했다고 표시하지 않는다. healthcheck와 의존성 처리 방식은 재현 가능해야 한다.
- 의존성의 최신 버전을 추측해 고정하지 말고, 실제 설치한 버전 또는 허용 범위를 lockfile·설정에 남긴다.

## 완료 기준

1. 새 환경에서 .env.example을 이용해 환경 파일을 준비할 수 있다.
2. Docker Compose 실행으로 frontend, backend, database가 모두 시작된다.
3. backend의 GET /health가 HTTP 200과 상태 JSON을 반환한다.
4. backend가 PostgreSQL 연결 실패를 정상 상태로 보고하지 않는다.
5. frontend 루트 화면이 실행된다.
6. README의 실행·종료·테스트·DBeaver 연결 절차가 현재 설정과 일치한다.
7. 관련 테스트와 린트 또는 타입 검증이 통과한다.
8. docs/handoffs/T-001-claude-handoff.md에 증거를 남긴다.

## 완료 보고 형식

인수인계 양식은 docs/handoffs/CLAUDE_HANDOFF_TEMPLATE.md를 복사해 T-001-claude-handoff.md로 작성한다. 성공한 명령뿐 아니라 실패했거나 실행하지 못한 검증도 기록한다.
