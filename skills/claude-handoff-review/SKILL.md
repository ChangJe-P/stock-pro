---
name: claude-handoff-review
description: Verify a completed Jumong Claude Code task from its handoff, branch diff, and independently rerun evidence. Use when the user asks Codex to check a Claude Code completion; do not use to implement the task.
---

# Claude Code 인수인계 더블체크

Claude Code가 작업을 끝냈다고 보고하거나 사용자가 `T-XXX 검증해줘`라고 요청하면, `docs/handoffs/T-XXX-claude-handoff.md`를 시작점으로 Codex가 독립 검증한다.

## 확인 순서

1. 인수인계의 작업 ID·브랜치·커밋, 변경 파일 목록, 완료 기준별 근거, 실행 결과, 제한 사항을 읽는다.
2. `AGENTS.md`, 프로젝트 명세, 해당 작업 문서와 작업 문서가 지정한 Skill을 읽는다.
3. 기준 브랜치(`dev`가 기본) 대비 지정 브랜치 diff와 커밋을 대조한다. 제외 범위 밖 파일, 비밀값, 하드코딩, 문서와 다른 변경을 확인한다.
4. 가능한 테스트를 Codex 환경에서 독립 실행한다. mock 테스트, 실제 DB, 실제 외부 데이터 조회 결과는 반드시 구분한다. 실행할 수 없는 검증은 통과로 쓰지 않는다.
5. `docs/reviews/T-XXX-codex-review.md`에 완료 기준별 판정, P0~P2 발견 사항, 실제 실행 명령·결과, 미확인 항목, 병합 판단을 남긴다.

## 판정 원칙

- 인수인계의 설명은 증거가 아니다. 코드·Git diff·독립 실행 결과가 모두 맞을 때만 충족으로 판단한다.
- 환경·외부 제공처 문제로 확인하지 못한 실제 동작은 `부분 충족` 또는 `미확인`으로 기록한다.
- P0 또는 P1이 있으면 `수정 후 가능` 또는 `불가`로 판단한다. P2만 있으면 영향과 후속 시점을 함께 적고 병합 여부를 결정한다.
- Codex는 검증 중 서비스 구현 코드를 수정하지 않고, 검토 문서만 작성한다. push·병합은 사용자가 별도로 요청한 뒤에만 한다.
