# Plan: <기능/서비스 이름>

> **어떻게** 만드는지. spec.md 를 입력으로 받는다.
> 시작 전 **Constitution Check** 를 통과해야 한다.

## 0. Constitution Check (게이트 — 실패 시 plan 진행 불가)
- [ ] 전송: Streamable HTTP · Remote · 공개 URL (§1)
- [ ] Stateless 설계 (§1)
- [ ] 네이밍에 `kakao` 없음 (§1)
- [ ] 툴 3~10개, 각 툴 `annotations` 5필드 전부 지정 (§2)
- [ ] 응답 평균 100ms / p99 3s 달성 가능한 구조 (§3)
- [ ] 인증 사용 시 OAuth redirect URI 규격 반영 (§4)

## 1. 기술 스택
- 언어/런타임:
- MCP SDK (공식): <!-- constitution §5: 활발히 운영되는 SDK -->
- 배포 방식: PlayMCP in KC — [ ] Git 소스 / [ ] 컨테이너 이미지
- 로컬 개발/테스트 도구: MCP Inspector

## 2. 아키텍처
- 요청 흐름 (client → MCP → 외부 API → 응답):
- Stateless 보장 방법:
- 에러 처리 & 응답 정제(마크다운) 전략:

## 3. Tool 상세 설계
> 각 툴별로 아래를 확정. description은 영문·1024자 이내·서비스명(EN/국문) 포함.

### `exampleTool`
- description (영문):
- inputSchema (필드/타입/필수):
- output (정제 형태):
- annotations: `title` / `readOnlyHint` / `destructiveHint` / `openWorldHint` / `idempotentHint`

## 4. 성능 계획
- 평균 100ms / p99 3s 를 위한 조치 (캐싱·타임아웃·페이로드 축소):

## 5. 리스크 & 완화
- 반려 위험 포인트:
