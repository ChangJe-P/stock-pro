# 주몽 (Jumong)

국내 주식 초보자를 위한 가상투자·주식 학습 웹 프로젝트입니다. 실제 시장 일봉 데이터를 사용하되 가상 현금만 사용하며, 실제 계좌와 주문은 연결하지 않습니다.

## 현재 상태

T-001 Docker 기반 개발 환경 구성이 Claude Code 구현 대기 상태입니다.

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
