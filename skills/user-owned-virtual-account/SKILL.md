---
name: user-owned-virtual-account
description: Use when adding Google login, user-owned virtual accounts, legacy-account migration, or access control to Jumong's Django trading records.
---

# 사용자별 가상계좌 전환

주몽의 Google 로그인은 학습 기록을 나누기 위한 신원 확인일 뿐이다. 계좌·현금·주문·손익은 항상 가상이며, 실제 증권계좌·돈·결제·증권사 주문은 어떤 경로에도 추가하지 않는다.

## 시작 전

`AGENTS.md`, `docs/PROJECT_SPEC.md`, 현재 T-XXX 문서, `docs/ENVIRONMENT.md`, `docs/superpowers/specs/2026-10-01-google-auth-virtual-account-design.md`를 읽는다. 문서에 없는 Google OAuth·legacy·권한 결정이 필요하면 구현하지 말고 Codex에 질문한다.

## 소유권 규칙

| 데이터 | 규칙 |
|---|---|
| `VirtualAccount` | Django 사용자와 1:1. 서비스·view에서 `objects.first()`를 사용하지 않는다. |
| 현금 원장·가상 주문·포트폴리오 | 로그인 사용자의 계좌 범위로만 조회·생성·체결한다. 타 사용자의 주문 ID는 404로 처리한다. |
| `DailyPrice`, 수집 실행 기록 | 공용 읽기 데이터다. 사용자별 복제하지 않는다. |
| 기존 단일 계좌 | 자동 연결·공개 표시 금지. `INITIAL_OWNER_GOOGLE_EMAIL`과 일치하는 사용자가 확인 POST를 보낼 때 한 번만 연결한다. |

새 계좌는 로그인 후 사용자가 명시적으로 시작할 때만 기존 `VIRTUAL_*` 정책의 가상 현금을 스냅샷으로 만든다. 기존 계좌·원장·주문 행은 삭제·복제·재계산하지 않는다.

## 인증과 비밀값

- Google OAuth는 `openid`, `email`, `profile`만 요청한다. Client ID·Secret은 `.env`와 Django 설정 계층에만 둔다. DB `SocialApp`, template, 로그, response에 넣지 않는다.
- OAuth 값이 하나라도 없으면 로그인 시작을 안전하게 비활성화한다. 실제 값·길이·마스킹 값도 표시하지 않는다.
- HTML은 로그인 화면으로 이동시키고, JSON API는 `401 {"detail": "로그인이 필요합니다."}`를 반환한다. 계좌·주문·수집 POST의 `csrf_exempt`는 제거하고 CSRF를 쓴다. `/health`만 공개한다.
- KRX ID·비밀번호는 사용자 입력·DB 저장·화면 표시 대상이 아니다. 초기 소유자만 기존 pykrx 수집을 수동 요청할 수 있고, 다른 사용자는 저장된 일봉만 읽는다.

## 구현 순서

1. 인증·소유권·legacy migration의 실패 테스트를 먼저 작성하고 실패 원인을 확인한다.
2. migration으로 singleton 제약을 제거하고 owner 없는 legacy 행을 보존한다.
3. 계좌·원장·주문 서비스에 `user`를 전달해 모든 전역 조회를 소유 계좌 조회로 교체한다.
4. 화면·API에 로그인, CSRF, legacy 연결 확인, 수집 권한을 적용한다.
5. 기존 다음 거래일 시가 체결은 저장된 일봉만 읽는지 다시 검증한다.

로그인 버튼·빈 탭·가짜 시세·가짜 차트·실제 거래 UI를 먼저 만들지 않는다. 구현된 데이터와 동작이 있는 화면만 연결한다.

## 완료 전 확인

- A/B 사용자 격리, legacy 1회 연결, 비로그인 HTML/JSON, CSRF, 수집 권한, 다음 거래일 시가 체결 회귀 테스트를 실행한다.
- `manage.py test trading`, `check`, `makemigrations --check --dry-run` 결과를 인수인계에 실제 출력 기준으로 남긴다.
- 실제 Google OAuth 로그인은 사용자 설정 이후의 수동 검증으로 구분하고, Client Secret·KRX 자격증명은 절대 기록하지 않는다.
