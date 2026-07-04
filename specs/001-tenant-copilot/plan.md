# Plan: Lease Guide(전월세 길잡이) — 예선 MVP

> **어떻게** 만드는지. 입력: `spec.md`. 상위: `memory/constitution.md`(우선).
> 핵심 설계 원칙: **사전적재(§3-1)** — 요청 핫패스에 외부 호출 0.

## 0. Constitution Check (게이트 — 통과 확인)
- [x] 전송: Streamable HTTP · Remote · 공개 URL (§1) — FastMCP `streamable-http` 트랜스포트
- [x] Stateless 설계 (§1) — 무세션, 요청마다 자기완결. 로컬 DB는 read-only 오픈
- [x] 네이밍에 `kakao` 없음 (§1) — 서버명/툴명 확인
- [x] 툴 3개, 각 툴 `annotations` 5필드 전부 지정 (§2) — §3 참조
- [x] 응답 평균 100ms / p99 3s (§3) — 요청 시 **로컬 SQLite 조회만**, 외부 API는 오프라인 적재
- [x] 사전적재 원칙 (§3-1) — ingest 배치가 외부 호출 전담, 서버는 로컬만
- [x] 인증 (§4) — MVP 개인정보 미취급 → OAuth 미적용

## 1. 기술 스택
- **언어/런타임**: Python 3.11+
- **MCP SDK**: **FastMCP** (활발히 운영, 헌법 §5) — `streamable-http` 모드로 remote 서빙
- **로컬 데이터스토어**: **SQLite** 단일 파일 (`data/lease.db`) — 임베디드, 인덱스, 이미지에 동봉
- **데이터 수집**: 별도 `ingest/` 배치 스크립트 (국토부 4 API → 파싱 → SQLite 적재)
- **배포**: PlayMCP in KC — [x] **Git 소스 빌드** (프라이빗 레포 + fine-grained PAT)
  - 레포 루트 `Dockerfile` 필수. `linux/amd64` (Git 빌드는 카카오가 처리하나 이미지 방식 폴백 대비 명시)
- **로컬 개발/테스트**: MCP Inspector (헌법 §5 게이트)

### 1-1. 키(serviceKey) 취급 — 중요
- serviceKey는 **`ingest` 배치에서만** 사용. 로컬 `.env`(→ `.gitignore`)에 보관.
- **런타임 서버는 serviceKey를 모름** (로컬 DB만 읽음) → 이미지/레포에 키가 절대 안 들어감.
- 흐름: `.env`의 키로 로컬에서 `ingest` 실행 → `data/lease.db` 생성 → **DB 아티팩트를 커밋** →
  Dockerfile이 COPY → 서버가 read-only 조회. (예선은 단일 스냅샷으로 충분, 갱신은 재적재·재커밋)

## 2. 아키텍처

**2개 컴포넌트로 분리 (사전적재 원칙의 물리적 구현)**

```
[오프라인]  ingest 배치 ──국토부 4 API(강남구 11680 × 최근6개월)──▶ data/lease.db
                                                                       │ (커밋 → 이미지 동봉)
[런타임]    MCP client ──streamable-http──▶ FastMCP 서버 ──read-only──▶ data/lease.db
                                             (외부호출 0, 로컬조회만)
```

- **요청 흐름**: client → tool 호출 → SQLite 인덱스 조회 → 도메인 로직(위험구간 판정) → 마크다운 정제 → 반환. **외부 네트워크 호출 없음.**
- **Stateless 보장**: 세션 없음. SQLite는 read-only 커넥션, 요청 간 상태 공유 없음.
- **에러/정제 전략**: 모든 출력은 정제된 텍스트(마크다운) + 구조화 필드. raw API 응답 노출 금지(헌법 §3). 커버리지 밖 주소 → 에러 아닌 **안내 메시지**.

### 2-1. ingest 파이프라인 (오프라인)
1. `LAWD_CD=11680` × 최근 6개월(`YYYYMM` 6개) × **4 API** = 24 호출 (개발계정 일 10,000 한도 내)
2. XML 파싱 → 정규화(결측 층·건축년도 처리, 금액 문자열→정수, 지번/도로명 정리)
3. 테이블 적재: `apt_trade`, `apt_rent`, `villa_trade`, `villa_rent`
4. **시세 집계 사전계산**: (단지/건물 + 전용면적 버킷)별 매매가 중앙값 + 비교 거래 건수 → `price_stats`
5. **인덱스**: 지번/단지명/전용면적 조회 키
6. HUG 악성임대인 명단 적재 → `landlord_watchlist` (⚠️ §5 리스크 참조)

### 2-1a. 확인된 데이터 계약 — 아파트 전월세 (실물 검증 완료, 202605 강남구)
> 응답 포맷: XML `<response><body><items><item>…`. resultCode `000`=OK. `totalCount`로 페이징.

| 필드 | 의미 | 파싱 규칙 |
|---|---|---|
| `aptSeq` | **단지 식별자** (예 `11680-279`) | ⭐ **매매↔전월세 조인 키.** 시군구코드-단지일련 |
| `aptNm` | 아파트명 | 표시용 |
| `excluUseAr` | 전용면적(㎡) | 실수. **면적 버킷 매칭 키** |
| `deposit` | 보증금 | **단위 만원 + 콤마 문자열** → `,` 제거 후 ×10,000 = 원. (예 `67,200`=6.72억) |
| `monthlyRent` | 월세(만원) | **`0`=전세, >0=월세/반전세.** 전세가율은 `monthlyRent=0`만 사용 |
| `dealYear/dealMonth/dealDay` | 계약일 | 정수 조합 |
| `buildYear` | 건축년도 | 결측 가능 |
| `floor` | 층 | 결측 가능 |
| `jibun` | 지번 | 주소 매칭 보조 |
| `umdNm` | 읍면동(예 개포동) | 주소 매칭 |
| `roadnm` | 도로명 | 주소 매칭 보조 |
| `contractType`/`preDeposit`/`preMonthlyRent`/`contractTerm` | 갱신 여부·종전 조건 | 신규 계약은 공백. MVP 미사용(본선 갱신분석용) |

### 2-1b. 확인된 데이터 계약 — 아파트 매매 상세 (실물 검증 완료, 202605 강남구)
| 필드 | 의미 | 파싱 규칙 |
|---|---|---|
| `aptSeq` | **단지 식별자** (예 `11680-316`) | ⭐ 전월세와 **동일 키 확인됨** → 조인 확정 |
| `dealAmount` | 매매가 | **만원 + 콤마** → ×10,000 = 원. (예 `230,000`=23억) |
| `excluUseAr` | 전용면적(㎡) | 면적 버킷 매칭 키 |
| `aptNm` | 아파트명 | 표시용 |
| `cdealType` / `cdealDay` | **해제 여부 / 해제일** | ⚠️ `cdealType='O'` = **해제(취소)된 거래** → **시세 집계에서 제외 필수** |
| `dealingGbn` | 중개/직거래 | MVP 참고용 |
| `landLeaseholdGbn` | 토지임대부 여부 | `Y`면 시세 왜곡 → 집계 제외 권장 |
| `buildYear`/`floor`/`aptDong` | 건축년도·층·동 | 결측 가능 |

**핵심 설계 이점 (확정)**: `aptSeq`가 매매·전월세 공통 단지키 → **아파트 전세가율은 `(aptSeq, 면적버킷)` 조인으로 산출** (주소 문자열 매칭 리스크 우회, plan §5-3 완화).
- 전세가율 = `전세 deposit(원)` ÷ `같은 (aptSeq, 면적버킷) 매매가 중앙값(원)`

**⚠️ 데이터 정제 규칙 (실물에서 발견 — 반드시 적용)**:
1. **해제거래 제외**: `cdealType='O'` 건은 시세 median에서 제외. (실물에서 동일 거래가 원본+해제본 **중복**으로 옴 → 미제거 시 시세 왜곡)
2. **토지임대부 제외**: `landLeaseholdGbn='Y'` 집계 제외.
3. **월세 제외**: 전월세에서 `monthlyRent>0` 은 전세가율 분자에서 제외.
4. **중복 제거**: (aptSeq, 면적, 층, 계약일, 금액) 기준 dedup.

### 2-2. 아키텍처 원칙 (브리프 §7 반영)
- 데이터 소스별 **추상 인터페이스**(실거래·건축물대장·명단) 뒤에 배치. 진단 로직은 추상에만 의존(DIP).
- 위험구간 임계값(전세가율 등)은 **설정으로 분리**(하드코딩 금지) → OCP.
- 도메인 로직(위험 판정)은 데이터 계층과 분리해 **단위 테스트 가능**하게.

## 3. Tool 상세 설계
> description은 영문·1024자 이내·서비스명 `Lease Guide(전월세 길잡이)` 포함. 3개 모두 read-only·non-destructive.

### `diagnose_lease_risk`
- **description (영문)**:
  "Analyzes lease risk signals for a rental home in Gangnam-gu, Seoul with Lease Guide(전월세 길잡이). Given an address, deposit, and property type, it computes the jeonse-to-sale-price ratio from recent real-transaction data (Ministry of Land/국토부) and returns risk-zone indicators, price-estimate confidence with comparable-transaction counts, items to verify on the property register(등기부등본), and a malicious-landlord watchlist(HUG 악성임대인) check. It never declares a property 'safe'; it surfaces risk signals and next verification steps only. Preliminary screening, not legal advice."
- **inputSchema**:
  - `address` (string, required) — 강남구 내 주소
  - `deposit` (integer, required) — 보증금(원)
  - `property_type` (enum `apartment`|`villa`, required)
  - `monthly_rent` (integer, optional) — 반전세 월세(원)
- **output (구조화 + 마크다운)**: `jeonse_ratio`, `risk_zone`(안전구간 아님·주의/위험 신호), `price_confidence`(level + 비교건수), `register_check_items[]`, `landlord_watchlist_hit`(bool+근거), `disclaimer`
- **annotations**: title=`Lease Risk Diagnosis` / readOnlyHint=`true` / destructiveHint=`false` / openWorldHint=`false`(로컬 폐쇄 데이터) / idempotentHint=`true`

### `get_stage_checklist`
- **description (영문)**:
  "Provides a stage-specific action checklist for the tenant lease lifecycle with Lease Guide(전월세 길잡이). Given a lifecycle stage (property search, before contract, contract day, balance/move-in day, during residence, near expiry), it returns the ordered actions and verification items for that moment — e.g., on balance-payment day, complete resident registration(전입신고) and fixed-date stamp(확정일자) immediately, since that ordering determines when opposing power(대항력) takes effect."
- **inputSchema**:
  - `stage` (enum `property_search`|`before_contract`|`contract_day`|`movein_day`|`during_residence`|`near_expiry`, required)
  - `context` (string, optional) — 상황 옵션
- **output**: `stage`, `ordered_actions[]`, `verify_items[]`, `notes`
- **annotations**: title=`Lease Stage Checklist` / readOnlyHint=`true` / destructiveHint=`false` / openWorldHint=`false` / idempotentHint=`true`

### `generate_contract_clauses`
- **description (영문)**:
  "Suggests special-agreement clause(특약) candidates for a lease contract with Lease Guide(전월세 길잡이). Given a described situation (e.g., newly built villa, existing senior mortgage(근저당), corporate landlord), it returns candidate clause texts with the reason each is needed. Output always includes a disclaimer that this is not legal advice and the tenant should consult a licensed real-estate agent(공인중개사)."
- **inputSchema**:
  - `situation` (string, required) — 자연어 상황 서술
- **output**: `clauses[]`(text + why), `disclaimer`
- **annotations**: title=`Contract Clause Suggestions` / readOnlyHint=`true` / destructiveHint=`false` / openWorldHint=`false` / idempotentHint=`true`

## 4. 성능 계획 (평균 ≤100ms / p99 ≤3s)
- **요청 시 외부 호출 0** — 로컬 SQLite만 → 조회 단건 수 ms
- **인덱스**: 지번/단지/전용면적 키 (풀스캔 금지)
- **시세 집계 사전계산**(`price_stats`) → 요청 시 재계산 없이 조회
- **정적 tool 2개**는 상수/문서 로딩 → <10ms (평균을 끌어내림)
- **콜드 스타트**(p99 영역): 컨테이너 워밍/최소 인스턴스 유지로 3s 내 보장
- **payload 최소화**: result에 필수 필드만(헌법 §3)

## 5. 리스크 & 완화 (반려/품질 위험)
1. **HUG 악성임대인 데이터 접근** — 깔끔한 오픈 API가 없을 수 있음(안심전세포털 공개 명단).
   → **완화**: 공개 명단을 오프라인 적재. API 부재 시 MVP는 "명단 대조 미지원"으로 **정직하게 축소**하고
   diagnose 출력에서 해당 필드를 명시적으로 비움(과장 금지). **본선 확장으로 이관 가능.** ⚠️ 조기 확인 필요.
2. **빌라 시세 신뢰도** — 비교 매매 희소 → 전세가율 신뢰도 낮음. spec §6 대로 **"신뢰도 낮음" 명시**로 대응(리스크가 아니라 정직성 = 가점).
3. **주소 매칭**(지번 vs 도로명, 신축 미등재) — 국토부는 지번 기반. → 지번 정규화 + 미매칭 시 안내.
4. **API 필드 결측/개정** — 층·건축년도 공백 흔함, 오퍼레이션명 개정 이력. → ingest에 방어적 파싱 + **T001에서 실제 응답 1건 검증 선행**.
5. **콜드 스타트로 p99 초과** — §4 워밍으로 완화, MCP Inspector로 측정.
6. **"안전 판정" 유출** — 출력 카피에서 단정 표현 금지 룰을 코드/템플릿에 강제(테스트로 검증).

## 6. tasks 진행 시 우선순위 (7/7 마지노선 역산)
① 국토부 API 응답 실물 검증(T001) → ② ingest 파이프라인 + lease.db → ③ `diagnose_lease_risk`
→ ④ `get_stage_checklist` → ⑤ `generate_contract_clauses` → ⑥ Dockerfile + 배포 → ⑦ 임시등록 테스트 → ⑧ 심사요청
- 시간 부족 시 컷: HUG 명단(리스크1) → 빌라 커버리지 순. **tool 개수는 유지**(서사).
