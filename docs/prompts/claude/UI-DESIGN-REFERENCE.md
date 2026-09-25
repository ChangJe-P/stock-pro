# Claude Code 참고 프롬프트: 주몽 금융 대시보드 UI

> 이 문서는 단독 구현 지시가 아니다. 이후 UI 관련 T-XXX 구현 프롬프트의 `시작 전 필독`에 추가해 사용한다. 현재 T-XXX 작업 문서의 범위·데이터 계약·완료 기준이 항상 우선이다.

## Claude에게 전달할 프롬프트

```text
이번 작업의 UI를 구현하거나 수정하기 전에 아래 문서를 읽어줘.

1. AGENTS.md
2. docs/PROJECT_SPEC.md
3. 현재 T-XXX 작업 문서
4. 작업 문서가 참조하는 프로젝트 Skill
5. docs/UI-DESIGN-REFERENCE.md
6. C:\Users\박창제\.claude\skills\ui-ux-pro-max\SKILL.md
7. C:\Users\박창제\.claude\skills\frontend-design\SKILL.md

주몽은 실제 주문 서비스가 아니라 국내 주식 학습용 가상투자 장부다. 알파스퀘어(https://alphasquare.co.kr/)를 화면·문구·상표·이미지까지 복제하지 말고, 한 화면에서 관련 정보를 비교하기 쉬운 금융 대시보드의 정보 구조와 절제된 정보 밀도만 참고해줘.

현재 작업에 실제 데이터가 제공된 컴포넌트만 화면에 추가해줘. 미래 기능인 관심 종목, 차트, 매도, 실시간 가격, 자동 수집, 실제 주문을 빈 위젯·가짜 숫자·비활성 버튼으로 만들지 마. 작업 문서에 없는 API, 모델, migration, 외부 요청도 추가하지 마.

Django Template, semantic HTML, Django static CSS만 사용해줘. 새 프론트엔드 프레임워크, JavaScript 의존성, CSS·아이콘 library, CDN, 외부 폰트·이미지는 추가하지 마. 밝은 중립 배경, navy/blue 중심의 구조, emerald 수익·red 손실을 사용하되 수익·손실·변동 없음은 색상뿐 아니라 텍스트와 부호로 표시해줘.

화면에는 가상투자·읽기 전용 상태, 가격 기준일, 가격 출처, KRW·주·% 단위를 명확히 표시해줘. GET 화면이 가격 수집, 주문 체결, 계좌 초기화, 원장 쓰기를 시작하지 않게 유지해줘. 375px, 768px, 1024px, 1440px에서 핵심 값이 읽히도록 구현하고, 모바일에서는 표를 label이 있는 세로 행으로 바꿔 가로 스크롤에 의존하지 않게 해줘.

화면 구성, 어떤 데이터를 표시할지, 비어 있는 상태의 문구가 잘 이해되지 않거나 현재 문서만으로 결정할 수 없다면 추측해서 구현하지 말고 Codex에 먼저 질문해줘.
```

## 이후 작업 문서에 넣는 방법

UI가 포함된 T-XXX 구현 프롬프트의 `시작 전 필독` 목록에 다음 두 줄을 추가한다.

```text
- docs/UI-DESIGN-REFERENCE.md
- docs/prompts/claude/UI-DESIGN-REFERENCE.md
```

두 번째 문서는 Claude에게 전달할 문구를 담고 있다. 실제 구현 범위와 완료 조건은 반드시 해당 T-XXX 문서에 별도로 적는다.
