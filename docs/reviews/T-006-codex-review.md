---
task_id: T-006
branch: codex/portfolio
base_branch: dev
reviewer: Codex
reviewed_commits: 5a3bbf8, 087ea96, f80aacd
verdict: approved_with_unverified_runtime
---

# T-006 Codex 재검토: 가상 포트폴리오와 읽기 전용 대시보드

## 결론

**승인 — 병합 가능.** 이전 P1은 `087ea96`에서 해결됐다. 0원·음수 체결 금액, 음수 수수료, 0 이하 최초 가상 현금은 더 이상 수익률 계산으로 들어가지 않고 `계산 불가`로 안전하게 처리된다. 0 나눗셈으로 `GET /`가 500이 되던 경로를 막는 여섯 개의 회귀 테스트도 추가됐다.

Codex 환경에는 Django 의존성과 Docker CLI가 없어 39개 Django 테스트 및 Compose 실행을 독립 재실행하지 못했다. 이는 P2 미확인 항목이며, Claude 인수인계의 결과와 Codex의 문법·diff·코드 검토를 구분해 기록한다. P0·P1은 없다.

## 대조 대상

- 작업 문서: `docs/tasks/T-006-portfolio-dashboard.md`
- 프로젝트 Skill: `skills/portfolio-dashboard/SKILL.md`
- 인수인계: `docs/handoffs/T-006-claude-handoff.md` (`5a3bbf8` 구현, `087ea96` P1 수정, `f80aacd` 인수인계 갱신)
- 비교 범위: `origin/dev...codex/portfolio`, 11개 파일, 1,123줄 추가·57줄 삭제

## 이전 P1 해결 확인

| 이전 위험 | 수정·검증 근거 | 판정 |
|---|---|---|
| `gross_amount_krw=0` 또는 `fee_krw=0`으로 종목 원가가 0이 되면 `_pct()`가 0으로 나누어 `GET /` 500 | `_is_complete()`가 `gross_amount_krw > 0`, `fee_krw >= 0`을 확인하고, 종목 원가 `<= 0`도 `REASON_INCOMPLETE_FILL`로 처리한다. | 해결(코드) |
| 음수 체결 금액·수수료가 평가에 섞임 | 같은 유효성 검사에서 계산 불가로 분기한다. | 해결(코드) |
| 최초 가상 현금이 0 이하라 총 수익률 분모가 성립하지 않음 | `initial_cash_krw > 0`을 확인하고 `REASON_INVALID_ACCOUNT_DATA`로 분기한다. 빈 보유 계좌도 포함한다. | 해결(코드) |
| 수정이 다시 깨져도 감지하지 못함 | `PortfolioInvalidDataTests` 6건이 0·음수 금액, 무효 최초 현금, `GET /`의 200·읽기 전용을 다룬다. | 해결(테스트 추가) |

## 완료 기준 판정

| 기준 | Codex 확인 근거 | 판정 |
|---|---|---|
| filled 주문만 합산 | `status="filled"` 필터와 pending·거절 제외 테스트를 확인했다. | 충족(코드) |
| 공통 최신 비조정 종가 | 종목별 비조정 거래일 교집합에서 모든 체결일 이후의 최대 날짜를 선택한다. | 충족(코드) |
| 금액·손익·수익률과 수수료 원가 | 정수 금액, `Decimal` 수익률, `gross + fee` 원가 및 무효 분모 안전 처리를 확인했다. | 충족(코드) |
| 가격·체결 데이터 부재 안전 처리 | 공통일 부재·누락·0/음수 체결값·무효 계좌값을 추정 없이 계산 불가로 처리한다. | 충족(코드) |
| 읽기 전용 `GET /` | 계산·최근 주문 조회만 하며 수집·체결·원장 쓰기를 추가하지 않았다. | 충족(코드) |
| Django static CSS·semantic HTML | Django 내장 staticfiles, app CSS 한 개, semantic table·caption·scope, 외부 JS/CSS/font 없음. | 충족(코드) |
| 반응형·색 이외 상태 | stacked table CSS와 이익·손실·변동 없음 텍스트가 있다. 실제 브라우저 재확인은 미확인이다. | 부분 충족 |
| 새 table·migration·API·form 없음 | model·migration·URL 변경과 새 공개 API·자동 수집·입력 form이 없다. | 충족(코드) |
| 테스트·인수인계 | 인수인계는 실행 환경을 구분했다. Claude의 39개 통과는 독립 재실행하지 못했다. | 부분 충족 |

## 독립 실행 결과

| 명령 | Codex 결과 |
|---|---|
| `python -m py_compile` (T-006 변경 Python 4개) | 통과(문법 확인) |
| `git diff --check origin/dev...HEAD` | 통과(공백 오류 없음) |
| `git show --check HEAD` | 통과 |

- 프로젝트 `.venv`에는 Django가 설치되어 있지 않아 `backend/manage.py check`는 `ModuleNotFoundError: No module named 'django'`로 독립 실행할 수 없었다.
- Codex shell에는 `docker` CLI가 없어 Compose web·PostgreSQL·브라우저를 독립 확인할 수 없었다.
- 따라서 인수인계의 `manage.py check`, migration dry-run, **39개 Django 테스트**, Docker DB·375px 브라우저 확인은 Claude가 기록한 증거이며 Codex 독립 통과가 아니다.
- 실제 외부 pykrx 네트워크는 T-006 계산 범위가 아니다. 코드 검토에서 pykrx·HTTP 수집을 시작하는 경로는 발견하지 못했다.

## 범위·보안 점검

- 변경은 읽기 전용 포트폴리오 계산, root template/view, Django 내장 staticfiles 설정, CSS, 테스트, 인수인계·기획·Skill·리뷰 문서로 한정된다.
- 실제 계좌·실제 주문·매도·자동매매·자동 수집·새 DB table/migration·새 공개 API·입력 form은 추가되지 않았다.
- diff에서 API 키·토큰·비밀번호·전체 연결 문자열, 외부 font/CSS/JS·새 패키지를 발견하지 못했다.

## P2 후속 항목

- `portfolio.empty=True`와 `valuation_available=False`가 동시에 되는 무효 최초 현금 계좌는 template의 빈 보유 분기가 먼저 표시된다. 요약 카드는 `계산 불가`이지만 상단 안내는 계좌 오류 대신 보유 종목 없음을 말한다. 데이터 안전성에는 영향이 없으므로 병합은 가능하며, 다음 대시보드 문구 개선 때 분기 순서를 정리한다.
- Docker Compose `web` 컨테이너의 실제 HTTP·CSS 제공은 Docker CLI가 가능한 환경에서 한 번 재확인한다.

## 다음 행동

사용자가 승인하면 `codex/portfolio`를 원격에 push하고 T-006의 `dev` 병합 요청을 준비한다. P2는 별도 UI 문구 작업에서 처리한다.
