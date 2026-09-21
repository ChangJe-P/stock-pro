# Claude Code 전달 프롬프트 — T-003

아래 프로젝트에서 T-003을 구현해줘.

시작 전에 다음 파일을 모두 읽어라.

1. AGENTS.md
2. docs/PROJECT_SPEC.md
3. docs/ENVIRONMENT.md
4. docs/tasks/T-003-virtual-account-ledger.md
5. skills/virtual-trading-account/SKILL.md

현재 브랜치가 codex/trading인지 확인하라. 브랜치가 다르거나 T-002가 포함돼 있지 않으면 코드를 수정하지 말고 Codex에 보고하라.

작업 문서의 범위와 완료 기준만 구현하라. 단일 로컬 사용자용 가상계좌, 최초 가상 현금, 정책 스냅샷, 추가만 가능한 현금 원장, 초기화·조회 API만 만든다. 최초 가상 현금은 실제 돈이 아니며, 모든 금액은 KRW 정수로 다룬다.

기존 backend 설정 계층과 PostgreSQL 접근 방식을 재사용하라. 시작 현금·수수료율·세금율·슬리피지·정책 버전은 설정 계층에서만 읽는다. 서비스 코드·테스트 fixture에 값을 직접 적지 말고, 계좌 최초 생성 시 설정 스냅샷을 DB에 저장하라. 반복 초기화는 기존 계좌와 원장을 재설정하거나 새 opening_balance 행을 추가하면 안 된다.

실제 증권 계좌, 계좌번호, 로그인, 실주문, 자동매매, 주문 생성·취소, 다음 거래일 체결, 포지션, 손익 계산, 시장 데이터 수집 변경, frontend, Notion 연동, 다중 사용자, 정책 수정·원장 수정 또는 삭제 API는 만들지 마라. 제공처 추상화, 주문 엔진, 원장 편집 기능도 만들지 마라.

자동 테스트는 외부 시장 데이터·실제 증권사·실제 계좌에 요청을 보내면 안 된다. 기존 health와 T-002 테스트를 포함해 가능한 전체 backend 테스트를 실행하라. 실제 PostgreSQL을 확인했다면 명령·결과를 별도 증거로 남기고, 확인하지 못했으면 통과라고 쓰지 마라.

구현과 검증이 끝나면 docs/handoffs/CLAUDE_HANDOFF_TEMPLATE.md를 복사해 docs/handoffs/T-003-claude-handoff.md를 작성하라. 변경 파일, 완료 기준별 근거, 실행 명령·결과, 테스트·린트 결과, 가정·제한·미해결 항목을 빠짐없이 기록하라.

변경 사항은 논리적인 커밋으로 남기되 push하거나 main·dev에 병합하지 마라.
