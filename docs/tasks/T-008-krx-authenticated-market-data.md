---
id: T-008
title: KRX 인증 기반 pykrx 일봉 수집 설정
status: ready_for_claude
branch: codex/krx-auth
owner: Claude Code
reviewer: Codex
depends_on: T-007
---

# T-008 KRX 인증 기반 pykrx 일봉 수집 설정

## 배경과 목표

T-007 병합 뒤 실제 `pykrx` 비조정 일봉 수집을 종목 `000660`, 2024-01-02~03으로 한 번 실행했다. 수집 실행 기록은 0행 `partial/no_data_in_range`로 안전하게 남았지만, 실행 중 `KRX_ID` 또는 `KRX_PW`가 없다는 인증 경고와 외부 응답 파싱 오류가 확인됐다.

현재 설치된 pykrx는 KRX 로그인 세션을 지원하며, 인증이 필요한 요청에는 `KRX_ID`, `KRX_PW`를 사용한다. 이 작업의 목표는 사용자가 이미 보유한 KRX 로그인 정보를 **로컬 `.env`와 Docker `web` 컨테이너에만** 안전하게 제공하고, 한 종목·기간의 기존 수동 일봉 수집이 인증 설정을 확인한 뒤 pykrx를 호출하게 만드는 것이다.

## 확정 결정

- KRX는 실제 증권계좌·실제 주문과 무관한 시장 데이터 인증 용도다. 가상투자 제품 경계는 바꾸지 않는다.
- pykrx가 요구하는 변수명 그대로 `KRX_ID`, `KRX_PW`만 사용한다. 별칭·다른 제공처·계정 생성 UI는 만들지 않는다.
- 실제 값은 루트 `.env`에만 둔다. `.env.example`, Git, Claude 인수인계, 테스트 fixture, 브라우저 화면, 로그, 오류 응답에는 실제 값을 절대 넣지 않는다.
- `docker-compose.yml`의 기존 `web.env_file: .env`만 사용한다. `db` 서비스에는 KRX 자격증명을 전달하지 않는다.
- pykrx 최신 버전은 import/로그인 중 표준 출력에 로그인 ID를 출력할 수 있다. 따라서 pykrx import와 호출을 비밀값 비노출 가드 안에서 수행해야 한다. 표준 출력·표준 오류 원문, 예외 원문, 응답 원문을 로그·HTTP 응답·DB에 남기지 않는다.
- 자격증명은 Django 설정 계층에서 존재 여부만 판정한다. pykrx 내부가 같은 프로세스 환경변수를 읽는 것은 upstream 요구사항으로 한정하며, 애플리케이션 코드가 값을 출력·직렬화·전달용 API로 노출하면 안 된다.

## 구현 범위

### 1. 로컬 설정과 문서

- `.env.example`에 아래 두 빈 변수와 한국어 주석을 추가한다. 예시 ID·예시 비밀번호를 넣지 않는다.
  - `KRX_ID=`
  - `KRX_PW=`
- `docs/ENVIRONMENT.md`의 pykrx 설명을 현재 동작에 맞게 수정한다.
  - 비조정 일봉 수집에 KRX 인증이 필요할 수 있음을 기록한다.
  - 두 변수의 용도, 로컬 `.env` 전용, Git 금지, `web` 컨테이너만 전달됨, 누락 시 외부 요청을 보내지 않는다는 규칙을 기록한다.
  - 이전의 "pykrx는 인증값이 필요 없다"는 문구는 제거한다. `MARKET_DATA_BASE_URL`·`MARKET_DATA_API_KEY`·`MARKET_DATA_API_SECRET`·`MARKET_DATA_REQUESTS_PER_MINUTE`가 여전히 미사용임도 유지한다.
- 사용자가 `.env`를 수정한 뒤에는 이미지 재빌드 없이 `docker compose up -d --force-recreate web`으로 `web`만 다시 만들면 됨을 문서화한다. 실제 값이 들어간 `.env` 내용이나 Compose 설정 출력 전문을 기록하지 않는다.

### 2. 안전한 설정 판정

- `backend/jumong/settings.py`에서 `KRX_ID`, `KRX_PW`를 읽는다. 서비스·template·테스트가 `os.environ`을 직접 읽지 않는다.
- `backend/trading/config.py`에 두 값이 모두 비어 있지 않을 때만 참이 되는 최소 판정 함수를 둔다. 값 자체·길이·일부 마스킹 값은 반환하거나 오류 메시지에 쓰지 않는다.
- 기존 `market_data_configured()`는 제공처가 `pykrx`이고 KRX 자격증명이 모두 있을 때만 참이 되게 최소 수정한다.
- 제공처가 아니거나 ID·비밀번호 중 하나라도 없으면 pykrx import·로그인·외부 HTTP 호출 없이 안전한 `503` 설정 오류로 끝낸다. 화면에는 기존 수집 오류 영역을 재사용하고, 오류 문구에는 변수명·값·계정 정보·연결 정보를 넣지 않는다.

### 3. pykrx 호출 경계

- 기존 `market_data.collect_daily_prices()`와 저장·검증·upsert·수집 실행 기록 구조를 재사용한다. API 경로, form 입력 형식, PRG, 주문 체결 규칙, 스키마는 바꾸지 않는다.
- `fetch_ohlcv()`의 늦은 pykrx import와 실제 `get_market_ohlcv(..., adjusted=False)` 호출을 하나의 비밀값 비노출 가드 안에서 처리한다.
  - pykrx가 출력하는 로그인 ID·비밀번호·응답 원문이 프로세스 표준 출력/표준 오류를 통해 노출되지 않게 캡처·폐기한다.
  - 표준 스트림 전환은 프로세스 전역이므로 최소 잠금으로 import와 단일 호출만 감싼다. 코드에는 `ponytail:` 주석으로 단일 로컬 web 프로세스 전제와 다중 프로세스 수집을 추가할 때의 재검토 지점을 남긴다.
  - pykrx의 실패 원문을 재노출하지 말고, 기존의 안전한 외부 조회 실패(`502`) 흐름으로 변환한다.
- 외부 호출의 자동 재시도, 스케줄러, 큐, session/쿠키 파일 저장, 브라우저 자동 로그인, 직접 HTTP 요청, pykrx 버전 변경·포크·site-packages 수정은 추가하지 않는다.

### 4. 테스트와 수동 확인

- 자동 테스트는 실제 KRX에 접속하지 않는다. pykrx 호출을 mock 처리한다.
- 최소 자동 테스트:
  - provider가 아니거나 KRX_ID/KRX_PW 중 하나가 없으면 503이고 pykrx import/호출이 일어나지 않음
  - 둘 다 있을 때 기존 수집 경로가 mock된 pykrx 결과를 저장하고 기존 품질 검증·실행 기록이 유지됨
  - pykrx import/호출이 fake ID·fake password·fake upstream error를 출력해도 응답·로그 캡처·수집 실행 기록에 그 문자열이 없음
  - `/setup` 수집 POST가 누락 인증에서 503 안전 HTML을 반환하고, CSRF·422·PRG·GET 읽기 전용 규칙이 유지됨
- `python manage.py check`, `python manage.py makemigrations --check --dry-run`, 전체 Django 테스트를 실행한다.
- 사용자의 실제 값으로 확인할 때만, `web`을 재생성한 뒤 `/setup`에서 한 종목·짧은 기간을 수동 수집한다. 성공·0행·인증 실패·외부 실패를 구분해 기록하되, 자격증명·표준 출력 원문·전체 로그는 인수인계에 넣지 않는다.

## 제외 범위

- 실제 증권계좌·실제 주문·자동매매·자동 수집·실시간/장중 시세
- KIS 또는 다른 데이터 제공처, 제공처 추상화·팩토리, pykrx 교체·다운그레이드·포크
- 회원가입·비밀번호 변경·브라우저 로그인 자동화·세션/쿠키 영속화·자격증명 관리 서비스
- 인증 입력 화면, DB 저장, API 반환, Notion 연동, 다중 사용자, 새 테이블·migration·의존성
- 대시보드·주문·포트폴리오 UI 변경

## 완료 기준

1. Git에 저장되는 파일에는 `KRX_ID`, `KRX_PW`의 이름과 안전한 설명만 있고 실제 값은 없다.
2. Django 설정 계층에서만 두 값을 읽고, `web` 외 Compose 서비스에는 전달하지 않는다.
3. ID·비밀번호가 하나라도 없으면 외부 요청 없이 안전한 503으로 끝난다.
4. 둘 다 있으면 기존 pykrx 비조정 일봉 수집·검증·저장 경로를 재사용한다.
5. pykrx의 표준 출력/표준 오류와 예외 원문에서 ID·비밀번호·응답 원문이 로그·응답·DB로 새지 않는다.
6. 기존 `/setup` POST와 JSON 수집 API의 입력 검증·안전한 오류·수집 기록 규칙이 유지된다.
7. Django check, migration dry-run, 전체 테스트가 통과한다. mock·Compose·실제 KRX 네트워크 결과를 구분해 인수인계에 기록한다.
8. 실제 KRX 수집 성공은 사용자의 로컬 `.env` 설정 뒤에만 별도 수동 검증하며, 성공하지 못했으면 통과로 기록하지 않는다.
