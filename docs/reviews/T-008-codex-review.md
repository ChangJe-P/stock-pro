---
task_id: T-008
branch: codex/krx-auth
base_branch: dev
reviewer: Codex
reviewed_commits: f8b355a, 081e351
review_date: 2026-09-30
verdict: approved_with_unverified_external_data
---

# T-008 Codex 검토: KRX 인증 기반 pykrx 수동 수집

## 결론

**승인 — 병합 가능.** KRX ID·비밀번호는 Django 설정에서만 읽고, 제공처가 `pykrx`이며 두 값이 모두 존재할 때만 수집을 허용한다. 누락·부분 설정은 pykrx import 전에 503으로 끝나며, pykrx import와 호출 중의 표준 출력·오류는 잠금 안에서 캡처해 폐기한다. Codex가 실제 자격증명을 전달하지 않은 Compose 컨테이너에서 Django 검사·마이그레이션 검사·전체 61개 테스트와 503 응답을 독립 확인했다.

실제 KRX 자격증명으로 한 종목 일봉을 성공 수집하는 외부 네트워크 검증은 실행하지 않았다. `.env`의 실제 값은 열어 보지 않았고, 그 값이 HTTP 응답·로그·DB에 새지 않는지는 mock 기반 회귀 테스트로만 확인했다. 이 항목은 통과로 쓰지 않으며, 사용자 로컬 환경에서의 후속 수동 확인으로 남긴다.

## 대조 대상

- 작업 문서: `docs/tasks/T-008-krx-authenticated-market-data.md`
- 프로젝트 Skill: `skills/krx-authenticated-market-data/SKILL.md`
- 인수인계: `docs/handoffs/T-008-claude-handoff.md`
- 비교 범위: `dev...codex/krx-auth`, 10개 파일, 403줄 추가·21줄 삭제
- 구현 커밋: `f8b355a`
- 인수인계 커밋: `081e351`

## 완료 기준 판정

| 기준 | Codex 확인 근거 | 판정 |
|---|---|---|
| Git 추적 파일에 변수 이름·안전한 설명만 존재 | `.env.example`은 빈 `KRX_ID=`·`KRX_PW=`만 제공하며, diff의 문서·코드에 실제 값 없음 | 충족 |
| 설정 계층에서만 읽고 web에만 전달 | `jumong/settings.py`에서만 환경변수 읽기, Compose의 기존 `web.env_file`만 사용하고 `db`에는 전달 없음 | 충족 |
| 하나라도 없으면 외부 요청 없이 503 | `market_data_configured()`의 제공처·두 값 게이트, 3개 누락/제공처 테스트, 빈 값 Compose API 503 확인 | 충족 |
| 모두 있으면 기존 pykrx 수집 규칙 재사용 | 기존 `collect_daily_prices()` 경로, `adjusted=False`, 기존 검증·저장·실행 기록 로직 유지 | 충족 |
| ID·PW·upstream 원문 비노출 | `fetch_ohlcv()`가 import·호출을 `redirect_stdout`·`redirect_stderr`와 전역 잠금으로 감쌈; 성공·실패 mock 비노출 테스트 통과 | 충족 |
| 기존 `/setup`·JSON API 안전 동작 유지 | 수집 진입점은 기존 함수를 재사용하며 전체 trading 테스트 61개 통과 | 충족 |
| check·migration·전체 테스트 증거 | Codex가 새 Compose 이미지에서 세 명령을 독립 실행 | 충족 |
| 실제 KRX 성공 수집 | 실제 값·외부 요청을 실행하지 않음 | 미확인 |

## 독립 실행 결과

| 명령 | Codex 결과 |
|---|---|
| `git diff --check dev...HEAD` | 통과 |
| `docker compose up -d --build` | 현재 브랜치의 web 이미지를 재빌드하고 db healthy·web running 확인 |
| `docker compose exec -T -e KRX_ID= -e KRX_PW= web python manage.py check` | `System check identified no issues` |
| `docker compose exec -T -e KRX_ID= -e KRX_PW= web python manage.py makemigrations --check --dry-run` | `No changes detected` |
| `docker compose exec -T -e KRX_ID= -e KRX_PW= web python manage.py test trading` | **61개 통과** |
| 빈 KRX 변수의 JSON 수집 POST | **503**, 제공처 설정만 담긴 안전한 응답; pykrx 호출 없음 |
| 실제 KRX 인증·외부 일봉 수집 | 실행하지 않음; 성공 여부 미확인 |

- Django 검사·마이그레이션·테스트·503 확인 명령에는 `KRX_ID`와 `KRX_PW`를 빈 값으로 명시해 실제 로컬 자격증명이 그 검증 프로세스로 전달되지 않게 했다.
- 테스트 출력의 `pykrx 조회 실패`는 mock된 외부 실패 경로이며, 실제 KRX 네트워크 성공 증거가 아니다.

## 범위·보안 점검

- 변경은 설정 게이트, pykrx 출력 가드, 회귀 테스트, 환경 문서에 한정된다.
- 새 provider·직접 HTTP·재시도·스케줄러·쿠키 저장·secret manager·DB migration·의존성·UI/주문 기능 변경은 없다.
- 추적 diff에서 실제 API 키·토큰·비밀번호·전체 DB 연결 문자열을 발견하지 못했다.
- 전역 표준 스트림 전환은 단일 로컬 web 프로세스 전제를 가지며, `ponytail:` 주석이 다중 프로세스·동시 수집 추가 시 재검토 지점을 명시한다.

## 발견 사항과 병합 판단

- **P0: 없음**
- **P1: 없음**
- **P2: 없음**

실제 KRX 수집 성공은 외부·비밀값 의존 항목으로 `미확인`이다. 그러나 누락 자격증명 차단, 비노출 가드, 회귀 테스트, 기존 흐름 보존은 독립 확인됐으므로 T-008의 안전한 로컬 인증 적용은 병합해도 된다. 사용자가 승인하면 `codex/krx-auth`를 원격에 push하고 T-008의 `dev` 병합 요청을 준비한다.
