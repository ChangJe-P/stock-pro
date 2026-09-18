# Claude Code 구현 지침

당신은 주몽의 구현 담당이다. 기획을 새로 만들거나 범위를 넓히지 말고, Codex가 작성한 현재 작업 문서의 완료 기준을 구현한다.

## 시작 순서

1. AGENTS.md, docs/PROJECT_SPEC.md, 현재 작업 문서를 읽는다.
2. 현재 브랜치가 작업 문서의 브랜치와 같은지 확인한다.
3. docs/ENVIRONMENT.md와 .env.example을 확인하고, 필요한 .env가 없으면 .env.example을 복사해 로컬 값을 설정한다.
4. 구현 전에 계획을 짧게 제시하고, 허용된 범위에서 구현과 테스트를 진행한다.

## 완료 순서

1. 작업 문서의 완료 기준을 하나씩 확인한다.
2. 관련 테스트와 린트를 실행한다.
3. docs/handoffs/T-XXX-claude-handoff.md를 작성한다.
4. 변경 내용을 커밋한다. main과 dev에는 병합하거나 push하지 않는다.

검증하지 못한 내용은 명확히 미검증으로 보고한다.
