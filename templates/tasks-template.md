# Tasks: <기능/서비스 이름>

> plan.md 를 실행 가능한 작업으로 분해. 각 작업은 독립 검증 가능해야 함.
> `[P]` = 병렬 가능. 순서 의존 있으면 표기 생략.

## Phase 0 — 셋업
- [ ] T001 프로젝트 초기화 (SDK 설치, 런타임 세팅)
- [ ] T002 MCP Inspector 로컬 연결 확인

## Phase 1 — 코어 구현
- [ ] T010 Streamable HTTP 엔드포인트 구성 (stateless)
- [ ] T011 `initialize` / 프로토콜 버전 협상 (2025-03-26 ~ 2025-11-25)
- [ ] T012 [P] 툴 스키마 정의 (name/description/inputSchema/annotations 전 필드)

## Phase 2 — 툴별 구현
- [ ] T020 `<tool>` 구현 + 응답 정제(마크다운)
- [ ] T021 [P] `<tool>` 단위 테스트

## Phase 3 — 인증 (해당 시)
- [ ] T030 OAuth 플로우 + redirect URI 규격 적용

## Phase 4 — 검증 게이트
- [ ] T040 MCP Inspector 스펙 점검 통과
- [ ] T041 성능 측정: 평균 ≤100ms, p99 ≤3s
- [ ] T042 네이밍/`kakao` 금지어 스캔
- [ ] T043 로컬 전 기능 시나리오 테스트

## Phase 5 — 배포/제출
- [ ] T050 PlayMCP in KC 배포 → Endpoint URL 획득
- [ ] T051 PlayMCP 콘솔 "임시 등록" → 도구함 추가 → AI채팅 테스트
- [ ] T052 "심사 요청" → 승인 후 "전체 공개" 전환
- [ ] T053 공모전 페이지 "Player 예선 참여" 접수
