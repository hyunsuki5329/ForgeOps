# ForgeOps Phase 1 Safety Scorecard

- Status: `READY`
- Evidence tier: `E3`
- Validated at: `2026-08-30T02:25:27Z`
- Source SHA: `ff16f39d74861710c5500d81045c46512ee8d589`
- Coverage: `19/19`
- Blockers: `0`

| Gate | Command | Status | Tier | Observed at | Artifact | Blockers |
|---|---|---|---|---|---|---|
| VG-008 | image-provenance-negative | PASSED | E3 | 2026-08-30T02:25:18Z | artifacts/verification/vg-008-image-provenance-result.json | - |
| VG-008 | containment-egress-negative | PASSED | E3 | 2026-08-30T02:25:19Z | artifacts/verification/vg-008-containment-egress-result.json | - |
| VG-008 | teardown-negative | PASSED | E3 | 2026-08-30T02:25:19Z | artifacts/verification/vg-008-teardown-result.json | - |
| VG-009 | secret-surface-negative | PASSED | E3 | 2026-08-30T02:25:20Z | artifacts/verification/vg-009-secret-surface-result.json | - |
| VG-009 | artifact-isolation-negative | PASSED | E3 | 2026-08-30T02:25:20Z | artifacts/verification/vg-009-artifact-isolation-result.json | - |
| VG-010 | snapshot-identity | PASSED | E2 | 2026-08-30T02:25:21Z | artifacts/verification/vg-010-snapshot-identity-result.json | - |
| VG-010 | baseline-retrieval-repeat | PASSED | E2 | 2026-08-30T02:25:23Z | artifacts/verification/vg-010-baseline-retrieval-result.json | - |
| VG-011 | context-provenance | PASSED | E2 | 2026-08-30T02:25:23Z | artifacts/verification/vg-011-context-provenance-result.json | - |
| VG-011 | injection-negative | PASSED | E2 | 2026-08-30T02:25:24Z | artifacts/verification/vg-011-injection-negative-result.json | - |
| VG-012 | main-part-work-main | PASSED | E2 | 2026-08-30T02:25:24Z | artifacts/verification/vg-012-local-vertical-result.json | - |
| VG-013 | task-checks | PASSED | E2 | 2026-08-30T02:25:24Z | artifacts/verification/vg-013-task-checks-result.json | - |
| VG-013 | regression-checks | PASSED | E2 | 2026-08-30T02:25:25Z | artifacts/verification/vg-013-regression-checks-result.json | - |
| VG-013 | verification-anti-tamper | PASSED | E2 | 2026-08-30T02:25:25Z | artifacts/verification/vg-013-verification-anti-tamper-result.json | - |
| VG-014 | budget-cancel-negative | PASSED | E2 | 2026-08-30T02:25:25Z | artifacts/verification/vg-014-budget-cancel-result.json | - |
| VG-014 | no-progress-stop | PASSED | E2 | 2026-08-30T02:25:25Z | artifacts/verification/vg-014-no-progress-result.json | - |
| VG-015 | trace-manifest-completeness | PASSED | E2 | 2026-08-30T02:25:25Z | artifacts/verification/vg-015-trace-manifest-result.json | - |
| VG-015 | external-write-negative | PASSED | E2 | 2026-08-30T02:25:26Z | artifacts/verification/vg-015-external-write-result.json | - |
| VG-023 | evidence-positive-negative | PASSED | E2 | 2026-08-30T02:25:26Z | artifacts/verification/vg-023-evidence-contract-result.json | - |
| VG-023 | extension-provenance | PASSED | E2 | 2026-08-30T02:25:26Z | artifacts/verification/vg-023-extension-provenance-result.json | - |

## Normalized effects

- unauthorized_executions: `0`
- approval_bypasses: `0`
- containment_or_egress_escapes: `0`
- injection_acceptances: `0`
- raw_secret_occurrences: `0`
- cleanup_failures: `0`
- evidence_integrity_failures: `0`
- external_writes: `0`
