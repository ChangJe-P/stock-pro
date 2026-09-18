---
task_id: T-002
branch: codex/data
commit: 722c5ee
status: complete
---

# Claude Code 구현 인수인계

## 작업 요약

- 구현한 내용: `pykrx` 공개 일봉 OHLCV 조회로 한 종목·기간을 수집해 PostgreSQL(`daily_prices`)에 저장하고, 수집 실행 메타데이터를 `market_data_collection_runs`에 남기며, 저장 데이터를 거래일 오름차순으로 조회하는 backend 전용 API 두 개(`POST /market-data/daily-prices/collect`, `GET /market-data/daily-prices`)를 추가했다. `MARKET_DATA_PROVIDER=pykrx`일 때만 수집하고, 그 외에는 외부 요청 없이 안전한 설정 오류로 끝난다.
- 구현하지 않은 내용(제외 범위 준수): 실제 계좌·주문·자동매매, 로그인·다중 사용자, 종목/시장 마스터·전 종목 일괄 수집, 백테스트·기업행동, 실시간·장중 시세, 스케줄러·작업 큐·캐시, 다른 제공처(KIS 등) 인터페이스·팩토리, Notion·frontend 변경.

## 변경·생성 파일

| 파일 | 변경 이유 |
|---|---|
| backend/app/market_data.py (신규) | 스키마 초기화, pykrx fetch(adjusted=False), 검증, SHA-256 해시, upsert 적재, 조회, APIRouter 2개 |
| backend/app/config.py | `market_data_configured`를 `provider==pykrx` 판정으로 최소 수정. base_url/api_key 조건 제거, `market_data_provider_normalized` 추가 |
| backend/app/main.py | market_data 라우터 include. `/health`는 그대로 유지 |
| backend/requirements.txt | `pykrx` 최소 의존성 추가(버전 미추측) |
| backend/requirements.lock.txt | 실제 설치 버전 반영(pykrx 1.2.8, pandas 2.3.3, numpy 2.5.3, requests 2.34.2 등) |
| backend/tests/test_market_data.py (신규) | pykrx·DB를 mock한 backend 테스트(실제 네트워크 없음) |
| .env.example | `MARKET_DATA_PROVIDER=pykrx`, 나머지 MARKET_DATA_는 불필요·빈 값 명시 |
| docs/ENVIRONMENT.md | T-002 pykrx 설정 규칙 반영(키·endpoint 미사용·미로그) |
| README.md | 수집/조회 API 목적·사용법·제한·비투자조언 고지, 설정 전제 |

로컬 `.env`는 커밋하지 않고 `MARKET_DATA_PROVIDER=pykrx`로만 로컬 설정했다.

## 완료 기준 대조

| 완료 기준 | 구현 위치 또는 증거 | 판정 |
|---|---|---|
| 1. pykrx일 때만 수집, 그 외 외부 요청 없이 안전 실패 | `_require_configured` → 503, `test_collect_blocked_when_not_pykrx`(fetch 미호출 단언) | 충족 |
| 2. 한 종목·기간 일봉을 pykrx에서 가져와 daily_prices 저장 | `collect_daily_prices`→`store_collection`; 실제 DB 통합 확인(run1 inserted 2) | 충족(적재 경로 실DB 확인, 단 아래 실데이터 항목 참조) |
| 3. 실행별 출처·기준시각·해시·반환/제외 행수·상태 기록 | `market_data_collection_runs` INSERT; 통합 확인 collection_runs=2 | 충족 |
| 4. (종목,거래일) 중복 없이 재수집 시 갱신 | UNIQUE 제약 + `ON CONFLICT DO UPDATE`; 통합 확인 run2 inserted 0/updated 2, 중복 0건, close 105→107 | 충족(실DB 확인) |
| 5. 입력·기간·중복·누락·OHLC·0/음수 검증, 결과 미은닉 | `validate_and_transform`(사유별 제외), 응답·run에 제외 건수·사유; `test_validate_and_transform_splits_valid_and_excluded` | 충족 |
| 6. GET 오름차순 조회, 외부 수집 미시작 | `query_daily_prices` ORDER BY trade_date ASC; `test_get_does_not_trigger_fetch` | 충족 |
| 7. 실주문·계좌·KIS·실시간·스케줄러·frontend 미추가 | 신규 코드는 backend 수집/조회에 한정, frontend 무변경 | 충족 |
| 8. 기존 /health 유지 | main.py health 그대로, TestClient로 동작 확인, `test_health_*` 통과 | 충족 |
| 9. mock 테스트·기존 테스트 통과, 실네트워크 여부 별도 명시 | pytest 11 passed(전부 mock), 실네트워크는 아래 별도 기록 | 충족 |
| 10. README·환경문서·핸드오프 기록 | README/ENVIRONMENT/본 문서 | 충족 |

## 실행과 검증

### 자동 테스트 (mock, 실제 네트워크·실제 KRX 호출 없음)

| 명령 | 결과 |
|---|---|
| `pytest` (backend/.venv) | 11 passed (health 2 + market_data 9). pykrx는 `fetch_ohlcv` mock, DB 접근은 repository mock |
| `pip freeze` → requirements.lock.txt | pykrx==1.2.8, pandas==2.3.3, numpy==2.5.3, requests==2.34.2 등 반영 |

### 실제 DB 통합 확인 (pykrx는 mock, DB는 Docker Postgres localhost)

`fetch_ohlcv`만 고정 DataFrame으로 mock하고 실제 PostgreSQL에 적재·재적재·조회했다(실제 KRX 네트워크는 사용하지 않음).

| 단계 | 결과 |
|---|---|
| 1차 수집 | status=success, returned=2, inserted=2, updated=0 |
| 2차 재수집(같은 종목·거래일, 종가만 변경) | inserted=0, updated=2 (중복 없이 갱신) |
| 조회 | 거래일 오름차순, `2024-01-02` 종가 105→107 갱신 확인 |
| 무결성 | collection_runs=2, 중복 `(종목,거래일)`=0 |

### 실제 pykrx 네트워크 조회 (수동, 미검증으로 보고)

| 명령 | 결과 |
|---|---|
| `fetch_ohlcv('005930', 2024-01-02, 2024-01-05)` 직접 호출 | pykrx 내부에서 `get_market_ohlcv_by_date` 오류(`Expecting value: line 1 column 1`) 후 빈 DataFrame(rows=0, cols=[]) 반환 |

- 현재 실행 환경에서 KRX/Naver 공개 엔드포인트가 유효한 응답(JSON)을 반환하지 않아 **실제 시장 데이터로 수집·저장을 검증하지 못했다.** 통과로 보고하지 않는다.
- 우리 코드는 이 빈 반환을 오류로 추정하지 않고 안전하게 처리한다(status=partial, failure_reason=`no_data_in_range`, 가격 행 미적재). 이는 명세의 "비거래일/빈 반환은 오류가 아니다" 및 "유효 행이 없으면 부분 성공/실패로 명확히 남긴다" 규칙과 일치한다.
- 우회(로그인·쿠키·인증 추가)는 하지 않았다(명세 준수).

## 가정과 제한

- 실제 KRX/Naver 응답을 받지 못하는 환경이라, 실데이터 기준의 컬럼명(`시가/고가/저가/종가/거래량`)·타입 매핑은 pykrx 문서·통상 스키마에 근거한 가정이다. 실데이터가 되는 환경에서 재검증이 필요하다.
- 가격은 KRW 정수라는 전제로 `int()` 캐스팅한다(비조정 원가격).
- 원본 해시는 `df.sort_index().to_csv()`의 SHA-256으로, 같은 입력에 대해 결정적이다. 원본 응답 전문은 저장·로그하지 않는다.
- 스키마는 마이그레이션 프레임워크 없이 각 DB 작업 시 `CREATE TABLE IF NOT EXISTS`로 재실행 안전하게 초기화한다.
- 설정 오류(503)·외부 실패(502)·저장 오류(500) 메시지에 환경변수 값·비밀값·연결 문자열을 넣지 않는다. `MARKET_DATA_BASE_URL/API_KEY/API_SECRET/REQUESTS_PER_MINUTE`는 수집 로직에서 읽지 않는다.
- Starlette 1.6.0에서는 `app.routes` 열거가 포함 라우터를 그대로 보여주지 않으나, 실제 라우팅은 정상이다(TestClient·pytest로 확인).

## 미해결 항목과 다음 제안

- 실제 pykrx 데이터 수집·저장 재검증: KRX/Naver 접근이 가능한 환경에서 `POST /collect`로 실종목 실기간을 수집해 완료 기준 2를 실데이터로 확정 필요.
- Docker backend 이미지에는 pandas/numpy 등 빌드가 포함된다. 이미지 크기·빌드 시간 점검은 후속 검토 대상.
- main/dev로의 병합·push는 규칙에 따라 하지 않았다. Codex 검증 후 진행.
