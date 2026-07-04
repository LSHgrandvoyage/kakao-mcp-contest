# Constitution — Agentic Player 10 MCP 서버

> 이 문서는 **협상 불가능한 제약**이다. 모든 spec / plan / tasks 는 여기에 종속된다.
> 출처: PlayMCP 서버 개발가이드(2026.06.12), 공모전 참가 방법, 참가 유의사항.
> 아래 항목 위반 시 **심사 반려**된다.

## 1. 프로토콜 제약 (HARD — 위반 시 즉시 반려)

- [ ] MCP 스펙 버전: **최소 `2025-03-26` ~ 최대 `2025-11-25`** 범위 지원
- [ ] **Streamable HTTP** 전송 방식만 사용 (SSE-only/stdio 불가)
- [ ] **Remote MCP** 서버 — 공개된 URL로 접근 가능한 도메인이어야 함
- [ ] **Stateless** 서버 권장 (no session)
- [ ] 인증이 필요하면 **OAuth 표준** 또는 **커스텀 헤더** 방식만 사용
- [ ] 네이밍: MCP Server Name / Tool Name 에 **`kakao` 사용 금지**
      (대소문자 무관, prefix·suffix·중간 포함 전부 불가)

## 2. Tool 설계 규칙 (HARD)

- [ ] 툴 개수: **3~10개 권장, 20개 초과 금지** (많을수록 tool-call 성공률 하락)
- [ ] 툴 이름: 1~128자, `[A-Za-z0-9_-]`만 허용, 중복 불가, **대소문자 구분**
- [ ] 각 툴에 필수 property 포함: `name`, `description`, `inputSchema`, `annotations`
- [ ] `annotations` 는 **5개 필드 전부 값 지정**:
      `title`, `readOnlyHint`, `destructiveHint`, `openWorldHint`, `idempotentHint`
- [ ] `description` 규칙:
  - 영문 작성 권장, **1,024자 이내**
  - 서비스(MCP) 이름을 description에 포함 — 고유명사는 **영문·국문 병기**
    (예: `Retrieves ... from Melon(멜론)`)
  - 툴 이름에는 MCP명 포함 불필요 (PlayMCP가 prefix 자동 부여)

## 3. 응답/운영 요건 (HARD)

- [ ] 응답 속도: **평균 100ms 이내, p99 3,000ms 필수**
- [ ] `result` 크기는 **최소한**으로 구성
- [ ] error / non-widget 응답은 **정제된 텍스트(마크다운 권장)** — raw API 응답 그대로 금지
- [ ] 툴 답변이 **광고 노출을 유도하면 안 됨**

## 4. OAuth (인증 사용 시에만)

- [ ] Redirect URI 설정:
      `https://playmcp.kakao.com/api/v1/applied-mcps/{mcpId}/authorize/oauth:callback`
      (`{mcpId}` = 등록 후 발급되는 MCP id)
- [ ] MCP 인증 스펙(2025-03-26 authorization flow) 준수
- [ ] 개인정보 카카오 전달 시 '개인정보 제3자 제공 동의' 화면 구성 (권장)

## 5. 검증 게이트 (구현 전/후 반드시 통과)

- [ ] **MCP Inspector** 로 표준 스펙 사전 점검 통과
- [ ] 활발히 운영되는 공식 **SDK** 사용/참조
- [ ] 로컬 환경에서 전 기능 테스트 완료 후 PlayMCP in KC 배포

## 6. 공모전 운영 상수 (참고)

- 예선 접수: **2026-06-15 ~ 2026-07-14**
- PlayMCP in KC 무상 배포도 위 기간에만 발급 가능
- 심사 소요: 통상 영업일 1~2일 (최대 7일)
- 계정당 MCP 서버 2대, 접수 양식에 최대 2개 MCP 등록 가능
- **MCP 개발 이슈는 카카오가 지원하지 않음** (자력 해결)
