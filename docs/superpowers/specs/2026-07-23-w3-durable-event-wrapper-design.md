# W3-3 Durable event wrapper·ordering·provenance 설계

**작성일:** 2026-07-23  
**상태:** 사용자 승인 설계  
**범위:** `WBS-007`, `PRD-FR-004`, `PRD-NFR-006`, `ARC-009`, `ARC-011`, `VG-003`, `VG-004`

## 1. 목적

Protocol 2.0 canonical event를 durable stream에 기록할 때 task/run identity, 두 종류의
sequence, accepted revision, actor와 provenance를 손실 없이 보존하는 closed wrapper를
정의한다. 이 작업은 event store 또는 broker를 구현하지 않고 serialization과 ordering
계약만 제공한다.

## 2. Wrapper 구조

계약 파일은 `contracts/forgeops-event/1.0/schema.json`이다. root object는 다음 필드를
정확히 갖는다.

- `schema_id="forgeops.event"`, `schema_version="1.0"`
- `event_id`, `task_id`, `run_id`, `correlation_id`
- `stream_id`, `stream_seq`, `recorded_at`
- `accepted_revision`
- `canonical_event`
- `provenance`

`canonical_event`는 Main contract의 `seq`, `task_id`, `correlation_id`, `actor`, `phase`,
`attempt`, `severity`, `code`, `action`, `evidence_refs`를 보존한다. wrapper와 내부 event의
task/correlation identity는 ordinal exact match해야 한다. 내부 `seq`는 Main이 확정한
canonical sequence이고 `stream_seq`는 durable stream append 순서다. 둘을 서로
대체하거나 값이 같다고 가정하지 않는다.

`provenance`는 `source_kind`, `source_ref`, `content_sha256`, `recorder_id`를 갖는다.
version 1.0의 `source_kind`는 `MAIN_DECISION` constant다. Part/Work의
`event_suggestions`는 직접 저장하지 않고 Main이 검증·정규화하고 `seq`를 배정해
MainDecision에 포함한 뒤에만 wrapper 입력이 된다. 따라서 내부 event의 `actor`가
`part|work`여도 durable record의 authoritative source는 MainDecision이다.

## 3. Ordering과 revision 규칙

- `stream_seq`는 같은 `stream_id`에서 1부터 시작해 정확히 1씩 증가한다.
- duplicate, reuse, skip, 감소와 다른 run의 stream 혼합을 거부한다.
- canonical `seq`의 W2 규칙은 그대로 유지하며 durable wrapper가 새 seq를 배정하지 않는다.
- `accepted_revision`은 source MainDecision의 accepted revision과 같아야 한다.
- 같은 revision에서 여러 관찰 event가 존재할 수 있지만 state-accept event는 revision당
  하나만 허용한다.
- `recorded_at`은 strict UTC `yyyy-MM-dd'T'HH:mm:ss'Z'`이고 source가 제공하지 않은
  시간을 canonical event에 역으로 주입하지 않는다.

## 4. Payload와 민감정보 경계

wrapper는 raw prompt, request body, stdout/stderr, credential, approval token, nonce,
private payload를 담지 않는다. event가 상세 데이터를 필요로 하면 manifest가 해석할
수 있는 opaque `evidence_refs` 또는 artifact reference를 사용한다. 모든 reference는
non-empty ordinal-unique literal이고 W3-4 resolver가 같은 run 안에서 해석한다.

public-safe result에는 원문 event 대신 event ID, expected/actual verdict, sequence와 hash만
기록한다.

## 5. Stable error와 fixture

stable category는 다음과 같다.

- `EVENT_SCHEMA_INVALID`
- `EVENT_IDENTITY_MISMATCH`
- `EVENT_STREAM_OUT_OF_ORDER`
- `EVENT_CANONICAL_SEQUENCE_INVALID`
- `EVENT_REVISION_MISMATCH`
- `EVENT_OWNER_INVALID`
- `EVENT_PROVENANCE_INVALID`
- `EVENT_REFERENCE_INVALID`
- `EVENT_TIMESTAMP_INVALID`

positive fixture는 최초 append, 같은 run의 연속 append, revision 증가, Main이 정규화한
`part|work` actor event와 Main actor event를 포함한다. negative fixture는 stream reuse/skip,
canonical seq 변조, task/run/correlation 혼합, stale revision, Work의 authoritative state
event, source hash 누락, duplicate evidence reference, timestamp 형식 오류를 포함한다.

## 6. 계획된 산출물과 완료 기준

- `contracts/forgeops-event/1.0/schema.json`
- `fixtures/forgeops-event-contract/suite.json`
- `tests/interface_contract/test_event_wrapper.py`

완료 기준은 event schema와 semantic ordering 검증이 모두 통과하고 모든 negative가
manifest나 store write 전에 거부되는 것이다. 실제 durable append, broker delivery,
retention, encryption, replay execution과 WBS 상태 변경은 이 설계 범위가 아니다.
