"""Registered CLI for ForgeOps W9 Phase 1 safety decisions."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from typing import Sequence

from jsonschema import Draft202012Validator


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.phase1_safety.audit import reduce_security_negative
from tools.phase1_safety.model import SafetyError, SourceIdentity, atomic_write_json, validate_source_identity
from tools.phase1_safety.registry import load_registry


SCHEMA_REF = "contracts/forgeops-phase1-safety/1.0/schema.json"
SUITE_REF = "fixtures/forgeops-phase1-safety/suite.json"
TRUSTED_COMMANDS = {
    "phase1-security-negative": {
        "result": "artifacts/verification/phase-1-security-negative-result.json",
        "report_md": None,
        "report_html": None,
    },
    "phase1-evidence-freshness": {
        "result": "artifacts/verification/phase-1-evidence-freshness-result.json",
        "report_md": None,
        "report_html": None,
    },
    "phase1-safety-gate": {
        "result": "artifacts/verification/phase-1-safety-gate-result.json",
        "report_md": "artifacts/reviews/phase-1-safety-scorecard.md",
        "report_html": "artifacts/reviews/phase-1-safety-scorecard.html",
    },
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--suite", required=True)
    parser.add_argument("--result", required=True)
    parser.add_argument("--report-md")
    parser.add_argument("--report-html")
    parser.add_argument("--command-id", required=True)
    return parser


def _validate_cli(args: argparse.Namespace) -> None:
    if args.schema != SCHEMA_REF or args.suite != SUITE_REF or args.command_id not in TRUSTED_COMMANDS:
        raise SafetyError("VERIFIER_IDENTITY_INVALID")
    trusted = TRUSTED_COMMANDS[args.command_id]
    if (
        args.result != trusted["result"]
        or args.report_md != trusted["report_md"]
        or args.report_html != trusted["report_html"]
    ):
        raise SafetyError("VERIFIER_IDENTITY_INVALID")


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SafetyError("VERIFIER_INPUT_INVALID") from error


def _identity_from_environment() -> SourceIdentity:
    default_branch = os.environ.get("GITHUB_EVENT_DEFAULT_BRANCH", "")
    return validate_source_identity(
        {
            "repository": os.environ.get("GITHUB_REPOSITORY", ""),
            "repository_id": os.environ.get("GITHUB_REPOSITORY_ID", ""),
            "default_branch": default_branch,
            "workflow_ref": os.environ.get("GITHUB_REF", ""),
            "source_sha": os.environ.get("GITHUB_SHA", ""),
            "workflow_sha": os.environ.get("GITHUB_WORKFLOW_SHA", ""),
            "run_id": os.environ.get("GITHUB_RUN_ID", ""),
            "run_attempt": int(os.environ.get("GITHUB_RUN_ATTEMPT", "0")) if os.environ.get("GITHUB_RUN_ATTEMPT", "0").isdigit() else 0,
        }
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    root: Path = REPOSITORY_ROOT,
    validated_at: datetime | None = None,
    source_identity: SourceIdentity | None = None,
    binding_resolver=None,
    source_checker=None,
) -> int:
    args = _parser().parse_args(argv)
    try:
        _validate_cli(args)
        schema = _load_json(root / args.schema)
        suite = _load_json(root / args.suite)
        if not isinstance(schema, dict) or not isinstance(suite, dict):
            raise SafetyError("VERIFIER_INPUT_INVALID")
        Draft202012Validator.check_schema(schema)
        if list(Draft202012Validator(schema).iter_errors(suite)):
            raise SafetyError("VERIFIER_INPUT_INVALID")
        registrations = load_registry(suite)
        identity = source_identity or _identity_from_environment()
        when = validated_at or datetime.now(timezone.utc).replace(microsecond=0)
        if args.command_id != "phase1-security-negative":
            raise SafetyError("VERIFIER_COMMAND_NOT_IMPLEMENTED")
        kwargs = {}
        if binding_resolver is not None:
            kwargs["binding_resolver"] = binding_resolver
        if source_checker is not None:
            kwargs["source_checker"] = source_checker
        result = reduce_security_negative(
            root,
            registrations=registrations,
            validated_at=when,
            source_identity=identity,
            **kwargs,
        )
        result_schema = {"$ref": "#/$defs/reducerResult", "$defs": schema["$defs"]}
        if list(Draft202012Validator(result_schema).iter_errors(result)):
            raise SafetyError("VERIFIER_RESULT_INVALID")
        atomic_write_json(root / args.result, result)
        return 0 if result["status"] == "PASSED" else 1
    except SafetyError as error:
        print(error.code, file=sys.stderr)
        return 2
    except Exception:
        print("VERIFIER_UNEXPECTED_FAILURE", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
