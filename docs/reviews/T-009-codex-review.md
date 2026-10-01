---
task_id: T-009
reviewer: Codex
reviewed_at: 2026-10-01
base: dev@1516a52
branch: codex/ui@719ae46
decision: 수정 후 가능
---

# T-009 Codex 검증 결과

## 결론

**수정 후 가능**. Django UI 구조, 기존 읽기 전용 동작, Docker 기반 자동 테스트는 확인됐으나, T-009 완료 기준 4의 양수 부호(`+`)가 실제 화면에 없다. P1 한 건을 수정한 뒤 재검증한다.

## 증거 범위

- 인수인계: `docs/handoffs/T-009-claude-handoff.md` (`719ae46`)
- 구현 커밋: `176acce`
- 비교 기준: `dev@1516a52...codex/ui@719ae46`
- Codex 독립 실행(Docker `web`):

```text
docker compose exec web python manage.py test trading
Ran 64 tests ... OK

docker compose exec web python manage.py check
System check identified no issues (0 silenced).

docker compose exec web python manage.py makemigrations --check --dry-run
No changes detected
```

- Codex 브라우저 확인(새 `http://localhost:3000/`, `http://localhost:3000/setup` 탭): 공통 navigation, 가상 학습 투자 안내, 실제 평가 기준·계좌·보유·최근 주문, `/setup` 3단계 안내가 렌더링됨을 확인했다.

## 완료 기준 대조

| 기준 | 판정 | Codex 확인 근거 |
|---|---|---|
| 1. 가상 학습 장부와 실제 두 화면 navigation | 충족 | 두 template의 `site-nav`, 브라우저에서 `/`·`/setup` 링크 확인 |
| 2. 실제 계좌·평가·보유·최근 주문만 재배치 | 충족 | `dashboard.html`의 기존 context와 `.dashboard-grid`; view/service/model 변경 없음 |
| 3. `/setup` 기존 기능 유지 + 3단계 설명 | 충족 | 기존 form action·CSRF·조건 분기 유지, 브라우저에서 흐름 안내 확인 |
| 4. 이익/상승 빨강, 손실/하락 파랑 + 상태 텍스트·`+`/`-` 부호 | **부분 충족 (P1)** | CSS 색상과 `이익`/`손실` 텍스트는 있으나, 실제 양수 값이 `29`, `0.97%`로 렌더링되어 `+`가 없음 |
| 5. 1440/1024/768/375 반응형·모바일 표 | 부분 충족 | CSS breakpoint와 `data-label`은 확인. Claude의 1440/375 확인은 인수인계 근거이며, Codex는 1024/768 실제 viewport 캡처를 재실행하지 못함 |
| 6. Template/static CSS/semantic HTML만 사용 | 충족 | diff에 JavaScript·외부 리소스·의존성 추가 없음 |
| 7. 기존 계약과 읽기 전용 보장 | 충족 | view/service/model/migration/API/Compose diff 없음, 독립 64 테스트 통과 |
| 8. 자동·수동 결과를 구분해 기록 | 부분 충족 | 자동 결과는 Codex가 재실행. 1024/768 및 손실 상태의 브라우저 직접 확인은 인수인계에서도 미수행 |

## 발견 사항

### P1 — 양수 손익과 수익률의 `+` 부호가 없다

- 위치: `backend/templates/trading/dashboard.html`의 총 평가손익·총 수익률·보유 종목 평가손익·수익률 출력
- 증거: Codex가 새 대시보드 탭에서 총 평가손익 `29`, 총 수익률 `0.00%`, 종목 평가손익 `29 이익`, 종목 수익률 `0.97%`를 확인했다. 양수 앞에 `+`가 없다.
- 영향: T-009에서 명시한 색상 이외의 부호 표현이 양수 상태에 적용되지 않는다. 색각이나 빠른 수치 비교 상황에서 상승/이익 의미가 덜 명확하다.
- 수정 요청: 양수 상태에만 template에서 `+`를 붙이고, 음수는 기존 음수 값의 `-`를 유지하며, 중립은 부호를 붙이지 않는다. 양수 총 손익·수익률과 종목 손익·수익률에 대한 render 회귀 테스트를 추가한다. 계산 서비스나 context 계약은 바꾸지 않는다.

### P2 — 중간 viewport와 손실 상태의 실제 브라우저 확인이 없다

- 1024px·768px 및 손실(파랑) 상태는 CSS 규칙/코드만 확인됐다.
- P1 수정 뒤 1024px·768px·손실 데이터가 있는 화면을 브라우저로 확인하고, 자동 테스트와 별도로 인수인계에 남긴다.

## 범위·안전성 확인

- 예상된 Django Template, static CSS, 테스트, 인수인계 및 기존 기획/Skill/프롬프트 파일 외 변경은 없다.
- `git diff --check dev...HEAD`는 오류가 없었다.
- 새 외부 URL·script·CDN·frontend dependency·환경변수·비밀값은 T-009 diff에서 확인되지 않았다.
- Claude가 보고한 먼저 실패한 render 테스트 실행은 현재 Git 상태만으로 독립 재현할 수 없으므로, 이 검토에서는 인수인계 주장으로만 기록한다. 현재 64개 테스트의 통과는 Codex가 독립 확인했다.

## 병합 판단

P1 수정과 재검증 전에는 push·PR·`dev` 병합을 준비하지 않는다.
