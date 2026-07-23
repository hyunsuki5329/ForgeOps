# W2-3 RESOURCE 권한·보호 읽기 설계

**작성일:** 2026-07-22  
**상태:** 사용자 승인 설계  
**범위:** `WBS-005`의 RESOURCE exact authority 및 protected-read gate, `VG-005`

## 1. 목적

RESOURCE 권한은 canonical project-root-relative literal과 closed scope/list
조합으로만 판단한다. 이 작업은 protected resource, credential, private data가
exact-target 인간 승인 전에 첫 byte조차 reader·model context·log·evidence로
들어오지 않는다는 계약을 negative fixture로 증명한다.

## 2. 권한 모델

| Scope | companion list | 허용 규칙 |
| --- | --- | --- |
| `PROJECT` | 빈 배열 | confirmed root containment를 만족하는 RESOURCE read/write만 허용 |
| `NAMED_RESOURCES` | 비어 있지 않은 배열 | case-sensitive exact literal membership만 허용 |
| `NONE` | 빈 배열 | 해당 operation 거부 |

absolute path, `..`, wildcard, glob, regex, prefix/suffix 추론, duplicate,
빈 literal, case conversion 및 symlink escape는 거부한다. `PROJECT`는
COMMAND execute 또는 NETWORK에 사용할 수 없다. authorization은 approved
candidate, current revision, operation mode, runtime capability와의 교집합이며
`UNKNOWN`은 deny다.

## 3. 보호 데이터 preflight

보호 대상은 적용 profile의 protected-resource 패턴, credential/private-data
classification과 exact target approval을 함께 사용해 판정한다. preflight는
경로 canonicalization과 containment를 확인한 뒤, target별 사람 승인이 없으면
reader invocation보다 먼저 종료한다. mutation은 user-change ownership과
protected status를 effect 직전에 재검사한다.

fixture runner는 sentinel content를 가진 guarded reader, model-context sink,
log sink, evidence sink을 주입한다. 거부 case에서는 reader call count와 세
sink의 sentinel occurrence가 모두 0이어야 한다. raw sentinel 값은 결과
artifact에 기록하지 않는다.

## 4. 구성과 데이터 흐름

- `contracts/forgeops-authority-policy/1.0/schema.json`: shared closed policy
  envelope, RESOURCE scope/list, action identity, capability·candidate·revision
  precondition을 정의한다. W2-4와 W2-5가 같은 envelope를 사용한다.
- `fixtures/forgeops-authority-resource/suite.json`: path/scope/protected-read
  negative cases를 정의한다.
- `tools/policy_contract/verify.py resource`: schema → path → scope/list →
  capability/candidate/revision → protected preflight → sink assertion 순으로
  판정한다.
- `tests/policy_contract/test_resource.py`: exact membership과 first-byte
  block을 회귀 검증한다.

## 5. 오류와 fixture

stable category는 `RESOURCE_SCHEMA_INVALID`, `RESOURCE_PATH_INVALID`,
`RESOURCE_SCOPE_INVALID`, `RESOURCE_CONTAINMENT_FAILED`,
`RESOURCE_EXACT_MATCH_REQUIRED`, `RESOURCE_CAPABILITY_DENIED`,
`PROTECTED_TARGET_APPROVAL_REQUIRED`, `USER_CHANGE_CONFLICT`를 사용한다.

fixture는 valid PROJECT·NAMED read/write, absolute/parent/wildcard/prefix/case
mismatch, empty·duplicate list, `UNKNOWN` capability, root escape, symlink
escape, stale revision, unapproved protected target, credential/private-data
sentinel, user-modified resource mutation을 포함한다.

## 6. 검증과 범위 제외

`resource-authority-negative`와 `protected-read-negative`는 E2 result에
case ID, stable category, sink zero assertion, schema/suite hash만 남긴다.
실제 repository의 protected file을 읽거나 수정하지 않으며, sandbox race
hardening과 production credential lifecycle은 이후 runtime 작업의 범위다.
