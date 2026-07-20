# W1 Product Task Contract bridge 검토

**검토 상태:** 완료

**대상 작업:** WBS-002, WBS-003

**검증 gate:** VG-002

**관찰 시각:** `2026-07-20T05:53:16Z`

## 검토 결과

Product Task Contract 1.0 schema와 Contract→TaskPacket bridge의 lossless mapping,
canonical control non-grant, trusted command resolution, gate 단조 강화 및
provenance 조건을 공개 fixture 19건으로 검토했다. 등록된
`forgeops-contract-bridge` profile의 `bridge-schema-fixture` 명령을 fresh
실행한 결과 정상 3건과 거부 16건이 모두 기대 결과와 일치해 `VG-002`는
E2 `PASSED`다.

| 항목 | 결과 |
| --- | --- |
| 전체 fixture | 19/19 PASSED |
| positive | 3/3 PASSED |
| negative | 16/16 PASSED |
| runner regression | 3/3 PASSED |
| Python | 3.11.9 |
| jsonschema | 4.26.0 |
| Schema SHA-256 | `25056ed672952c95ccd4e1f944dd884a9de5a9886c6cd3b3a2b87ab2a6d8c9e4` |
| Suite SHA-256 | `0033fe2a6f1dcca44378fae5ffa5d52c284309b254a9e9a72ea3bca8599061ab` |

## VG-002 criterion과 증빙

| Criterion | 검증 fixture | 결과 |
| --- | --- | --- |
| 원문·criterion·constraint·source identity lossless 보존 | baseline, embedded control text, provenance hash case | PASSED |
| Contract control claim의 canonical control non-grant | 7개 forbidden control field와 embedded text case | PASSED |
| closed schema와 stable rejection | unknown·missing·wrong-type, duplicate, version, intent case | PASSED |
| trusted command와 gate 단조성 | untrusted command, strengthening, relaxation case | PASSED |

검토 중 발견된 expected-result 불일치는 0건이며 미해소 VG-002 위반도 0건이다.

## 증빙과 재현

- Schema: [`contracts/product-task-contract/1.0/schema.json`](../../contracts/product-task-contract/1.0/schema.json)
- Bridge 계약: [`docs/contracts/product-task-contract-to-taskpacket.md`](../contracts/product-task-contract-to-taskpacket.md)
- Canonical 결과: [`artifacts/verification/vg-002-contract-bridge-result.json`](../../artifacts/verification/vg-002-contract-bridge-result.json)
- 공개 안전 렌더: [`artifacts/reviews/w1-contract-bridge-checkpoint.html`](../../artifacts/reviews/w1-contract-bridge-checkpoint.html)
- Fixture manifest: [`fixtures/product-task-contract-bridge/suite.json`](../../fixtures/product-task-contract-bridge/suite.json)
- 검증기: [`tools/contract_bridge/verify.py`](../../tools/contract_bridge/verify.py)
- 검증기 회귀 테스트: [`tests/contract_bridge/test_verify.py`](../../tests/contract_bridge/test_verify.py)
- 등록 위치: [`AGENTS.md`](../../AGENTS.md)의 `bridge-schema-fixture`

재현 명령은 다음과 같다.

```text
python tools/contract_bridge/verify.py --schema contracts/product-task-contract/1.0/schema.json --suite fixtures/product-task-contract-bridge/suite.json --result artifacts/verification/vg-002-contract-bridge-result.json --report artifacts/reviews/w1-contract-bridge-checkpoint.html
```

검증기 자체의 exact case catalog와 fail-closed artifact 처리는 다음 명령으로
재검증한다.

```text
python -m unittest tests.contract_bridge.test_verify -v
```

## 검토 결론과 경계

- Contract 원문, criterion, constraint와 source identity는 지정된 data 및
  namespaced provenance 위치에 보존된다.
- Contract의 capability, authority, approval, policy, budget, state 또는 tool
  주장은 canonical control을 생성하거나 완화하지 않는다.
- unknown·missing·wrong-type field, duplicate criterion, unmapped intent,
  untrusted command, gate 완화와 provenance 불일치는 stable category로 거부된다.
- HTML 검토본은 공개 fixture ID와 stable 결과만 포함하며 외부 링크, 원격
  리소스 또는 활성 스크립트를 포함하지 않는다.
- 이 완료는 Product Task Contract bridge 범위에 한정된다. 제품 runtime,
  VG-001·VG-003 이후 gate, Phase 0 Exit, 외부 게시·push·PR 권한을 뜻하지 않는다.
