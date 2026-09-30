# Claude Code 구현 요청: T-008 KRX 인증 기반 pykrx 일봉 수집 설정

## 시작 전 필독

아래 파일을 순서대로 읽고, 충돌하면 T-008 작업 문서의 범위와 완료 기준을 따른다.

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/ENVIRONMENT.md`
4. `docs/tasks/T-002-daily-market-data.md`
5. `docs/tasks/T-007-onboarding-data-setup.md`
6. `docs/tasks/T-008-krx-authenticated-market-data.md`
7. `skills/market-data-collector/SKILL.md`
8. `skills/onboarding-data-setup/SKILL.md`
9. `skills/krx-authenticated-market-data/SKILL.md`

현재 브랜치가 `codex/krx-auth`인지 먼저 확인해줘. 실제 KRX 아이디·비밀번호를 요청하거나, 채팅·문서·코드·테스트·로그에 기록하지 마. 인증 방식이나 pykrx 내부 동작이 작업 문서로 해결되지 않는다면 추측해 우회하지 말고 Codex에 질문해줘.

## 구현 요청

T-008 작업 문서의 완료 기준을 만족하도록, 현재 pykrx가 요구하는 KRX 인증 정보를 로컬 Docker `web` 컨테이너에만 안전하게 적용해줘.

- `.env.example`과 `docs/ENVIRONMENT.md`에 `KRX_ID`, `KRX_PW`의 이름·빈 값·안전한 로컬 사용 규칙만 추가해. 실제 값·가짜처럼 보이는 값·전체 `.env` 예시는 넣지 마.
- `backend/jumong/settings.py`에서만 KRX 환경변수를 읽고, `trading.config`에서 provider와 두 값의 존재 여부를 최소로 판정해. 값, 길이, 마스킹 값도 반환·표시·로그에 넣지 마.
- provider가 아니거나 두 값 중 하나라도 비어 있으면 pykrx import·로그인·외부 요청 없이 503 안전 오류로 끝내. `/setup`은 기존 오류 표시를 재사용하고 새 form·API·DB 구조를 만들지 마.
- 기존 `market_data.collect_daily_prices()`·`fetch_ohlcv()`·품질 검증·upsert·수집 기록을 재사용해. `adjusted=False`, 한 종목·기간, POST 수동 수집, PRG, CSRF, GET 읽기 전용을 유지해.
- 최신 pykrx는 import/로그인 중 로그인 ID를 표준 출력에 쓸 수 있다. pykrx import와 호출을 작은 동기화된 비노출 가드로 감싸 표준 출력·표준 오류·예외 원문이 logger·HTTP 응답·DB에 도달하지 않게 해. 전역 표준 스트림 가드의 단일 로컬 web 프로세스 전제를 `ponytail:` 한국어 주석으로 남겨.
- 직접 HTTP, 재시도·스케줄러·큐, 브라우저 로그인, 쿠키/세션 파일, 다른 제공처·추상화, pykrx 버전 교체·포크, secret manager, migration, UI 재설계는 추가하지 마.

## 테스트와 인수인계

- 자동 테스트에서 실제 KRX 네트워크·실제 자격증명을 사용하지 마. pykrx를 mock해 provider/자격증명 누락 시 외부 import·호출 없음과 503을 검증해.
- fake ID·fake password·fake upstream 출력/예외가 HTTP 응답, 애플리케이션 로그 캡처, `MarketDataCollectionRun`에 포함되지 않음을 검증해.
- 완전한 설정에서 mock된 기존 수집·저장·실행 기록과 `/setup` 수집 POST의 기존 422·CSRF·PRG·GET 읽기 전용 규칙이 유지되는지 검증해.
- `python manage.py check`, `python manage.py makemigrations --check --dry-run`, 전체 Django 테스트를 실행해. Docker가 가능하면 `web` 재생성 뒤 설정 누락 503을 확인해. 실제 KRX 성공 수집은 사용자가 로컬 `.env`에 값을 입력한 경우에만 수동으로 확인하고, 실행하지 못했거나 실패하면 그대로 제한 사항으로 남겨.
- `docs/handoffs/T-008-claude-handoff.md`에 변경 파일, 완료 기준별 구현 위치, 실행 명령과 결과, mock/Compose/실제 네트워크 구분, 가정·제한을 기록해. 실제 자격증명, 표준 출력 원문, 전체 로그는 넣지 마.
- 논리적인 커밋을 만들되 **push, PR 생성, 병합은 하지 마.** 완료 뒤 커밋 해시와 인수인계 경로를 알려줘.
