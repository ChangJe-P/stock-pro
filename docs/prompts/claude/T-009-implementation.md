# Claude Code 구현 요청: T-009 금융 정보 중심 Django 화면 개선

## 시작 전 필독

아래 파일을 순서대로 읽고, 충돌하면 T-009 작업 문서의 범위와 완료 기준을 따른다.

1. `AGENTS.md`
2. `docs/PROJECT_SPEC.md`
3. `docs/UI-DESIGN-REFERENCE.md`
4. `docs/tasks/T-006-portfolio-dashboard.md`
5. `docs/tasks/T-007-onboarding-data-setup.md`
6. `docs/tasks/T-009-finance-ui-refresh.md`
7. `skills/portfolio-dashboard/SKILL.md`
8. `skills/onboarding-data-setup/SKILL.md`
9. `skills/django-finance-ui/SKILL.md`
10. `C:\Users\박창제\.claude\skills\ui-ux-pro-max\SKILL.md`
11. `C:\Users\박창제\.claude\skills\frontend-design\SKILL.md`

현재 브랜치가 `codex/ui`인지 먼저 확인해줘. 화면 구성이나 실제 데이터의 표시 기준을 잘 이해하지 못했거나 문서에 없는 결정을 해야 한다면, 추측하지 말고 **Codex에 먼저 질문해줘.**

## 구현 요청

T-009 작업 문서의 완료 기준을 만족하도록 `/`와 `/setup`의 Django Template 및 static CSS만 개선해줘.

- 알파스퀘어의 금융 화면 느낌은 정보 우선순위·밀도·밝은 패널·얇은 구분선·절제된 빨간 강조색만 참고해. 상표, 이미지, 문구, 아이콘, 화면 배치를 복제하지 마.
- 실제 context에 이미 있는 계좌 요약, 평가 기준, 보유 종목, 최근 주문, 계좌 시작, 일봉 수집·수집 결과만 표시해. 차트·검색·관심종목·매수/매도·AI·실시간 시세·가짜 CTA는 만들지 마.
- 국내 주식 화면 관례대로 상승·이익은 빨강, 하락·손실은 파랑으로 표시해. 색상만 사용하지 말고 `이익`/`손실`/`변동 없음`과 `+`/`-` 부호를 함께 유지하거나 추가해.
- 1440px에서는 실제 평가 기준·계좌/보유 종목·최근 주문을 비교할 수 있는 금융 화면 구성으로 만들고, 1024px·768px·375px에서는 한 열 또는 읽기 쉬운 card형 표로 전환해. 모바일에서 핵심 값을 가로 스크롤에 숨기지 마.
- `/setup`은 가상계좌 시작 → 일봉 수동 수집 → 대시보드 확인의 실제 흐름을 보여 주되, 기존 form action·CSRF·오류·PRG·수집 결과 조건은 바꾸지 마.
- `views.py`, 서비스, models, migrations, API, Docker Compose, 환경변수, 의존성은 변경하지 마. JavaScript, CDN, 외부 폰트·이미지·icon/CSS library, 새 frontend framework도 추가하지 마.

## 테스트와 인수인계

- 화면 변경 전에 `backend/trading/tests.py`의 최소 render 계약 테스트를 먼저 작성하고, 새 semantic UI 구조가 없어 실패하는 것을 확인해. 이후 template/CSS를 최소 변경해 통과시켜.
- 기존 GET 읽기 전용, CSRF, PRG, 수집 입력 검증, 계좌 반복 초기화, JSON API 테스트를 삭제·약화하지 마.
- `docker compose exec web python manage.py test trading`, `check`, `makemigrations --check --dry-run`을 실행해. Docker를 실행할 수 없으면 실제 실행 환경과 결과를 정확히 구분해.
- `/`와 `/setup`을 1440px·1024px·768px·375px에서 확인하되, 화면 검증을 위해 계좌 생성·일봉 수집·주문 체결을 새로 시작하지 마.
- `docs/handoffs/T-009-claude-handoff.md`에 변경 파일, 완료 기준별 위치, 실패 후 통과한 테스트, 자동/수동 화면 확인 구분, 제한 사항을 기록해.
- 논리적인 커밋을 만들되 **push, PR 생성, 병합은 하지 마.** 완료 뒤 커밋 해시와 인수인계 경로를 알려줘.
