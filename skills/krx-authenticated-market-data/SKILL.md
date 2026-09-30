---
name: krx-authenticated-market-data
description: Use for Jumong T-008-style KRX-authenticated pykrx daily-price collection. Keeps KRX credentials local, blocks requests before configuration is complete, and prevents upstream credential output from escaping.
---

# 주몽 KRX 인증 일봉 수집

## 시작 전

- `AGENTS.md`, `docs/PROJECT_SPEC.md`, `docs/ENVIRONMENT.md`, 현재 T-XXX 작업 문서를 먼저 읽는다. 작업 문서가 이 Skill보다 우선한다.
- 기존 `trading.config`, `trading.market_data`, `/setup` 수집 form과 T-002·T-007 테스트를 먼저 확인한다. 같은 수집·저장·입력 검증을 다시 구현하지 않는다.
- 사용자 자격증명은 채팅, 코드, 커밋 메시지, 문서, 테스트, 인수인계에 요구하거나 기록하지 않는다.

## 자격증명 경계

- KRX 자격증명은 루트 `.env`의 `KRX_ID`, `KRX_PW`에만 존재한다. `.env`는 Git에 넣지 않는다.
- `.env.example`은 두 변수의 빈 값과 안전한 사용 설명만 제공한다. 실제처럼 보이는 ID·비밀번호도 넣지 않는다.
- Django 설정 계층이 존재 여부를 읽고, service·template·test가 `os.environ`을 직접 읽지 않는다.
- Docker Compose의 기존 `web.env_file`만 사용한다. db·browser·frontend·API 응답·DB에는 자격증명을 전달하거나 저장하지 않는다.
- 누락·부분 설정·잘못된 인증·외부 오류 모두 값·변수명·응답 원문 없이 안전하게 처리한다.

## pykrx 호출 규칙

- `MARKET_DATA_PROVIDER=pykrx`와 두 자격증명이 모두 준비됐을 때만 기존 `collect_daily_prices()`가 pykrx를 한 번 호출한다.
- pykrx의 늦은 import와 `get_market_ohlcv(..., adjusted=False)` 호출은 표준 출력·표준 오류 비노출 가드 안에서 수행한다. upstream 출력, 예외 문자열, HTTP 원문을 logger·응답·DB에 전달하지 않는다.
- 표준 스트림 가드는 전역 효과가 있으므로 최소 잠금으로 import와 호출 범위만 보호한다. 다중 프로세스·자동 수집을 지금 해결하려고 확장하지 않는다.
- 저장·품질 검증·hash·upsert·`MarketDataCollectionRun`·PRG·CSRF·GET 읽기 전용 규칙은 T-002/T-007 구현을 재사용한다.

## 검증과 금지 사항

- 자동 테스트의 pykrx는 반드시 mock한다. 실제 KRX 네트워크와 실제 자격증명을 자동 테스트에서 사용하지 않는다.
- fake 자격증명과 fake upstream 출력으로도 비밀값이 응답·로그·DB에 없는지 확인한다.
- `manage.py check`, migration dry-run, 전체 Django 테스트를 실행한다. 실제 수동 수집 결과는 별도 한정 사항으로 기록한다.
- 다른 제공처, 직접 HTTP, 재시도·스케줄러·큐, 브라우저 로그인, 쿠키 저장, secret manager, DB schema/API/UI 변경, pykrx 패키지 교체를 추가하지 않는다.
