# W3-4 Run manifest·artifact/evidence reference 설계

**작성일:** 2026-07-23  
**상태:** 사용자 승인 설계  
**범위:** `WBS-008`, `PRD-FR-004`, `PRD-NFR-004`, `PRD-NFR-006`, `ARC-011`, `VG-004`, `VG-023`

## 1. 목적

하나의 run을 재구성하는 데 필요한 identity, 상태, event range, input provenance,
artifact와 evidence reference를 closed manifest로 정의한다. manifest는 데이터 본문을
저장하는 container가 아니라 immutable reference와 무결성 metadata의 index다.

## 2. Manifest 구조

계약 파일은 `contracts/forgeops-run-manifest/1.0/schema.json`이다. root는 다음을 갖는다.

- `schema_id="forgeops.run-manifest"`, `schema_version="1.0"`
- `manifest_id`, `manifest_version`
- `task_id`, `run_id`, `correlation_id`, `run_mode`
- `status`, `accepted_revision`
- `source_contract`, `event_stream`
- `artifacts`, `evidence`, `decision_refs`
- `created_at`, `finalized_at`, `manifest_sha256`

`run_mode`는 최초 실행의 `PRIMARY`와 W2 replay contract의
`AUDIT_REPLAY|COUNTERFACTUAL|REEXECUTE`를 합친 closed enum이다. replay mode의 의미와
재승인 규칙은 W2 계약을 그대로 따른다. terminal manifest의 `status`는 canonical
terminal state와 일치해야 하며 non-terminal snapshot은
`finalized_at`과 terminal decision reference를 가질 수 없다.

`source_contract`는 Product Task Contract의 `artifact_id`, `artifact_version`,
`content_sha256`을 갖는다. `event_stream`은 `stream_id`, `first_seq`, `last_seq`, `count`,
`content_sha256`을 갖고 count는 inclusive sequence range와 일치해야 한다.

`manifest_sha256`은 `manifest_sha256` field 자체를 제외한 canonical JSON serialization의
SHA-256이다. field 순서나 host별 newline 차이로 다른 hash를 만들지 않도록 key 정렬과
UTF-8 no-BOM serialization을 계약에 포함한다.

## 3. Artifact와 evidence reference

artifact record는 `artifact_id`, `artifact_version`, `kind`, `content_sha256`,
`media_type`, `classification`, `producer_event_seq`를 갖는다. `kind`과
`classification`은 closed enum이며 raw content나 외부 URL을 담지 않는다.

evidence record는 `evidence_id`, `tier`, `type`, `source_ref`, `producer_event_seq`와
freshness union을 갖는다. `file|diff`는 `observed_revision`만 요구하고 `observed_at`을
금지한다. `command|test|render|runtime|approval`은 strict UTC `observed_at`만 요구하고
`observed_revision`을 금지한다. 이 규칙은 Main/Work evidence 의미를 재정의하지 않는다.

`decision_refs`는 terminal criterion과 candidate가 참조한 evidence/artifact ID만
나열한다. 모든 reference는 같은 manifest catalog에서 정확히 한 번 해석되어야 한다.
duplicate ID, dangling reference, cross-run source, sequence range 밖 producer,
content hash 누락과 freshness wrong-mode를 거부한다.

## 4. 민감정보와 portability

`classification`은 `PUBLIC|INTERNAL|PRIVATE|SECRET` closed enum이다. PRIVATE 또는
SECRET record도 manifest에는 opaque identity와 hash만 존재하며 원문, credential,
tenant identifier 또는 signed URL을 담지 않는다. encryption, retention, deletion과
tenant access enforcement는 후속 runtime gate가 담당하고 W3는 이를 통과했다고
선언하지 않는다.

`source_ref`는 canonical project-root-relative literal 또는 ForgeOps-owned opaque URN만
허용한다. absolute path, parent traversal, backslash, wildcard, query와 fragment를
거부한다. host별 path normalization으로 reference 일치를 만들지 않는다.

## 5. Stable error와 fixture

- `MANIFEST_SCHEMA_INVALID`
- `MANIFEST_IDENTITY_MISMATCH`
- `MANIFEST_MODE_INVALID`
- `MANIFEST_EVENT_RANGE_INVALID`
- `MANIFEST_ID_DUPLICATE`
- `MANIFEST_REFERENCE_DANGLING`
- `MANIFEST_REFERENCE_CROSS_RUN`
- `MANIFEST_PRODUCER_SEQUENCE_INVALID`
- `MANIFEST_EVIDENCE_FRESHNESS_INVALID`
- `MANIFEST_HASH_INVALID`
- `MANIFEST_SENSITIVE_CONTENT_FORBIDDEN`

positive fixture는 primary terminal run, non-terminal snapshot, audit replay와
counterfactual manifest, revision/time evidence union을 포함한다. negative fixture는
duplicate·dangling·wrong-mode reference, event count mismatch, cross-task/run reference,
producer sequence range 이탈, hash 누락/형식 오류, terminal/finalized 불일치, raw secret
field와 absolute path를 포함한다.

## 6. 계획된 산출물과 완료 기준

- `contracts/forgeops-run-manifest/1.0/schema.json`
- `fixtures/forgeops-run-manifest/suite.json`
- `tests/interface_contract/test_run_manifest.py`

완료 기준은 schema validation 이후 semantic resolver가 모든 reference를 exact하게
해석하고 negative case를 stable category로 거부하는 것이다. artifact store, encryption,
retention, deletion, tenant runtime과 실제 hash storage는 포함하지 않는다.
