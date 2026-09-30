---
task_id: T-007
branch: codex/onboarding
base_branch: dev
reviewer: Codex
reviewed_commits: b97e6f1, b59bdd0
review_date: 2026-09-30
verdict: changes_required
---

# T-007 Codex 검토: 가상투자 시작과 일봉 수동 준비 화면

## 결론

**수정 후 병합 가능.** 계좌 최초 생성, 일봉 수동 수집, CSRF, 입력 검증, PRG, 결과 표시와 기존 API 보존은 확인했다. 하지만 DB 오류가 `/setup`의 세 경로에서 500으로 전파되고 개발 환경에서는 내부 예외 문자열까지 HTML에 노출된다. 이는 완료 기준 8의 안전한 DB 오류 안내를 충족하지 못하는 **P1**이다.

실제 pykrx 네트워크 수집 성공은 이번에도 검증하지 않았다. mock 테스트와 Compose의 저장된 실행 기록 표시는 통과했지만, 외부 제공처 성공은 `미확인`으로 남긴다.

## 대조 대상

- 작업 문서: `docs/tasks/T-007-onboarding-data-setup.md`
- 프로젝트 Skill: `skills/onboarding-data-setup/SKILL.md`
- 인수인계: `docs/handoffs/T-007-claude-handoff.md`
- 비교 범위: `dev...codex/onboarding`, 9개 파일, 641줄 추가·3줄 삭제
- 구현 커밋: `b97e6f1`
- 인수인계 커밋: `b59bdd0`

## P1 — DB 오류가 500과 내부 예외 노출로 이어짐

`backend/trading/views.py`의 `setup_account_initialize()`(247행)와 `setup_market_data_collect()`(262행)는 `ApiError`만 처리한다. 따라서 기존 서비스가 PostgreSQL `OperationalError` 같은 `DatabaseError`를 내면 안전한 HTML 안내로 전환되지 않는다. 또한 `setup()`(231행)의 `MarketDataCollectionRun` 조회(238행)는 `_setup_context()` 밖에 있어 DB 오류를 처리하지 않는다.

실행 중인 Compose `web` 컨테이너에서 `OperationalError("db outage secret-like-detail")`를 mock해 확인한 결과는 다음과 같다.

| 경로 | Codex 결과 | 위험 |
|---|---|---|
| `POST /setup/account/initialize` | 500, mock 예외 문자열이 HTML에 포함 | 계좌 초기화 DB 장애가 안전하게 안내되지 않음 |
| `POST /setup/market-data/collect` | 500, mock 예외 문자열이 HTML에 포함 | 수집 실행 기록·가격 저장 DB 장애가 안전하게 안내되지 않음 |
| `GET /setup?collection_run=x` | 500, mock 예외 문자열이 HTML에 포함 | 저장된 수집 결과 조회 DB 장애가 안전하게 안내되지 않음 |

현재 `DEBUG=True`인 개발 Compose에서도 재현됐다. 실제 DB 예외에는 호스트·연결 정보가 포함될 수 있으므로, 예외 원문을 화면에 보내면 안 된다.

### Claude 수정 요청

1. 세 경로에서 `django.db.DatabaseError` 계열만 명시적으로 처리한다. 프로그래밍 오류를 넓은 `except Exception`으로 숨기지 않는다.
2. 상태 코드는 503으로 하고, 동일한 안전한 한국어 DB 준비/연결 오류 안내만 렌더링한다. 예외 문자열·연결 문자열·환경변수 값은 context, HTML, 로그 메시지에 넣지 않는다.
3. `GET /setup?collection_run=...`의 결과 조회도 안전한 DB 오류 화면으로 돌아가게 한다. 이 경우 수집·계좌 생성·원장 쓰기를 시작하면 안 된다.
4. 위 세 DB 오류를 `OperationalError` mock으로 회귀 테스트한다. 503, 내부 예외 문자열 미포함, 외부 pykrx 호출·계좌/원장/가격/수집 실행 기록 추가 없음까지 확인한다.

## 완료 기준 판정

| 기준 | Codex 확인 근거 | 판정 |
|---|---|---|
| GET `/setup` 읽기 전용 | 코드에서 조회만 사용, 51개 테스트 통과, Compose GET 200 | 충족 |
| 계좌 없음 안내·CSRF form | 정책 설정값을 읽는 context와 template의 `{% csrf_token %}` 확인 | 충족 |
| one-time 계좌 초기화·303 PRG | 기존 `accounts.initialize_account()` 재사용, 테스트 통과 | 충족 |
| 기존 계좌 상태·재설정 없음 | 계좌 snapshot/원장 합계 표시와 template 분기 확인 | 충족 |
| 수집 입력 422·외부 호출 없음 | 기존 ticker/date helper 재사용, mock 테스트 통과 | 충족 |
| 유효 수집 1회·결과 PRG 표시 | `collect_daily_prices()` 호출 뒤 run_id GET, mock 테스트·Compose HTML 확인 | 충족 |
| 출처·비조정·기준시각·행 수·제외 사유 | 결과 table과 저장된 run 표시 확인 | 충족 |
| 설정·조회·DB 오류 안전 처리 | 설정/조회 `ApiError`는 처리하지만 DB 오류 P1 존재 | 수정 필요 |
| 기존 API·health·대시보드 유지 | URL diff는 추가 경로만 포함, 전체 테스트 통과 | 충족 |
| check·migration·전체 테스트·검증 구분 | Codex가 Compose에서 직접 실행, 실제 pykrx 성공만 미확인 | 부분 충족 |

## 독립 실행 결과

| 명령 | Codex 결과 |
|---|---|
| `git diff --check dev...HEAD` | 통과 |
| `docker compose ps` | `db` healthy, `web` running |
| `docker compose exec -T web python manage.py check` | 통과 |
| `docker compose exec -T web python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `docker compose exec -T web python manage.py test trading` | 51개 통과 |
| `GET /setup`, static CSS 읽기 확인 | 200, 수집 form·CSRF token·모바일 CSS 규칙 제공 확인 |
| 실제 pykrx form 제출 | 실행하지 않음; 외부 네트워크 성공 미확인 |

- 호스트 가상환경에서 `manage.py check`은 통과했다. host 실행은 `.env`를 자동 주입하지 않아 DB가 필요한 migration/test는 실행 불가였고, Compose `web`에서 독립 재실행해 보완했다.
- 테스트 출력의 `pykrx 조회 실패`는 기존 외부 제공처 실패 mock 경로이며, 실제 네트워크 성공 증거가 아니다.

## 범위·보안 점검

- 변경은 T-007 HTML 경로·Django Template·기존 CSS 최소 확장·테스트·문서에 한정된다.
- 새 DB table/migration, 새 공개 JSON API, 외부 프론트엔드 라이브러리, 자동 수집·주문·실거래 기능은 없다.
- diff에서 API 키·토큰·비밀번호·전체 연결 문자열, 외부 CDN·font·JS 의존성을 발견하지 못했다.

## 다음 행동

P1을 수정하고 인수인계의 테스트 결과를 갱신한 뒤 Codex에 재검증을 요청한다. P1이 해결되기 전에는 push·PR·`dev` 병합을 진행하지 않는다.
