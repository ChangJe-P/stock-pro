# Codex 검증 프롬프트 — T-002

코드를 수정하지 말고 T-002 구현 결과를 검증해줘.

다음 자료를 대조해라.

1. AGENTS.md
2. docs/PROJECT_SPEC.md
3. docs/ENVIRONMENT.md
4. skills/market-data-collector/SKILL.md
5. docs/tasks/T-002-daily-market-data.md
6. docs/handoffs/T-002-claude-handoff.md
7. dev 대비 `codex/data` Git diff
8. 실제 실행 가능한 backend 테스트와 기존 `/health` 테스트 결과

특히 아래를 독립적으로 확인해라.

- `pykrx` 하나만 사용하며 실제 주문·계좌·KIS·실시간·스케줄러·frontend 변경이 없는지
- 빈 값·다른 `MARKET_DATA_PROVIDER`에서 네트워크 요청을 보내지 않는지
- API 키·endpoint·로그인 정보·전체 DB URL을 코드·응답·로그·테스트에 노출하지 않는지
- 가격 저장·실행 기록·유일 제약·재수집 갱신·OHLC 검증·GET 조회가 작업 명세에 맞는지
- 테스트가 외부 네트워크에 의존하지 않는지와, 실제 공개 데이터 검증 여부를 인수인계와 구분했는지

아래 형식으로 결과를 작성해라.

- 완료 기준별 판정: 충족 / 부분 충족 / 미충족
- 발견 사항: P0, P1, P2 우선순위와 파일·근거
- 실제로 확인한 명령과 결과
- 확인하지 못한 항목
- 병합 가능 여부: 가능 / 수정 후 가능 / 불가

인수인계의 서술만으로 통과시키지 말고, 변경 파일과 실행 증거를 확인해라.
