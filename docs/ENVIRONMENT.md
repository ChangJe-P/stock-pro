# 환경변수와 비밀값 관리

## 원칙

- .env는 현재 PC의 로컬 개발용 파일이며 Git에서 제외한다.
- .env.example은 변수 이름과 안전한 예시만 Git에 저장한다.
- API 키, 비밀번호, Notion 연동 토큰, 실제 계좌 정보는 코드·Docker Compose·README·테스트 fixture·커밋·인수인계 문서에 하드코딩하지 않는다.
- backend는 하나의 설정 계층에서 환경변수를 읽는다. 누락된 필수값을 임의의 기본 비밀값으로 대체하지 않는다.
- frontend에 노출되는 환경변수는 공개되어도 되는 주소·기능 플래그만 사용한다. 비밀값을 NEXT_PUBLIC 접두어 변수에 넣지 않는다.
- 로그와 오류 메시지에 키·토큰·비밀번호·전체 연결 문자열을 출력하지 않는다.
- 설정 파일이나 코드에 설명이 필요하면 주석은 한국어로 작성한다. 단, 비밀값이나 전체 연결 문자열을 주석에 적지 않는다.

## T-001에서 필요한 값

| 변수 | 용도 | 로컬 기본값 |
|---|---|---|
| APP_ENV | 실행 환경 구분 | development |
| FRONTEND_PORT | frontend 공개 포트 | 3000 |
| BACKEND_PORT | backend 공개 포트 | 8000 |
| CORS_ALLOWED_ORIGINS | 개발 frontend 주소 | http://localhost:3000 |
| POSTGRES_HOST | Compose 내부 DB 호스트 | db |
| POSTGRES_PORT | DB 포트 | 5432 |
| POSTGRES_DB | 로컬 개발 DB 이름 | jumong |
| POSTGRES_USER | 로컬 개발 DB 사용자 | jumong_app |
| POSTGRES_PASSWORD | 로컬 개발 DB 비밀번호 | .env에서만 설정 |

Claude Code는 Docker Compose와 backend 설정에서 위 값을 사용한다. 포트·호스트·DB 자격 증명을 코드나 Compose 파일에 직접 적지 않는다.

## 시장 데이터 변수 (T-002, pykrx)

T-002에서 승인된 유일한 데이터 제공처는 Python 패키지 `pykrx`다. pykrx는 API 키·주소·요청 제한이 필요 없다.

| 변수 | 용도 | 로컬 값 |
|---|---|---|
| MARKET_DATA_PROVIDER | 수집 제공처 선택 | `pykrx` |
| MARKET_DATA_BASE_URL | pykrx에는 필요 없음 | 비어 있음 |
| MARKET_DATA_API_KEY | pykrx에는 필요 없음 | 비어 있음 |
| MARKET_DATA_API_SECRET | pykrx에는 필요 없음 | 비어 있음 |
| MARKET_DATA_REQUESTS_PER_MINUTE | pykrx에는 필요 없음 | 비어 있음 |

- `MARKET_DATA_PROVIDER=pykrx`일 때만 수집을 허용한다. 값이 비어 있거나 다른 값이면 외부 요청을 보내지 않고 비밀값을 포함하지 않는 설정 오류로 끝낸다.
- backend는 T-002 수집에서 `MARKET_DATA_BASE_URL`·`MARKET_DATA_API_KEY`·`MARKET_DATA_API_SECRET`·`MARKET_DATA_REQUESTS_PER_MINUTE`를 읽지 않으며 로그에도 남기지 않는다.
- pykrx 외 다른 제공처(KIS 등)를 위한 인터페이스·팩토리는 만들지 않는다.

## 아직 값이 없는 외부 연동 변수

| 변수 | 언제 설정하는가 | 현재 상태 |
|---|---|---|
| NOTION_INTEGRATION_TOKEN | Notion 내보내기 기능을 구현할 때 | 비어 있음 |
| NOTION_ 접두어 데이터 소스 ID | 주몽 운영실 데이터베이스를 만든 뒤 | 비어 있음 |

MVP에는 증권사 계좌·주문 API 변수를 추가하지 않는다. 실제 계좌나 주문 기능은 프로젝트 범위 밖이다.

## 지금 입력할 값

- `POSTGRES_PASSWORD`만 지금 정한다. 로컬 개발 DB 전용 비밀번호이며, `.env`에만 입력한다.
- T-002에서는 `MARKET_DATA_PROVIDER=pykrx`로 둔다. pykrx는 키·주소·요청 제한이 필요 없으므로 나머지 `MARKET_DATA_` 변수는 빈 값으로 둔다.
- 향후 다른 제공처를 승인하면(별도 작업 문서 필요) 제공처 코드, 공식 API 주소, 인증키, 별도 비밀값 유무, 요청 제한을 `.env`에 입력한다.
- Notion을 바로 연동하지 않으면 `NOTION_` 변수도 빈 값으로 둔다. 연동할 때는 Internal connection의 설치 액세스 토큰과 주몽 운영실의 각 데이터 소스 ID를 입력한다.

## 구현 시 처리

- T-001은 빈 외부 API 키 때문에 Docker 기반 환경 구성이 실패하지 않아야 한다. 외부 연동 기능 자체를 아직 만들지 않기 때문이다.
- 이후 외부 연동 기능은 필요한 변수, 권한 범위, 누락 시 동작, 테스트용 가짜 값을 작업 명세에 먼저 추가한다.
- 시장 데이터 기능은 제공처·주소·필수 인증값 중 하나라도 비어 있으면 요청을 보내지 않고, 설정이 필요하다고 알려야 한다.
- API 키가 필요한 기능은 키가 비어 있으면 요청을 보내지 않고, 사용자에게 설정이 필요하다고 알려야 한다.
