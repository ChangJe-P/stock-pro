---
task_id: T-009
reviewer: Codex
reviewed_at: 2026-10-01
base: dev@1516a52
branch: codex/ui@f06affb
decision: 병합 가능
---

# T-009 Codex 검토 기록

## 결론

최초 검토에서는 양수 손익·수익률의 `+` 부호 누락을 P1으로 발견했다. Claude가 `9c1e8dd`에서 이를 수정했고, 아래 **최종 재검증**에서 독립 실행과 실제 렌더링으로 해결을 확인했다.

## 최초 검토 증거 범위 (수정 전)

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

## 최종 재검증 (수정 후)

### 독립 실행 결과

```text
docker compose exec web python manage.py test trading
Ran 67 tests ... OK

docker compose exec web python manage.py check
System check identified no issues (0 silenced).

docker compose exec web python manage.py makemigrations --check --dry-run
No changes detected
```

- `SignRenderTests`는 양수 `+20000`·`+20.00%`·`+2.00%`, 음수 `-20000`·`-20.00%`·`-2.00%`, 중립 무부호를 확인한다.
- 새 브라우저 탭의 실제 양수 데이터는 `+29`, `+0.00%`, `+0.97%`, `이익`으로 렌더링됐다.
- 손실 상태 수동 확인 때 임시로 바꿨다는 일봉 종가(`005930`, `2024-01-03`)는 Codex 읽기 전용 조회에서 `1011`로 원복된 것을 확인했다.

### 최종 완료 기준 판정

| 기준 | 최종 판정 | 근거 |
|---|---|---|
| 1. 가상 학습 장부와 실제 두 화면 navigation | 충족 | template과 새 브라우저 탭의 `/`·`/setup` 링크 |
| 2. 실제 데이터만 재배치 | 충족 | 기존 context만 쓰는 `.dashboard-grid`, view/service/model 변경 없음 |
| 3. `/setup` 기존 기능 유지 + 3단계 설명 | 충족 | form action·CSRF·조건 분기 유지, 흐름 안내 렌더링 확인 |
| 4. 색·상태 텍스트·`+`/`-` 부호 | 충족 | CSS 색상 매핑, `SignRenderTests`, 실제 양수 렌더링 |
| 5. 반응형·모바일 표 | 충족 | 1025px/768px/440px breakpoint와 `data-label`; Claude의 수동 확인은 인수인계에 분리 기록 |
| 6. Template/static CSS/semantic만 사용 | 충족 | 새 JavaScript·외부 리소스·의존성 없음 |
| 7. 기존 계약과 읽기 전용 보장 | 충족 | 허용 범위 diff와 독립 67개 테스트 |
| 8. 자동·수동 결과 분리 | 충족 | 인수인계와 이 검토에서 분리 기록 |

### P2 참고 사항

손실 색상 확인을 위해 개발 DB의 일봉 종가 한 건을 일시 변경·원복한 절차는 남은 데이터 변경 없이 끝났고, 병합을 막지 않는다. 이후 화면 상태 검증은 Django 테스트 DB 또는 별도 검증 데이터베이스에서 수행한다.

## 병합 판단

P0/P1은 없다. `codex/ui`를 원격에 push하고 T-009의 `dev` 병합 요청을 준비할 수 있다. 실제 push·PR 생성·병합은 사용자의 별도 요청 뒤에만 한다.
