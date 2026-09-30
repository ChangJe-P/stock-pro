---
task_id: T-008
branch: codex/krx-auth
commit: f8b355a
status: complete
---

# Claude Code 구현 인수인계

## 작업 요약

- 구현한 내용: 최신 pykrx가 요구하는 KRX 로그인 인증(`KRX_ID`, `KRX_PW`)을 **로컬 `.env`와 Docker `web` 컨테이너에만** 안전하게 적용했다. Django 설정 계층에서만 두 값을 읽고 `trading.config`가 존재 여부만 판정하며, 제공처가 pykrx이고 두 값이 모두 있을 때만 기존 수집 경로가 pykrx를 호출한다. 누락·부분 설정이면 pykrx import·로그인·외부 요청 없이 안전한 503으로 끝난다. pykrx의 늦은 import와 단일 호출은 전역 잠금 + 표준 출력/오류 캡처 가드 안에서 수행해 로그인 ID·응답 원문이 로그·응답·DB로 새지 않게 했다. 기존 수집·검증·upsert·`MarketDataCollectionRun`·`/setup` POST(422·CSRF·PRG·GET 읽기 전용)와 JSON API는 그대로 재사용했다.
- 구현하지 않은 내용(제외 범위 준수): 다른 제공처·추상화, 직접 HTTP, 재시도·스케줄러·큐, 브라우저 로그인·쿠키/세션 파일, secret manager, 인증 입력 화면·DB 저장·API 반환, pykrx 교체·포크, 새 테이블·migration·의존성, 대시보드·주문·포트폴리오 UI 변경.

## 변경·생성 파일

| 파일 | 내용 |
|---|---|
| backend/jumong/settings.py | `KRX_ID`·`KRX_PW`를 설정 계층에서만 읽음(값·길이·마스킹 미노출) |
| backend/trading/config.py | `krx_credentials_present()`(존재 여부만) 추가, `market_data_configured()`를 provider==pykrx AND 두 자격증명 존재로 최소 수정 |
| backend/trading/market_data.py | `fetch_ohlcv`를 전역 잠금 + `redirect_stdout`/`redirect_stderr` 가드로 감싸 upstream 출력 캡처·폐기. `ponytail:` 주석으로 단일 web 프로세스 전제·재검토 지점 명시 |
| .env.example | `KRX_ID=`·`KRX_PW=` 빈 값과 안전한 로컬 사용 규칙 주석 추가. "pykrx는 인증 불필요" 문구 제거 |
| docs/ENVIRONMENT.md | KRX 인증 변수 절 추가(용도·로컬 전용·Git 금지·web만 전달·누락 시 미요청·force-recreate 절차). 미사용 MARKET_DATA_* 유지 |
| backend/trading/tests.py | T-008 테스트 7건 추가(누락 503·비import, 완전 설정 수집, upstream 비노출) |

로컬 `.env`에는 `KRX_ID=`·`KRX_PW=`를 빈 값으로 두었다(사용자가 실제 값 입력). `.env`는 Git 제외. 새 migration·모델·공개 API·의존성 없음(`makemigrations --check`=No changes).

## 완료 기준 대조 (요구사항별 구현 위치)

| 완료 기준 | 구현 위치 | 판정 |
|---|---|---|
| 1. Git 파일엔 이름·설명만, 실제 값 없음 | `.env.example`(빈 값), docs/ENVIRONMENT.md, `.env`는 미추적 | 충족 |
| 2. 설정 계층에서만 읽고 web 외 미전달 | `settings.KRX_ID/KRX_PW`; compose `web.env_file: .env`만(변경 없음), `db` 미전달 | 충족 |
| 3. 하나라도 없으면 외부 요청 없이 503 | `market_data_configured()` 게이트 → `collect_daily_prices` 503(기존 재사용); `KrxAuthConfigTests` | 충족 |
| 4. 둘 다 있으면 기존 pykrx 비조정 수집·검증·저장 재사용 | `collect_daily_prices`/`fetch_ohlcv`(adjusted=False) 그대로; `test_full_config_is_configured`, 수집 저장 테스트 | 충족 |
| 5. 표준 출력/오류·예외 원문에서 ID·PW·응답 원문 미노출 | `fetch_ohlcv` 가드(캡처·폐기) + 기존 generic 502·로그; `KrxUpstreamNonLeakTests` | 충족 |
| 6. `/setup` POST·JSON API 입력검증·안전 오류·수집 기록 유지 | 기존 view·검증 재사용(변경 없음); 기존 SetupScreenTests·MarketDataApiTests 통과 | 충족 |
| 7. check·migration dry-run·전체 테스트 통과, 검증 구분 기록 | 아래 실행과 검증 | 충족 |
| 8. 실제 KRX 성공은 사용자 설정 뒤 수동, 실패/미실행은 통과로 안 씀 | 아래 실제 네트워크 절 참조 | 충족(미검증 명시) |

## 실행과 검증

### 자동 테스트 (Django test runner, pykrx mock, 실 네트워크·실 자격증명 없음)

Django 테스트 DB(실제 PostgreSQL). pykrx는 mock(가짜 모듈/`fetch_ohlcv` patch), 실제 KRX·실제 자격증명 없음. 테스트의 가짜 자격증명은 존재 여부 판정·비노출 검증 전용이다.

| 명령 | 결과 |
|---|---|
| `python manage.py check` | System check identified no issues |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test trading` | **Ran 61 tests … OK**(기존 54 + T-008 7) |

T-008 신규 테스트: provider 아님/`KRX_ID` 누락/`KRX_PW` 누락 시 503·`fetch_ohlcv`(pykrx import) 미호출·수집 기록 0; 완전 설정에서 `market_data_configured()` 참; 판정 함수가 불리언만 반환; 가짜 upstream이 표준 출력에 자격증명을 쓰고 예외 원문에 담아도 HTTP 응답·`assertLogs` 로그·`MarketDataCollectionRun`·가드 외부 표준 출력 어디에도 그 문자열이 없음(실패 502·성공 경로 각각).

### 실제 Docker Compose(db·web) 확인 (자동 테스트와 별도)

코드 변경이 있어 `docker compose up -d --build web`로 `web`을 다시 만든 뒤 확인했다. 로컬 `.env`의 `KRX_ID`·`KRX_PW`는 빈 값이다.

| 확인 | 결과 |
|---|---|
| `POST /market-data/daily-prices/collect`(JSON, 자격증명 누락) | **HTTP 503**, body `{"detail":"시장 데이터 수집이 설정되지 않았습니다. MARKET_DATA_PROVIDER=pykrx가 필요합니다."}` — KRX 변수명·값·연결 정보 없음, 외부 요청·수집 기록 없음 |

- 오류 문구는 provider 설정만 언급하고 `KRX_ID`/`KRX_PW`·값·계정 정보를 포함하지 않는다.

### 실제 KRX 네트워크 (미검증)

실제 KRX 자격증명으로의 성공 수집은 **검증하지 않았다.** 자격증명은 사용자만 로컬 `.env`에 입력하며(현재 빈 값), 이 인수인계·코드·테스트·로그에 실제 값을 넣지 않는다. 사용자가 값을 입력하고 `docker compose up -d --force-recreate web`로 재생성한 뒤 `/setup`에서 한 종목·짧은 기간을 수동 수집해 성공/0행/인증 실패/외부 실패를 구분 확인해야 한다. **성공을 통과로 기록하지 않는다.**

## 가정과 제한

- 표준 스트림 전환은 프로세스 전역이므로 단일 로컬 `web` 프로세스를 전제로 전역 잠금 하나로 import와 단일 호출만 감쌌다(코드 `ponytail:` 주석). 다중 프로세스·스레드 동시 수집이나 자동 수집을 추가하면 가드 범위·격리를 재검토해야 한다.
- 표준 출력/오류 가드는 Python 레벨(`contextlib.redirect_*`)이다. upstream이 C 레벨 파일 디스크립터로 직접 쓰는 경우는 이 범위 밖이며, 현재 pykrx 동작 기준으로 로그·응답·DB 비노출을 목표로 한다.
- 503 게이트 메시지는 기존 문구를 유지해 `MARKET_DATA_PROVIDER`만 언급한다(제공처 설정 값, KRX 자격증명 변수명·값 아님). 누락 원인이 provider인지 자격증명인지 구분해 노출하지 않는다.
- pykrx가 같은 프로세스 환경변수(`KRX_ID`/`KRX_PW`)를 직접 읽는 것은 upstream 요구사항으로 한정한다. 애플리케이션 코드는 값을 출력·직렬화·API로 노출하지 않는다.
- 실제 자격증명 확인이 필요한 완료 기준 8은 위 "실제 KRX 네트워크(미검증)"로 남긴다.

## 미해결 항목과 다음 제안

- 실제 KRX 자격증명 성공 수집 수동 확인(사용자 `.env` 입력 후) — 현재 미검증.
- main/dev로의 병합·push·PR은 규칙에 따라 하지 않았다. Codex 검증 후 진행.

## 최종 보고
- 커밋: `f8b355a`(구현), 본 인수인계는 별도 커밋
- 인수인계 파일: `docs/handoffs/T-008-claude-handoff.md`
