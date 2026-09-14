# Claude Code 전달 프롬프트 — T-001

아래 프로젝트에서 T-001을 구현해줘.

시작 전에 AGENTS.md, CLAUDE.md, docs/PROJECT_SPEC.md, docs/tasks/T-001-project-foundation.md를 모두 읽어라. 현재 브랜치가 codex/setup인지 확인하라.

docs/ENVIRONMENT.md와 .env.example을 설정의 단일 기준으로 사용하라. 키·토큰·비밀번호·DB URL·호스트·포트·CORS 주소·외부 API endpoint를 코드, Docker Compose, frontend 번들, 로그, 테스트 fixture에 하드코딩하지 마라. 비밀값은 backend에서만 읽어라.

작업 문서의 구현 범위와 완료 기준을 충족하는 코드만 작성해라. 실제 주식 데이터, 주문, Notion API, 인증, AWS 기능은 만들지 마라.

구현과 검증이 끝나면 docs/handoffs/CLAUDE_HANDOFF_TEMPLATE.md를 복사해 docs/handoffs/T-001-claude-handoff.md를 작성하라. 변경 파일, 실행 명령과 결과, 테스트·린트 결과, 가정과 미해결 항목을 빠짐없이 기록하라.

변경 사항은 논리적인 커밋으로 남기되, main과 dev에는 병합하거나 push하지 마라.
