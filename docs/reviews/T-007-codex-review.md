---
task_id: T-007
branch: codex/onboarding
base_branch: dev
reviewer: Codex
reviewed_commits: b97e6f1, b59bdd0, 0cb3651, c23348e
review_date: 2026-09-30
verdict: approved_with_unverified_external_data
---

# T-007 Codex 검토: 가상투자 시작과 일봉 수동 준비 화면

## 결론

**승인 — 병합 가능.** P1 수정 `0cb3651`이 `/setup`의 GET·두 POST에서 `DatabaseError`만 명시적으로 잡아 안전한 503 HTML 안내로 바꾸고, 예외 원문을 노출하지 않도록 해결했다. Codex가 새 Compose 이미지에서 전체 54개 테스트와 세 경로의 독립 `OperationalError` mock을 재실행해 이를 확인했다.

실제 pykrx 네트워크 수집 성공은 이번에도 검증하지 않았다. mock 테스트와 Compose의 저장된 실행 기록 표시는 통과했지만, 외부 제공처 성공은 `미확인`으로 남긴다.

## 대조 대상

- 작업 문서: `docs/tasks/T-007-onboarding-data-setup.md`
- 프로젝트 Skill: `skills/onboarding-data-setup/SKILL.md`
- 인수인계: `docs/handoffs/T-007-claude-handoff.md`
- 비교 범위: `dev...codex/onboarding`, 9개 파일, 641줄 추가·3줄 삭제
- 구현 커밋: `b97e6f1`
- 인수인계 커밋: `b59bdd0`

## 이전 P1 해결 확인 — DB 오류 503 안전 처리

기존 P1은 `backend/trading/views.py`의 두 POST가 `ApiError`만 처리하고, `setup()`의 `MarketDataCollectionRun` 조회가 DB 오류를 처리하지 않던 문제였다. `0cb3651`은 `_setup_context()`의 넓은 예외 처리를 `DatabaseError`로 좁히고, `_db_error_response()`를 추가했으며, 수집 실행 기록 조회와 두 POST에서 `DatabaseError`를 503 안전 화면으로 전환한다. 일반 `Exception`을 잡아 프로그래밍 오류를 숨기지는 않는다.

재빌드한 Compose `web` 컨테이너에서 `OperationalError("db outage secret-like-detail")`를 mock해 독립 확인한 결과는 다음과 같다.

| 경로 | Codex 결과 | 위험 |
|---|---|---|
| `POST /setup/account/initialize` | 503, mock 예외 문자열 미포함 | 해결 |
| `POST /setup/market-data/collect` | 503, mock 예외 문자열 미포함 | 해결 |
| `GET /setup?collection_run=x` | 503, mock 예외 문자열 미포함 | 해결 |

실제 DB 예외에는 호스트·연결 정보가 포함될 수 있다. 현재 `DEBUG=True` Compose에서도 위 모의 문자열이 응답에 없음을 확인했고, 새 회귀 테스트 세 건은 503·예외 문자열 미포함·추가 기록 없음·외부 pykrx 미호출을 검증한다.

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
| 설정·조회·DB 오류 안전 처리 | `ApiError` 기존 처리와 GET·두 POST의 `DatabaseError` 503 회귀 테스트를 독립 확인 | 충족 |
| 기존 API·health·대시보드 유지 | URL diff는 추가 경로만 포함, 전체 테스트 통과 | 충족 |
| check·migration·전체 테스트·검증 구분 | Codex가 Compose에서 직접 54개 테스트를 재실행, 실제 pykrx 성공만 미확인 | 부분 충족 |

## 독립 실행 결과

| 명령 | Codex 결과 |
|---|---|
| `git diff --check dev...HEAD` | 통과 |
| `docker compose ps` | `db` healthy, `web` running |
| `docker compose exec -T web python manage.py check` | 통과 |
| `docker compose exec -T web python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `docker compose up -d --build` | 수정본 web 이미지를 재빌드·기동, DB volume 유지 |
| `docker compose exec -T web python manage.py test trading` | 54개 통과 |
| `GET /setup`, static CSS 읽기 확인 | 200, 수집 form·CSRF token·모바일 CSS 규칙 제공 확인 |
| `OperationalError` mock: GET·두 POST | 모두 503, mock 내부 문자열 미포함 |
| 실제 pykrx form 제출 | 실행하지 않음; 외부 네트워크 성공 미확인 |

- 호스트 가상환경에서 `manage.py check`은 통과했다. host 실행은 `.env`를 자동 주입하지 않아 DB가 필요한 migration/test는 실행 불가였고, Compose `web`에서 독립 재실행해 보완했다.
- 테스트 출력의 `pykrx 조회 실패`는 기존 외부 제공처 실패 mock 경로이며, 실제 네트워크 성공 증거가 아니다.

## 범위·보안 점검

- 변경은 T-007 HTML 경로·Django Template·기존 CSS 최소 확장·테스트·문서에 한정된다.
- 새 DB table/migration, 새 공개 JSON API, 외부 프론트엔드 라이브러리, 자동 수집·주문·실거래 기능은 없다.
- diff에서 API 키·토큰·비밀번호·전체 연결 문자열, 외부 CDN·font·JS 의존성을 발견하지 못했다.

## 병합 판단과 다음 행동

P0·P1·P2는 없다. 실제 pykrx 네트워크 성공만 외부 환경 제약으로 미확인인 상태이며, 이는 자동 수집·실거래가 아닌 수동 수집 화면의 병합을 막지 않는다. 사용자가 승인하면 `codex/onboarding`을 원격에 push하고 T-007의 `dev` 병합 요청을 준비한다.
