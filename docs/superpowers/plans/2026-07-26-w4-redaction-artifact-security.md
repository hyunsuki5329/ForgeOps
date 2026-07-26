# W4-4 Redaction and Artifact Security Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement VG-009 E3 fixtures proving that raw secret/private values never reach observable surfaces and cross-tenant or unsafe artifact writes are rejected before storage/export.

**Architecture:** A closed secret/artifact schema defines safe surface and artifact metadata. A pure redaction and admission evaluator operates on synthetic fixtures through in-memory spies; the registered CLI emits only counts/categories and separate secret-surface and artifact-isolation artifacts.

**Tech Stack:** Python 3.11, `jsonschema` Draft 2020-12, stdlib `argparse`/`json`/`re`/`tempfile`/`unittest`, JSON Schema, Markdown

## Global Constraints

- WBS-009 and both VG-001 commands must be fresh PASSED before WBS-011 can complete.
- Fixture secrets are synthetic test markers only; public results must contain neither marker text, reversible preview, encoded variants, nor a general SHA-256 of the raw marker.
- Inspect these exact surfaces: `packet`, `event`, `prompt`, `artifact`, `trace`, `telemetry`, `response`.
- Apply redaction or rejection before storage, exporter, response publish, model-context, log, or evidence admission.
- Unredactable raw content is discarded; a reference may be retained only when it passes the closed artifact policy.
- Artifact metadata requires exact tenant identity, checksum, encryption state, retention class, deletion policy, and tamper reference. Cross-tenant refs, absolute paths, URLs, signed URLs, credential-like fields, unknown fields, and duplicate IDs are denied.
- Negative cases require `store_calls=0`, `export_calls=0`, `publish_calls=0`, and `raw_occurrences=0`.
- Accept only registered schema/suite/result literals and command IDs `secret-surface-negative` and `artifact-isolation-negative`.
- Do not Git add/commit/push/PR, publish, access a network, use real credentials/private data, or perform external effects.

---

## File Structure

- Create `contracts/forgeops-secret-artifact-contract/1.0/schema.json`: closed surface input, safe projection, and artifact metadata definitions.
- Create `fixtures/forgeops-secret-artifact-security/suite.json`: exact ordered secret and artifact catalogs.
- Create `tools/secret_artifact_security/__init__.py` and `tools/secret_artifact_security/verify.py`.
- Create `tests/secret_artifact_security/__init__.py` and `tests/secret_artifact_security/test_verify.py`.
- Modify `AGENTS.md`: register two E3 commands and profile.
- Generate `artifacts/verification/vg-009-secret-surface-result.json` and `artifacts/verification/vg-009-artifact-isolation-result.json`.
- Modify WBS/RTM/quality documents only after both commands pass with fresh E3 evidence.

### Task 1: Define closed redaction and artifact contracts

**Files:**

- Create: `contracts/forgeops-secret-artifact-contract/1.0/schema.json`
- Create: `fixtures/forgeops-secret-artifact-security/suite.json`
- Create: `tests/secret_artifact_security/__init__.py`
- Create: `tests/secret_artifact_security/test_verify.py`

**Interfaces:**

- `SurfaceCase`: `id`, `kind`, `surface`, `input`, `expected`, `expected_effects`.
- `ArtifactCase`: `id`, `kind`, `artifact`, `expected_context`, `expected`, `expected_effects`.
- Surface enum: `packet|event|prompt|artifact|trace|telemetry|response`.
- Artifact metadata fields: `artifact_id`, `tenant_id`, `source_ref`, `checksum_sha256`, `encryption_state`, `retention_class`, `deletion_policy`, `tamper_ref`.

- [ ] **Step 1: Write failing schema and exact-catalog tests**

```python
class SecretArtifactSchemaTests(unittest.TestCase):
    def test_objects_are_closed_and_surface_enum_is_exact(self):
        schema = load_schema()
        objects = [node for node in walk(schema) if node.get("type") == "object"]
        self.assertTrue(all(node.get("additionalProperties") is False for node in objects))
        self.assertEqual(
            ["packet", "event", "prompt", "artifact", "trace", "telemetry", "response"],
            schema["$defs"]["SurfaceCase"]["properties"]["surface"]["enum"],
        )
```

- [ ] **Step 2: Run schema tests and observe RED**

Run: `python -m unittest tests.secret_artifact_security.test_verify.SecretArtifactSchemaTests -v`

Expected: FAIL because schema and suite do not exist.

- [ ] **Step 3: Create the closed schema**

Set exact enums:

```json
{
  "encryption_state": ["ENCRYPTED", "PUBLIC_SAFE"],
  "retention_class": ["EPHEMERAL", "AUDIT_SHORT", "PUBLIC"],
  "deletion_policy": ["DELETE_ON_TERMINAL", "DELETE_AFTER_RETENTION", "RETAIN_PUBLIC"],
  "case_kind": ["positive", "negative"]
}
```

Require `source_ref` to be a canonical root-relative literal or `forgeops:artifact:<opaque-id>`; reject schemes, absolute paths, parent traversal, backslashes, query/fragment, userinfo, and sensitive URN kinds.

- [ ] **Step 4: Create exact ordered fixture catalogs**

```python
SECRET_CASES = (
    ("positive-public-packet", "PASSED"),
    ("positive-exact-marker-redacted", "PASSED"),
    ("negative-packet-raw-secret", "SECRET_SURFACE_LEAK"),
    ("negative-event-encoded-secret", "SECRET_SURFACE_LEAK"),
    ("negative-prompt-credential-field", "SECRET_SURFACE_LEAK"),
    ("negative-artifact-raw-preview", "SECRET_SURFACE_LEAK"),
    ("negative-trace-private-id", "SECRET_SURFACE_LEAK"),
    ("negative-telemetry-secret", "SECRET_SURFACE_LEAK"),
    ("negative-response-token", "SECRET_SURFACE_LEAK"),
    ("negative-unredactable-content", "REDACTION_UNSUPPORTED"),
)
ARTIFACT_CASES = (
    ("positive-same-tenant-encrypted", "PASSED"),
    ("positive-public-safe-artifact", "PASSED"),
    ("negative-cross-tenant", "ARTIFACT_TENANT_VIOLATION"),
    ("negative-absolute-source", "ARTIFACT_REFERENCE_INVALID"),
    ("negative-signed-url", "ARTIFACT_REFERENCE_INVALID"),
    ("negative-unencrypted-sensitive", "ARTIFACT_POLICY_INVALID"),
    ("negative-retention-mismatch", "ARTIFACT_POLICY_INVALID"),
    ("negative-tamper-ref", "ARTIFACT_POLICY_INVALID"),
    ("negative-unknown-field", "ARTIFACT_POLICY_INVALID"),
)
```

Use synthetic marker `FORGEOPS_TEST_SECRET_DO_NOT_STORE` only inside fixture inputs. Every negative case declares all effect counters and raw occurrences as zero.

- [ ] **Step 5: Run schema and catalog tests**

Run: `python -m unittest tests.secret_artifact_security.test_verify.SecretArtifactSchemaTests tests.secret_artifact_security.test_verify.CatalogTests -v`

Expected: PASS with exact catalog order and closed fields.

### Task 2: Implement pre-storage redaction and artifact admission

**Files:**

- Create: `tools/secret_artifact_security/__init__.py`
- Create: `tools/secret_artifact_security/verify.py`
- Modify: `tests/secret_artifact_security/test_verify.py`

**Interfaces:**

- `class SecretArtifactError(Exception)` exposes `.code` only.
- `class SurfaceSpy`: `store_calls`, `export_calls`, `publish_calls`, and in-memory admitted values.
- `redact_surface(surface: str, value: object, markers: tuple[str, ...]) -> object`.
- `validate_public_projection(value: object, markers: tuple[str, ...]) -> None`.
- `admit_artifact(artifact: dict, expected_tenant_id: str, spy: SurfaceSpy) -> None`.
- `run_cases(command_id: str, suite: dict) -> list[dict]`.

- [ ] **Step 1: Write failing redaction and before-write tests**

```python
def test_raw_marker_never_reaches_any_surface(self):
    for surface in verify.SURFACES:
        with self.subTest(surface=surface):
            projected = verify.redact_surface(
                surface,
                {"message": verify.TEST_MARKER},
                (verify.TEST_MARKER,),
            )
            self.assertNotIn(verify.TEST_MARKER, json.dumps(projected))

def test_cross_tenant_artifact_is_denied_before_store(self):
    artifact = valid_artifact(tenant_id="TENANT-B")
    spy = verify.SurfaceSpy()
    with self.assertRaisesRegex(verify.SecretArtifactError, "ARTIFACT_TENANT_VIOLATION"):
        verify.admit_artifact(artifact, "TENANT-A", spy)
    self.assertEqual((0, 0, 0), (spy.store_calls, spy.export_calls, spy.publish_calls))
```

- [ ] **Step 2: Run evaluator tests and observe RED**

Run: `python -m unittest tests.secret_artifact_security.test_verify.RedactionTests tests.secret_artifact_security.test_verify.ArtifactAdmissionTests -v`

Expected: FAIL until redaction and admission functions exist.

- [ ] **Step 3: Implement recursive bounded redaction**

```python
FORBIDDEN_KEYS = {
    "credential", "credentials", "token", "secret", "private", "raw",
    "raw_log", "raw_event", "raw_manifest", "headers", "signed_url",
}
REDACTED = "[REDACTED]"

def redact_surface(surface, value, markers):
    if surface not in SURFACES:
        raise SecretArtifactError("REDACTION_UNSUPPORTED")
    projected = redact_value(value, markers, depth=0, items=0)
    validate_public_projection(projected, markers)
    return projected
```

`redact_value` must cap nesting at 12, total items at 1000, and strings at 4096 characters. Forbidden keys replace their value with `[REDACTED]`; exact marker and bounded credential patterns are replaced. Invalid type, excessive size/depth, undecodable bytes, or content that still contains a marker raises `REDACTION_UNSUPPORTED` and returns no projection.

- [ ] **Step 4: Implement artifact validation before effects**

Validation order: closed schema → exact tenant → canonical source ref → encryption/retention/deletion combination → checksum/tamper ref → spy store. Never call a spy on failure.

```python
def admit_artifact(artifact, expected_tenant_id, spy):
    validate_artifact_schema(artifact)
    if artifact["tenant_id"] != expected_tenant_id:
        raise SecretArtifactError("ARTIFACT_TENANT_VIOLATION")
    validate_source_ref(artifact["source_ref"])
    validate_artifact_policy(artifact)
    spy.store(public_artifact_record(artifact))
```

- [ ] **Step 5: Build closed case records and scan raw occurrences**

Case results contain only `case_id`, `expected`, `actual`, `status`, the three effect counts, and `raw_occurrences`. Count marker occurrences across every in-memory admitted value and require zero for all cases.

- [ ] **Step 6: Run all evaluator tests**

Run: `python -m unittest tests.secret_artifact_security.test_verify -v`

Expected: PASS; all seven surfaces are covered, artifact policies are exact, and negative effects/raw occurrences are zero.

### Task 3: Register VG-009, generate E3 evidence, and synchronize WBS-011

**Files:**

- Modify: `tools/secret_artifact_security/verify.py`
- Modify: `tests/secret_artifact_security/test_verify.py`
- Modify: `AGENTS.md`
- Generate: `artifacts/verification/vg-009-secret-surface-result.json`
- Generate: `artifacts/verification/vg-009-artifact-isolation-result.json`
- Modify: `docs/project/wbs.md`
- Modify: `docs/project/requirements-traceability-matrix.md`
- Modify: `docs/quality/verification-and-evaluation-plan.md`

**Interfaces:**

- Profile ID: `forgeops-secret-artifact-security`.
- Command IDs: `secret-surface-negative`, `artifact-isolation-negative`.
- CLI flags: `--schema`, `--suite`, `--result`, `--command-id`; `allow_abbrev=False`.
- Result fields: `gate_id`, `profile_id`, `command_id`, `status`, `observed_at`, `hashes`, `summary`, `cases`, `assertions`; safe failure adds only `failure_code`.

- [ ] **Step 1: Write failing exact-path and result-leak tests**

```python
def test_wrong_result_for_command_is_denied(self):
    args = registered_namespace(
        command_id="artifact-isolation-negative",
        result="artifacts/verification/vg-009-secret-surface-result.json",
    )
    with self.assertRaisesRegex(verify.SecretArtifactError, "SECRET_ARTIFACT_RUNNER_CONTRACT_INVALID"):
        verify.validate_registered_paths(args)

def test_public_result_contains_no_marker_or_hash(self):
    result = verify.run_registered("secret-surface-negative", OBSERVED_AT)
    encoded = json.dumps(result)
    self.assertNotIn(verify.TEST_MARKER, encoded)
    self.assertNotIn(hashlib.sha256(verify.TEST_MARKER.encode()).hexdigest(), encoded)
```

- [ ] **Step 2: Implement exact command/result mapping and atomic writes**

```python
TRUSTED_RESULTS = {
    "secret-surface-negative": "artifacts/verification/vg-009-secret-surface-result.json",
    "artifact-isolation-negative": "artifacts/verification/vg-009-artifact-isolation-result.json",
}
```

On parse/read/schema/evaluation failure, atomically replace only the registered target with a closed failure result. Never include exception text or source values.

- [ ] **Step 3: Register the exact E3 commands**

```text
python tools/secret_artifact_security/verify.py --schema contracts/forgeops-secret-artifact-contract/1.0/schema.json --suite fixtures/forgeops-secret-artifact-security/suite.json --result artifacts/verification/vg-009-secret-surface-result.json --command-id secret-surface-negative
python tools/secret_artifact_security/verify.py --schema contracts/forgeops-secret-artifact-contract/1.0/schema.json --suite fixtures/forgeops-secret-artifact-security/suite.json --result artifacts/verification/vg-009-artifact-isolation-result.json --command-id artifact-isolation-negative
```

Add both to profile `forgeops-secret-artifact-security` with `cwd: "."`, `evidence_tier: E3`, and `required: true`.

- [ ] **Step 4: Run both registered commands and all tests**

Run both commands above.

Run: `python -m unittest discover -s tests/secret_artifact_security -p "test_*.py" -v`

Expected: both artifacts are fresh `PASSED`, hashes match, all public cases pass, raw occurrence and negative effect counts are zero, and all tests pass.

- [ ] **Step 5: Inspect results independently**

Run `python -m json.tool` on both artifacts. Recompute schema/suite hashes and scan serialized results for the marker, its SHA-256, forbidden keys, absolute paths, URL credentials, and unknown result fields.

Expected: no sensitive or unregistered content.

- [ ] **Step 6: Synchronize evidence-backed documents**

Set WBS-011 to `WBS_DONE` only if both VG-009 commands have fresh E3 PASSED results and WBS-009 is done. Update only mapped PRD-FR-007 and PRD-NFR-004/012 RTM facts plus quality profile registration. Do not change WBS-010/012 or declare Phase 0 Exit.

- [ ] **Step 7: Run final checks**

Re-run both registered commands, full secret/artifact tests, `git diff --check`, and `git status --short`.

Expected: fresh passing E3 artifacts, no leaks or whitespace errors, only W4-4 scoped changes, and no staged/committed/published changes.
