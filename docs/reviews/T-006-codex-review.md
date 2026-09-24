---
task_id: T-006
branch: codex/portfolio
base_branch: dev
reviewer: Codex
reviewed_commits: 5a3bbf8, 1e53371
verdict: changes_requested
---

# T-006 Codex 검토: 가상 포트폴리오와 읽기 전용 대시보드

## 결론

**수정 요청 — 현재 병합하면 안 됨.** 계산의 정상 경로, 읽기 전용 범위, static CSS와 반응형 구조는 작업 명세에 대체로 맞는다. 다만 비정상 `filled` 주문의 금액이 0원 또는 음수인 경우를 유효한 체결로 통과시켜, `GET /`가 `ZeroDivisionError`로 500이 될 수 있는 P1이 있다.

T-006은 체결 금액·수수료가 비어 있거나 **유효하지 않으면** 추정·0 보정 대신 `계산 불가`로 처리해야 한다. 따라서 P1 수정과 회귀 테스트를 확인한 뒤에만 재검증·병합 판단한다.

## 대조 대상

- 작업 문서: `docs/tasks/T-006-portfolio-dashboard.md`
- 프로젝트 Skill: `skills/portfolio-dashboard/SKILL.md`
- 인수인계: `docs/handoffs/T-006-claude-handoff.md` (`5a3bbf8` 구현, `1e53371` 인수인계)
- 비교 범위: `origin/dev...codex/portfolio`, 10개 파일, 952줄 추가·57줄 삭제

## 완료 기준 판정

| 기준 | Codex 확인 근거 | 판정 |
|---|---|---|
| filled 주문만 합산 | `portfolio.compute_portfolio()`가 `status="filled"`만 읽고, pending·거절 테스트가 있다. | 충족(코드) |
| 공통 최신 비조정 종가 | `_pick_valuation_date()`가 종목별 비조정 거래일 교집합 중 마지막 체결일 이후의 최대 날짜를 선택한다. | 충족(코드) |
| 금액·수익률·수수료 원가 | 정상 값에서 `gross + fee`, 정수 금액, `Decimal` 수익률 공식은 맞다. 단 P1 경계값 때문에 전체 기준은 미충족이다. | **미충족(P1)** |
| 공통일 부재·불완전 체결 안전 처리 | `None` 필드는 안내로 처리한다. 단 0·음수 금액은 유효하지 않은 값인데 처리하지 못한다. | **미충족(P1)** |
| 읽기 전용 `GET /` | view는 계산·최근 주문 조회만 하고 수집·체결·원장 쓰기 호출을 추가하지 않았다. | 충족(코드) |
| Django static CSS·semantic HTML | Django 내장 staticfiles와 app CSS 한 개, semantic table·caption·scope, 외부 JS/CSS/font 없음. | 충족(코드) |
| 반응형·색 이외 상태 | 640px 이하 stacked table과 이익·손실·변동 없음 텍스트 상태를 확인했다. 실제 브라우저 재확인은 아래 제한으로 미확인이다. | 부분 충족 |
| 새 테이블·migration·API·form 없음 | model·migration·URL 변경 없고, 새 공개 API·자동 수집·입력 form을 추가하지 않았다. | 충족(코드) |
| 테스트·인수인계 | 인수인계는 변경 파일·명령·제한을 구분했다. Claude의 33개 통과 주장은 독립 재실행하지 못했다. | 부분 충족 |

## P1 발견 사항

### [P1] 0원 또는 음수 체결 금액을 유효한 체결로 취급해 대시보드가 500이 됨

- 위치: `backend/trading/portfolio.py`의 `_is_complete()`와 `_pct()` 호출 경로
- 원인: `_is_complete()`는 `gross_amount_krw`와 `fee_krw`가 `None`이 아닌지만 확인한다. `gross_amount_krw=0`, `fee_krw=0`인 filled 주문은 통과하고, 종목 `cost_krw`가 0이 된다. 이후 `_pct(pnl, h["cost_krw"])`가 0으로 나누어 예외를 낸다.
- 영향: 기존 DB schema의 `gross_amount_krw`, `fee_krw`에는 양수·음수 CHECK 제약이 없다. 따라서 과거 데이터·수동 DB 입력·향후 버그로 만들어진 한 행이 읽기 전용 대시보드 전체를 500으로 만들 수 있다.
- 명세 위반: T-006은 체결 수량·체결 금액·수수료·체결일이 비어 있거나 **유효하지 않으면** 전체 평가를 `계산 불가`로 표시하고 0 보정을 금지한다.
- 수정 방향: `gross_amount_krw > 0`, `fee_krw >= 0`과 계산된 종목 원가 `> 0`을 유효성 조건으로 확인한다. 조건을 만족하지 않으면 기존 `REASON_INCOMPLETE_FILL` 또는 의미가 분명한 새 안전 사유로 `valuation_available=False`를 반환한다. `initial_cash_krw <= 0`도 수익률 분모가 되므로 동일하게 안전 처리한다.
- 회귀 테스트: 금액 0·음수 또는 총 원가 0인 `filled` 주문에서 `compute_portfolio()`과 `GET /`가 예외 없이 200/`계산 불가`를 반환하고, 외부 수집·주문·원장 쓰기가 없음을 추가로 검증한다.

## 독립 실행 결과

### Git·정적 점검

| 명령 | Codex 결과 |
|---|---|
| `git diff --check origin/dev...HEAD` | 통과(공백 오류 없음) |
| `git show --check HEAD` | 통과 |
| `python -m py_compile` (T-006 변경 Python 4개) | 통과(문법 확인) |

변경 파일을 직접 검토했다. 실제 계좌·실제 주문·자동 수집·pykrx/HTTP 호출, 새 패키지, 외부 font/CSS/JS, 비밀값·전체 연결 문자열은 diff에서 발견하지 못했다.

### Django 테스트·실제 DB·브라우저

Codex 환경에서는 독립 재실행하지 못했다.

- 프로젝트 `.venv`에 Django가 설치되어 있지 않아 `backend/manage.py check`는 `ModuleNotFoundError: No module named 'django'`로 실행 불가였다.
- Codex shell에는 `docker` CLI가 없어 Compose `web`·PostgreSQL 검증을 실행할 수 없었다.
- 따라서 인수인계의 `manage.py check`, migration dry-run, 33개 Django 테스트, Docker DB·375px 브라우저 확인은 **Claude가 기록한 증거**로만 보관하며 Codex의 독립 통과로 표현하지 않는다.
- 실제 외부 pykrx 네트워크 호출은 T-006 계산 범위가 아니며, Codex 코드 검토에서도 이를 시작하는 경로를 발견하지 못했다.

## 범위·보안 점검

- `git diff --check origin/dev...HEAD` 통과.
- 변경은 포트폴리오 읽기 모듈, root template/view, Django 내장 staticfiles 설정, CSS, 테스트, 인수인계·기획 문서·Skill로 한정된다.
- `VirtualBuyOrder`·`DailyPrice`를 읽기만 하며 새 DB table·migration·공개 API·주문 form·매도·자동 수집은 없다.
- `STATIC_URL = "static/"`은 Django 내부 정적 경로 설정이며 키·호스트·포트·외부 endpoint가 아니다. 비밀값·실계좌 정보·토큰은 추가되지 않았다.

## 다음 행동

1. Claude Code가 P1 유효성 검증과 회귀 테스트를 `codex/portfolio`에서 수정·커밋한다. push·PR·병합은 하지 않는다.
2. Claude는 인수인계의 변경 파일 목록·테스트 결과·제한 사항을 갱신한다.
3. 사용자가 다시 검증을 요청하면 Codex가 수정 diff와 새 테스트 결과를 대조해 병합 가능 여부를 판정한다.
