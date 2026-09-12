"""Catan Lab engine, shared by native Python and the browser worker."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "vendor"))
ENGINE_VERSION = "0.3.0"
REPLAY_VERSIONS = ("0.1.0", "0.2.0", "0.3.0")
RULESET = "catan-base-4p-2025-v2"
REPLAY_RULESETS = ("catan-base-4p-2025-v1", RULESET)
