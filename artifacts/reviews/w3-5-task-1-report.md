# W3-5 Task 1 Implementation Report

## Scope

Implemented only Task 1, "Build the exact-path integrated runner and failure-safe result," from the approved W3-5 plan. The work does not register `AGENTS.md`, generate the registered VG-004 result artifact, update WBS/RTM status, invoke network/process/external services, or perform Git mutation.

## Changed resources

- `tools/interface_contract/verify.py`
  - Adds the closed CLI for the seven registered contract/suite literals, the single registered result literal, and command ID `interface-contract-fixture`.
  - Rejects aliases, traversal-equivalent spellings, arbitrary result targets, unknown command IDs, and CLI parse failures with `INTERFACE_RUNNER_CONTRACT_INVALID`.
  - Validates exact suite identities, versions, ordered case IDs, uniqueness, root fields, and case-envelope fields before evaluating any fixture case.
  - Runs the OpenAPI/version, data-control boundary, durable event, and manifest validators in-memory and projects only case ID, kind, expected/actual category, and verdict.
  - Hashes only the seven registered contract/suite files and reports closed component totals.
  - Counts negative effect-spy observations and requires zero for a passing result.
  - Atomically replaces only the registered result path using a sibling temporary file.
  - Converts CLI, JSON parse, input-contract, and component-contract failures into a closed safe failure result without exception text, traceback, source payload, or arbitrary output path writes.
- `tests/interface_contract/test_verify.py`
  - Covers exact path/command admission, ordered and closed catalog guards, integrated 104-case evaluation, strict UTC output, arbitrary result denial, JSON corruption, CLI parse failures, safe stale-result replacement, temporary cleanup, and public-safe failure fields.

## TDD evidence

### RED 1: runner absent

Command:

`python -m unittest tests.interface_contract.test_verify -v`

Observed result: exit code 1; the test module failed to import because `tools.interface_contract.verify` did not exist.

### GREEN refinement: event mutation contract

The first integrated GREEN run passed six tests and failed the integrated case because event stream mutations intentionally omit `operation` and mean exact replacement. Inspection of all event stream mutation records confirmed the same shape. The mutation applicator was changed to default only a missing operation to `replace`; explicit `remove` and `replace` remain closed.

### RED 2: result timestamp boundary

Command:

`python -m unittest tests.interface_contract.test_verify.IntegratedRunnerTests.test_non_strict_observation_time_is_denied_before_public_result tests.interface_contract.test_verify.IntegratedRunnerTests.test_cli_parse_error_writes_closed_failure_without_parser_detail -v`

Observed result: exit code 1; the CLI parse safety case passed, while a `+00:00` timestamp was accepted by `run_conformance` instead of being rejected.

The runner now checks the exact `YYYY-MM-DDTHH:MM:SSZ` UTC form before building a public result. The same two-test command then exited 0.

## Verification evidence

- `python -m unittest tests.interface_contract.test_verify -v`
  - Exit code 0; 13 Task 1 tests passed.
- `python -m unittest tests.interface_contract.test_openapi_version tests.interface_contract.test_api_boundary tests.interface_contract.test_event_wrapper tests.interface_contract.test_run_manifest tests.interface_contract.test_verify -v`
  - Exit code 0; all 79 interface-contract tests passed.
  - The integrated result evaluated 16 API version cases, 28 API boundary cases, 26 event cases, and 34 manifest cases.
- `python -m py_compile tools/interface_contract/verify.py tests/interface_contract/test_verify.py`
  - Exit code 0.
- Static external-effect import/endpoint scan and `git diff --check`
  - Exit code 0; no network/process client or endpoint usage and no whitespace error were found.
- Targeted workspace inspection
  - Only the Task 1 runner, tests, and this report are new in the assigned scope.
  - `artifacts/verification/vg-004-interface-contract-result.json` remains absent; no registered artifact was generated.

## Deferred scope

W3-5 Task 2 cross-contract identity/reference/terminal-state checks and recursive result-safety enforcement remain deferred. W3-5 Task 3 command registration, registered artifact generation, evidence inspection, and WBS/RTM synchronization also remain deferred. No completion claim is made for either task.

## Independent review and remediation — 2026-07-24

The first independent review returned `CHANGES_REQUESTED` with one blocking entry-point defect and two closed-boundary gaps. Each finding was independently reproduced before modification.

### Registered script entry point

`python tools/interface_contract/verify.py --help` initially exited 1 with `ModuleNotFoundError: No module named 'tools'`, while module-import tests passed. Script-mode repository-root bootstrapping now runs before package imports. The in-process entry-point regression and the exact script-form help probe both exit 0 without writing the registered artifact.

### Exact CLI flags

The initial parser accepted `--open` as an abbreviation for `--openapi`. `_RunnerArgumentParser` now uses `allow_abbrev=False`; the abbreviation regression returns `INTERFACE_RUNNER_CONTRACT_INVALID`.

### Closed public categories

A manifest fixture with `kind="UNTRUSTED_RAW_MARKER"` initially produced a PASSED component record containing the marker, and event expected-error values were not fixed per case. Event negative errors and manifest positive/negative kinds and expected categories are now exact per registered case. Direct catalog tests reject both marker mutations, and CLI execution against a temporary tampered registered suite writes only the closed safe failure result without the marker.

Fresh post-remediation evidence is the 13 focused and 79 full interface-contract tests recorded above, plus successful direct script import, compilation, whitespace inspection, and confirmation that the registered VG-004 artifact remains absent.

## Independent re-review — 2026-07-24

**Verdict: APPROVED.** No Critical, Important, or Minor finding remains for Task 1.

- The direct registered script form imports successfully because repository-root bootstrapping precedes package imports.
- Abbreviated flags fail closed, while every registered literal remains accepted.
- Event and manifest public categories are fixed per registered case, and a raw-marker fixture mutation produces only the closed safe failure result.
- The reviewer independently observed 13/13 focused tests and 79/79 full interface-contract tests passing.
- The registered VG-004 artifact remains absent, and no out-of-scope or Git mutation was observed.
