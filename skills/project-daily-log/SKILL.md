---
name: project-daily-log
description: Record verified Jumong project progress in both Notion and the user's Obsidian project vault with one timestamped title. Use when the user asks to summarize a day, session, progress, review, or next actions for Jumong; do not use for code implementation or unrelated notes.
---

# 주몽 일일 기록

## 목적

주몽 프로젝트의 결정, 구현, 검증, 다음 행동을 Notion과 Obsidian에 같은 제목으로 남긴다.

## 기록 전 확인

- 현재 한국 표준시로 `yyyy-MM-dd_HH_mm` 형식의 제목과 파일명을 만든다.
- 현재 대화, Git 상태와 커밋, 작업 문서, Claude 인수인계, 실제 실행·테스트 결과에서 확인된 사실만 수집한다.
- 인수인계의 주장과 Codex가 직접 실행한 결과를 구분한다. 실행하지 못한 항목은 통과라고 쓰지 않는다.
- API 키, 비밀번호, 토큰, 전체 DB 연결 문자열, 실제 계좌 정보는 기록하지 않는다.

## Obsidian

- 경로는 `C:\Users\박창제\Documents\Obsidian Vault\프로젝트\<timestamp>.md`를 사용한다.
- YAML frontmatter에 `created`, `project`, `tags`를 넣고, 본문에는 아래 순서로 기록한다.
  1. 오늘의 목표
  2. 결정 사항
  3. 구현·변경 사항
  4. 검증 결과
  5. 알려진 제한 또는 후속 정비
  6. 다음 행동
- 파일이 생성됐는지 확인하고, 같은 이름이 이미 있으면 덮어쓰지 말고 사용자에게 확인한다.

## Notion

- Notion MCP 연결을 먼저 확인하고, `주몽 프로젝트 기록` 페이지를 검색한다.
- 페이지가 없으면 한 번만 상위 페이지로 만든다. 이미 있으면 새 상위 페이지나 데이터베이스를 만들지 않는다.
- 상위 페이지의 하위 페이지로 `<timestamp>` 제목의 일지를 만든다.
- Notion API 토큰을 프로젝트 `.env`에 추가하지 않는다. 이 기록은 MCP 연결로만 작성한다.

## 완료 보고

- Obsidian 절대 경로와 Notion 페이지 링크를 알려 준다.
- 이번 기록의 증거 범위와 다음 행동을 한 줄로 요약한다.
