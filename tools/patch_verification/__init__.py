"""Deterministic bounded patch verification for ForgeOps VG-013."""

from .profiles import TRUSTED_PROFILE, TRUSTED_PROFILE_DIGEST
from .anti_tamper import build_guard_manifest, verify_guard_manifest

__all__ = [
    "TRUSTED_PROFILE",
    "TRUSTED_PROFILE_DIGEST",
    "build_guard_manifest",
    "verify_guard_manifest",
]
