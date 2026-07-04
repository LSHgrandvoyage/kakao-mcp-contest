# Kakao MCP — Agentic Player 10

카카오 **Agentic Player 10** 공모전 출품용 MCP 서버 개발 저장소.
개발은 **SDD(Spec-Driven Development)** 흐름으로 진행한다.

## SDD 흐름

```
constitution  →  spec  →  plan  →  tasks  →  implement  →  verify  →  submit
 (제약/불변)     (무엇·왜)  (어떻게)   (분해)      (구현)      (검증)     (제출)
```

1. **constitution** (`memory/constitution.md`) — 협상 불가 제약. 반려 방지 체크리스트. 항상 먼저 읽는다.
2. **spec** — `templates/spec-template.md` 복사 → `specs/NNN-<name>/spec.md`. *무엇을·왜* 만 작성.
3. **plan** — `templates/plan-template.md` 복사 → `specs/NNN-<name>/plan.md`. Constitution Check 게이트 통과 후 *어떻게* 작성.
4. **tasks** — `templates/tasks-template.md` 복사 → `specs/NNN-<name>/tasks.md`. 실행 가능한 작업으로 분해.
5. **implement / verify / submit** — tasks 순서대로 구현, 검증 게이트 통과 후 PlayMCP 등록·심사·접수.

## 디렉토리 구조

```
memory/constitution.md      # 불변 제약 (반려 조건 = HARD 룰)
templates/                  # spec/plan/tasks 템플릿
specs/NNN-<name>/           # 기능별 spec + plan + tasks
```

## 새 기능 시작

```bash
mkdir -p specs/001-<name>
cp templates/spec-template.md  specs/001-<name>/spec.md
cp templates/plan-template.md  specs/001-<name>/plan.md
cp templates/tasks-template.md specs/001-<name>/tasks.md
```

## 핵심 제약 요약 (전체는 constitution 참조)

- Streamable HTTP · Remote · 공개 URL · Stateless 권장
- 스펙 버전 `2025-03-26` ~ `2025-11-25`
- 이름에 `kakao` 금지 / 툴 3~10개 / `annotations` 5필드 전부
- description 영문·1024자·서비스명(EN/국문) 포함
- 응답 평균 ≤100ms, p99 ≤3s / 광고 유도 금지
- 예선 접수: **2026-06-15 ~ 2026-07-14**
```
