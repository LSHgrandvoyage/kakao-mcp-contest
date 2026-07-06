# Tasks: Lease Guide(전월세 길잡이) — 예선 MVP

> plan.md 실행 분해. `[P]`=병렬 가능. 7/7 심사요청 마지노선 역산 우선순위.
> 데이터 정제 규칙은 plan §2-1b 준수(해제거래·토지임대부·월세·중복 제거).

## Phase 0 — 셋업
- [x] T000 프로젝트 초기화: `.gitignore`(`.env`·`__pycache__` 제외, `data/lease.db`는 추적), `.env.example`, `requirements.txt`, 디렉토리(`ingest/`, `data/`)
- [x] T001 [P] 국토부 API 응답 실물 검증 — 전월세/매매 aptSeq 조인·필드·해제거래 확인. 빌라 2종은 스키마 동일 가정, 라이브 실행 시 확인
- [x] T002 `.env` 로더(dotenv) + serviceKey 는 ingest 배치에서만 사용(런타임 서버 미인지)

## Phase 1 — ingest 파이프라인 (사전적재, 오프라인)
> 코드 완성 + 실물 XML 샘플로 로직 검증 완료(파싱·전세플래그·해제거래 제외·멱등성).
> `data/lease.db` 산출(T015)만 **라이브 실행 대기**(사용자가 키 넣고 `python -m ingest.run`).
- [x] T010 국토부 클라이언트(`ingest/client.py`): UA 필수, serviceKey 재인코딩 방지, 페이징, resultCode/WAF 처리
- [x] T011 정규화(`ingest/normalize.py`): 금액 만원+콤마→원, 전세 플래그, 날짜, 아파트/빌라 필드명 흡수
- [x] T012 **정제 규칙**(`normalize`+`store`): `cdealType='O'`·`landLeaseholdGbn='Y'` 분리 저장, nat_key upsert 로 해제 sticky + 멱등 dedup
- [x] T013 SQLite 적재(`ingest/store.py`): `transactions` 통합 테이블(타입 컬럼) + 인덱스(building_key/면적/umd)
- [x] T014 시세 사전집계: `(building_key, 면적버킷)` 매매가 중앙값 + 표본수 → `price_stats` (해제·토지임대부 제외)
- [ ] T015 `data/lease.db` 산출물 생성 + 커밋 (예선 단일 스냅샷) ← **라이브 실행 대기**

## Phase 2 — 도메인 로직 (외부 API 무관, 단위 테스트 대상)
> `domain/policy.py` 순수 함수로 구현, `tests/test_policy.py` 6종 통과.
> 실데이터 검증: 아파트 전세 66.7%/빌라 9.9% 시세매칭 → 빌라 저신뢰 가설 확인.
- [~] T020 전세가율 계산: `assess()`가 deposit÷중앙값+신뢰도 산출. **주소→building_key 조회(repository)만 남음** → Phase 4 연결 시
- [x] T021 위험구간 판정: `classify_zone` 임계값 설정 분리(80/70%), "안전" 단정 금지·신호 언어·확인항목
- [x] T022 [P] 빌라 시세 신뢰도: `classify_confidence` 빌라 한 등급 하향(최대 보통) + 저신뢰 안내
- [x] T023 [P] 단위 테스트: 전세가율·구간·신뢰도·"안전 미단정"·시세없음 UNKNOWN·면책 (6종)

## Phase 2b — 마켓 데이터 조회 (repository, lease.db 접근) ✅
> `domain/repository.py`(조회) + `domain/service.py`(조합). 실 lease.db 로 end-to-end 검증:
> 까치마을 34㎡→전세가율 23.4%(신뢰 high), 빌라→69.5%(신뢰 medium 상한), 미매칭→UNKNOWN.
- [x] T024 단지명+동 → building_key 해소 (정규화: 괄호·'아파트'·공백 제거, 거래多 우선)
- [x] T025 building_key + 면적버킷(±1 폴백) → price_stats 중앙값·표본수 (read-only, 인덱스)

## Phase 3 — 임대인 리스크 (차별화 · 갈림길)
- [~] T030 갈림길: 공개명단 API 수집은 미확인 → **대안 사다리 2순위 채택**.
  diagnose 의 확인항목에 **"임대인 미납국세 열람권 안내"를 상시 포함**(제품 원칙과 정합).
  watchlist 적재는 본선 확장으로 이관.

## Phase 4 — MCP 서버 (tool 3개) ✅
> `server/app.py`(FastMCP streamable-http) + `server/content.py`(정적 콘텐츠).
> FastMCP in-memory 클라이언트로 3종 호출 검증 + 헌법 체크(annotations 5필드·금지어·1024자·병기) 통과.
- [x] T040 FastMCP `streamable-http` 서버, lease.db read-only 요청마다 오픈(무상태·스레드안전)
- [x] T041 `diagnose_lease_risk` — 영문 description(병기)·inputSchema(A안)·annotations 5필드·마크다운·면책
- [x] T042 [P] `get_stage_checklist` — 6단계 정적 콘텐츠
- [x] T043 [P] `generate_contract_clauses` — 상황 키워드 → 특약 선별 + 이유 + 면책
- [x] T044 커버리지 밖/미매칭 → 에러 아닌 "강남구만 지원" 안내(UNKNOWN 경로)

## Phase 5 — 검증 게이트 (헌법)
- [ ] T050 **MCP Inspector** 표준 스펙 점검 통과 ← **사용자 직접(로컬 서버 대상)**
- [x] T051 성능 측정: **평균 3.87ms / p99 5.12ms** (요건 100ms/3000ms 대비 20배 여유)
- [x] T052 [P] 네이밍 `kakao` 금지어 스캔 — 통과(in-memory 클라이언트 assert)
- [x] T053 [P] description 1,024자·영문·서비스명 병기 검증 — 3종 통과
- [x] T054 로컬 전 기능 시나리오 테스트 — 3 tool + 대표 시나리오 + UNKNOWN 경로

## Phase 6 — 배포/제출 (7/7 마지노선)
- [x] T060 `Dockerfile`(루트, linux/amd64 명시) + `.dockerignore` — lease.db COPY, serviceKey 미포함, 서버 부팅 확인
- [ ] T061 PlayMCP in KC → **Git 소스 빌드**(프라이빗 + fine-grained PAT) → Endpoint URL 획득 ← 사용자
- [ ] T062 PlayMCP 콘솔 "임시 등록" → 도구함 추가 → AI채팅 테스트 ← 사용자
- [ ] T063 **심사 요청** (7/7까지) → 승인 후 "전체 공개" 전환 → MCP URL 복사 ← 사용자
- [ ] T064 공모전 페이지 "Player 예선 참여" 접수 (7/14 마감, 제출 1회) ← 사용자

## 시간 부족 시 컷 순서 (tool 개수는 유지 — 서사)
1. T030 실패 시 미납국세 안내로 대체(기능 유지)
2. 빌라 커버리지 축소(아파트 우선)
3. 위험구간 판정 정교함 축소(임계값 단순화)

## Phase 7 — 본선 확장 (예선 제출 이후) ✅
> spec §8 / plan §7. tool 3개 유지, `diagnose_lease_risk` 강화. 회귀 통과(policy 7종·서버 3종·성능).
- [x] T070 등기정보광장 클라이언트 `ingest/iros_client.py` — 임차권등기명령(id 0000000079) JSON 파싱(실물 검증)
- [x] T071 지역위험 도메인 `domain/area.py` — 최근3 vs 직전3 추세(RISING/FLAT/FALLING), 순수+테스트
- [x] T072 `store.area_risk` 테이블 + `run.py` 지역위험 적재(선택, 키 없으면 생략) — 강남구 12개월
- [x] T073 diagnose 통합 — 렌더에 '지역 신호(강남구 전체)' 섹션, 미적재 시 graceful 생략
- [x] T074 근저당 입력 `senior_debt`·`senior_deposit` → `secured_ratio` 계산(`policy.assess`)
- [x] T075 낙찰가율(B) 주의 출력 고지 + 근저당 미입력 시 안내 nudge
- [x] T076 테스트 `test_senior_debt_flips_zone` + 실데이터 데모(근저당 8억 → LOW→CAUTION 뒤집힘)
- [ ] T077 재배포(본선용) — 커밋 → PlayMCP in KC 재빌드 ← 사용자
- 남은 숙제(본선): 개별 근저당 자동조회(유료 벽), 지역 확대, 강제경매 지표 추가, Kakao Tools 위젯
