# Tasks: Lease Guide(전월세 길잡이) — 예선 MVP

> plan.md 실행 분해. `[P]`=병렬 가능. 7/7 심사요청 마지노선 역산 우선순위.
> 데이터 정제 규칙은 plan §2-1b 준수(해제거래·토지임대부·월세·중복 제거).

## Phase 0 — 셋업
- [ ] T000 프로젝트 초기화: Python 3.11+, FastMCP, `.gitignore`(`.env`, `__pycache__`, `*.db`는 예외 관리), 디렉토리(`server/`, `ingest/`, `domain/`, `data/`, `tests/`)
- [ ] T001 [P] 국토부 API 응답 실물 검증 — **완료** (전월세/매매 aptSeq 조인·필드·해제거래 확인). 빌라 2종은 스키마 동일 가정, ingest 시 확인
- [ ] T002 `.env` 로더 + serviceKey 로컬 보관(레포/이미지 유입 금지 검증)

## Phase 1 — ingest 파이프라인 (사전적재, 오프라인)
- [ ] T010 국토부 클라이언트: `-A` User-Agent 필수, LAWD_CD=11680 × 최근6개월 × 4 API, XML 파싱, 방어적 결측 처리
- [ ] T011 정규화: 금액(만원+콤마→원), `monthlyRent=0` 전세 플래그, 날짜 조합, 지번/도로명 정리
- [ ] T012 **정제 규칙 적용**(plan §2-1b): `cdealType='O'` 제외 · `landLeaseholdGbn='Y'` 제외 · 중복 dedup
- [ ] T013 SQLite 적재: `apt_trade`, `apt_rent`, `villa_trade`, `villa_rent` + **인덱스**(aptSeq, 면적, umdNm)
- [ ] T014 시세 사전집계: `(aptSeq, 면적버킷)` 매매가 중앙값 + 비교건수 → `price_stats`
- [ ] T015 `data/lease.db` 산출물 생성 + 커밋 (예선 단일 스냅샷)

## Phase 2 — 도메인 로직 (외부 API 무관, 단위 테스트 대상)
- [ ] T020 전세가율 계산: 전세 deposit ÷ `price_stats` 중앙값. 비교건수 기반 **신뢰도 등급**
- [ ] T021 위험구간 판정: 임계값 **설정 분리**(하드코딩 금지). "안전" 단정 금지, 신호+확인항목만
- [ ] T022 [P] 빌라 시세 신뢰도: 비교거래 희소 시 "신뢰도 낮음" 명시 로직
- [ ] T023 [P] 단위 테스트: 금액 파싱, 전세가율, 신뢰도, "안전 단정 미출력" 검증

## Phase 3 — 임대인 리스크 (차별화 · 갈림길)
- [ ] T030 **안심전세포털 악성임대인 공개명단 수집 가능성 확인** (API/명단 형태) — 갈림길
  - 가능 → `landlord_watchlist` 적재 + 대조
  - 불가 → **"임대인 미납국세 열람권 안내"로 대체**(plan §5-1 대안 사다리). diagnose 출력에서 조회필드 비우고 안내 제공

## Phase 4 — MCP 서버 (tool 3개)
- [ ] T040 FastMCP `streamable-http` 서버 스캐폴드, `data/lease.db` read-only 오픈, stateless
- [ ] T041 `diagnose_lease_risk` — 영문 description(서비스명 병기)·inputSchema·**annotations 5필드**·마크다운 출력·면책
- [ ] T042 [P] `get_stage_checklist` — 6단계 정적 콘텐츠 + 출력
- [ ] T043 [P] `generate_contract_clauses` — 특약 후보+이유+면책(정적)
- [ ] T044 커버리지 밖 주소 → 에러 아닌 "강남구만 지원" 안내

## Phase 5 — 검증 게이트 (헌법)
- [ ] T050 **MCP Inspector** 표준 스펙 점검 통과
- [ ] T051 성능 측정: 평균 ≤100ms / p99 ≤3s (로컬 조회 경로)
- [ ] T052 [P] 네이밍 `kakao` 금지어 스캔(서버명·툴명)
- [ ] T053 [P] description 1,024자·영문·서비스명 병기 검증
- [ ] T054 로컬 전 기능 시나리오 테스트(spec §2 대표 3건)

## Phase 6 — 배포/제출 (7/7 마지노선)
- [ ] T060 `Dockerfile`(루트, linux/amd64 호환) — `data/lease.db` COPY, serviceKey 미포함 확인
- [ ] T061 PlayMCP in KC → **Git 소스 빌드**(프라이빗 + fine-grained PAT) → Endpoint URL 획득
- [ ] T062 PlayMCP 콘솔 "임시 등록" → 도구함 추가 → AI채팅 테스트
- [ ] T063 **심사 요청** (7/7까지) → 승인 후 "전체 공개" 전환 → MCP URL 복사
- [ ] T064 공모전 페이지 "Player 예선 참여" 접수 (7/14 마감, 제출 1회)

## 시간 부족 시 컷 순서 (tool 개수는 유지 — 서사)
1. T030 실패 시 미납국세 안내로 대체(기능 유지)
2. 빌라 커버리지 축소(아파트 우선)
3. 위험구간 판정 정교함 축소(임계값 단순화)
