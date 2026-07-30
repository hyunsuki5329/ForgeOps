# Phase 0 Exit Report

## Decision

Status: **NOT_READY**
Observed at: 2026-07-30T08:14:21Z
Coverage: 15/18 passed

## Gate summary

| Gate | Profile | Command | Status | Tier | Observed at | Artifact |
| --- | --- | --- | --- | --- | --- | --- |
| VG-001 | forgeops-foundation-conformance | protocol-conformance | PASSED | E2 | 2026-07-30T08:14:07Z | artifacts/verification/vg-001-protocol-conformance-result.json |
| VG-001 | forgeops-foundation-conformance | sample-fixture | PASSED | E2 | 2026-07-30T08:14:07Z | artifacts/verification/vg-001-sample-fixture-result.json |
| VG-002 | forgeops-contract-bridge | bridge-schema-fixture | PASSED | E2 | 2026-07-30T08:13:48Z | artifacts/verification/vg-002-contract-bridge-result.json |
| VG-003 | forgeops-state-contract | state-transition-fixture | PASSED | E2 | 2026-07-30T08:13:48Z | artifacts/verification/vg-003-state-transition-result.json |
| VG-003 | forgeops-state-contract | event-order-fixture | PASSED | E2 | 2026-07-30T08:13:49Z | artifacts/verification/vg-003-event-order-result.json |
| VG-003 | forgeops-state-contract | replay-contract-negative | PASSED | E2 | 2026-07-30T08:13:51Z | artifacts/verification/vg-003-replay-contract-result.json |
| VG-004 | forgeops-interface-contract | interface-contract-fixture | PASSED | E2 | 2026-07-30T08:14:05Z | artifacts/verification/vg-004-interface-contract-result.json |
| VG-005 | forgeops-authority-resource | resource-authority-negative | PASSED | E2 | 2026-07-30T08:13:53Z | artifacts/verification/vg-005-resource-authority-result.json |
| VG-005 | forgeops-authority-resource | protected-read-negative | PASSED | E2 | 2026-07-30T08:13:54Z | artifacts/verification/vg-005-protected-read-result.json |
| VG-006 | forgeops-authority-command-network | command-network-negative | PASSED | E2 | 2026-07-30T08:14:00Z | artifacts/verification/vg-006-command-network-result.json |
| VG-007 | forgeops-approval-policy | approval-negative-fixture | PASSED | E2 | 2026-07-30T08:14:04Z | artifacts/verification/vg-007-approval-policy-result.json |
| VG-008 | forgeops-sandbox-security | image-provenance-negative | NOT_RUN | E3 | 2026-07-30T07:18:20Z | artifacts/verification/vg-008-image-provenance-result.json |
| VG-008 | forgeops-sandbox-security | containment-egress-negative | NOT_RUN | E3 | 2026-07-30T07:18:21Z | artifacts/verification/vg-008-containment-egress-result.json |
| VG-008 | forgeops-sandbox-security | teardown-negative | NOT_RUN | E3 | 2026-07-30T07:18:22Z | artifacts/verification/vg-008-teardown-result.json |
| VG-009 | forgeops-secret-artifact-security | secret-surface-negative | PASSED | E3 | 2026-07-30T08:14:20Z | artifacts/verification/vg-009-secret-surface-result.json |
| VG-009 | forgeops-secret-artifact-security | artifact-isolation-negative | PASSED | E3 | 2026-07-30T08:14:21Z | artifacts/verification/vg-009-artifact-isolation-result.json |
| VG-023 | forgeops-evidence-contract | evidence-positive-negative | PASSED | E2 | 2026-07-30T08:14:06Z | artifacts/verification/vg-023-evidence-contract-result.json |
| VG-023 | forgeops-evidence-contract | extension-provenance | PASSED | E2 | 2026-07-30T08:14:07Z | artifacts/verification/vg-023-extension-provenance-result.json |

## Blocking conditions

- VG-008 / image-provenance-negative: PHASE_EXIT_STATUS_NOT_RUN
- VG-008 / image-provenance-negative: PHASE_EXIT_EVIDENCE_STALE
- VG-008 / containment-egress-negative: PHASE_EXIT_STATUS_NOT_RUN
- VG-008 / containment-egress-negative: PHASE_EXIT_EVIDENCE_STALE
- VG-008 / teardown-negative: PHASE_EXIT_STATUS_NOT_RUN
- VG-008 / teardown-negative: PHASE_EXIT_EVIDENCE_STALE

## Residual risks

- Phase 0 Exit conditions are not satisfied; resolve every blocker before reassessment.

## Reproduction command

- Aggregation is performed by the registered Phase 0 exit command.
