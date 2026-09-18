# Claude Code 전달 프롬프트 — T-002

아래 프로젝트에서 T-002를 구현해줘.

시작 전에 다음 파일을 모두 읽어라.

1. AGENTS.md
2. CLAUDE.md
3. docs/PROJECT_SPEC.md
4. docs/ENVIRONMENT.md
5. docs/tasks/T-002-daily-market-data.md
6. skills/market-data-collector/SKILL.md

현재 브랜치가 `codex/data`인지 확인하라. 브랜치가 다르거나 T-001 기반 환경이 없다면 코드를 수정하지 말고 Codex에 보고하라.

작업 문서의 범위와 완료 기준만 구현하라. `pykrx` 한 가지로 일봉 OHLCV를 수집하고 PostgreSQL에 저장·조회한다. 실제 증권 계좌, KIS·다른 제공처, 실제 주문, 자동매매, 실시간 시세, 전 종목 일괄 수집, 스케줄러, frontend, Notion 기능은 만들지 마라. 제공처 전환을 위한 인터페이스·팩토리도 만들지 마라.

`.env.example`과 docs/ENVIRONMENT.md를 설정의 단일 기준으로 사용하라. `MARKET_DATA_PROVIDER=pykrx`일 때만 수집을 허용하고, 빈 값 또는 다른 값이면 외부 요청 없이 안전한 설정 오류를 반환하라. 이 작업에 필요 없는 키·비밀번호·endpoint·요청 제한 변수를 읽거나 로그에 남기지 마라. 직접 HTTP 요청을 만들지 말고 `pykrx` 패키지 호출만 사용하라.

자동 테스트는 반드시 `pykrx` 호출을 mock 처리해 실제 네트워크 요청을 보내지 마라. 실제 공개 데이터 호출을 수동으로 검증했다면 그 명령과 결과를 인수인계에 분리해 기록하고, 실패하거나 실행하지 못했다면 그대로 기록하라.

구현과 검증이 끝나면 docs/handoffs/CLAUDE_HANDOFF_TEMPLATE.md를 복사해 docs/handoffs/T-002-claude-handoff.md를 작성하라. 변경 파일, 완료 기준별 근거, 실행 명령·결과, 테스트·린트 결과, 가정·제한·미해결 항목을 빠짐없이 기록하라.

변경 사항은 논리적인 커밋으로 남기되 push하거나 main·dev에 병합하지 마라.
