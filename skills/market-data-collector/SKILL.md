---
name: market-data-collector
description: Collect and validate approved Korean stock market data for Jumong, recording provenance and data-quality evidence. Use after a data source and storage task are approved; do not use for actual trading or unapproved scraping.
---

# 주몽 시장 데이터 수집

## 목적

승인된 데이터 소스에서 국내 주식 데이터를 수집하고, 원본·정제 결과·출처·품질 검증 결과를 재현 가능하게 남긴다.

## 시작 전 확인

- 현재 작업 문서에 데이터 소스, 이용 조건, 종목 범위, 기간, 저장 대상이 명시되어 있는지 확인한다.
- 데이터 소스가 승인되지 않았거나 이용 조건이 불명확하면 수집·크롤링을 시작하지 않는다. Codex에 결정이 필요한 항목으로 보고한다.
- 실제 주문·계좌·자동매매 API는 호출하지 않는다.

## 필수 기록

각 수집 실행에는 최소한 아래 정보를 남긴다.

- 데이터 소스와 조회 기준 시각
- 종목 코드, 시장, 요청 기간
- 원본 응답 위치 또는 해시
- 수집·정제 규칙의 버전
- 성공·실패 상태와 실패 사유

## 검증

- 종목·거래일 중복을 검사한다.
- 결측 거래일, 휴장일, 0 또는 음수 가격, 고가·저가·시가·종가 관계를 검사한다.
- 조정 여부와 기업행동 반영 여부를 구분해 기록한다.
- 데이터가 최신이라고 추정하지 않는다. 마지막 정상 데이터의 기준 시각을 결과에 포함한다.

## 출력

작업 결과에는 적재 건수뿐 아니라 제외·보류한 데이터와 그 이유를 포함한다. 검증하지 못한 데이터 품질 조건은 통과로 표시하지 않는다.
