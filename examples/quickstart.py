"""Quickstart examples for aumai-toolwatch.

Demonstrates the full lifecycle of tool fingerprinting and mutation detection:
  1. Fingerprinting a tool schema and sample responses
  2. Detecting schema drift
  3. Detecting response-pattern drift
  4. Using WatchManager to monitor multiple tools
  5. Serializing and restoring baselines

Run directly:
    python examples/quickstart.py

Or import individual demo functions for experimentation.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from aumai_toolwatch import (
    MutationDetector,
    ToolFingerprinter,
    WatchManager,
)
from aumai_toolwatch.models import ToolFingerprint, WatchConfig

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

CALCULATOR_SCHEMA_V1: dict[str, object] = {
    "name": "calculator",
    "description": "Evaluate a mathematical expression",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression to evaluate"}
        },
        "required": ["expression"],
    },
}

CALCULATOR_SCHEMA_V2: dict[str, object] = {
    "name": "calculator",
    "description": "Evaluate a mathematical expression",
    "parameters": {
        "type": "object",
        "properties": {
            "expression": {"type": "string", "description": "Math expression to evaluate"},
            "precision": {"type": "integer", "description": "Decimal places in result"},  # NEW
        },
        "required": ["expression"],
    },
}

CALCULATOR_RESPONSES_V1: list[dict[str, object]] = [
    {"result": 42, "error": None},
    {"result": 3.14, "error": None},
]

CALCULATOR_RESPONSES_V2: list[dict[str, object]] = [
    # Tool now returns an additional 'expression_normalized' key
    {"result": 42, "error": None, "expression_normalized": "6 * 7"},
    {"result": 3.14, "error": None, "expression_normalized": "3.14"},
]


# ---------------------------------------------------------------------------
# Demo 1: Basic fingerprinting
# ---------------------------------------------------------------------------


def demo_basic_fingerprinting() -> None:
    """Show how ToolFingerprinter computes stable hashes for a schema."""
    print("\n=== Demo 1: Basic Fingerprinting ===")

    fingerprinter = ToolFingerprinter()

    fp = fingerprinter.fingerprint(
        tool_name="calculator",
        schema=CALCULATOR_SCHEMA_V1,
        sample_responses=CALCULATOR_RESPONSES_V1,
        version="1.0.0",
    )

    print(f"Tool name         : {fp.tool_name}")
    print(f"Version           : {fp.version}")
    print(f"Schema hash       : {fp.schema_hash[:16]}...")
    print(f"Response hash     : {fp.response_pattern_hash[:16]}...")
    print(f"Captured at       : {fp.captured_at.isoformat()}")

    # Fingerprinting the same data twice produces the same hash
    fp_again = fingerprinter.fingerprint(
        tool_name="calculator",
        schema=CALCULATOR_SCHEMA_V1,
        sample_responses=CALCULATOR_RESPONSES_V1,
        version="1.0.0",
    )
    assert fp.schema_hash == fp_again.schema_hash, "Hash should be deterministic"
    print("Determinism check : PASSED (same schema produces same hash)")


# ---------------------------------------------------------------------------
# Demo 2: Detecting schema drift
# ---------------------------------------------------------------------------


def demo_schema_drift_detection() -> None:
    """Detect a schema change between v1 and v2 of the calculator tool."""
    print("\n=== Demo 2: Schema Drift Detection ===")

    fingerprinter = ToolFingerprinter()
    detector = MutationDetector()

    fp_v1 = fingerprinter.fingerprint(
        "calculator", CALCULATOR_SCHEMA_V1, CALCULATOR_RESPONSES_V1, version="1.0.0"
    )
    fp_v2 = fingerprinter.fingerprint(
        "calculator", CALCULATOR_SCHEMA_V2, CALCULATOR_RESPONSES_V1, version="2.0.0"
    )

    alert = detector.detect_mutation(fp_v1, fp_v2)

    if alert:
        print(f"Alert detected!")
        print(f"  Tool        : {alert.tool_name}")
        print(f"  Change type : {alert.change_type}")   # "schema_change"
        print(f"  Severity    : {alert.severity}")      # "medium"
        print(f"  Detected at : {alert.detected_at.isoformat()}")
    else:
        print("No mutation detected.")


# ---------------------------------------------------------------------------
# Demo 3: Detecting response-pattern drift (schema unchanged)
# ---------------------------------------------------------------------------


def demo_response_pattern_drift() -> None:
    """Detect behavioral drift when the schema is unchanged but responses changed."""
    print("\n=== Demo 3: Response-Pattern Drift (Silent Behavioral Change) ===")

    fingerprinter = ToolFingerprinter()
    detector = MutationDetector()

    # Same schema, different response structure
    fp_old = fingerprinter.fingerprint(
        "calculator", CALCULATOR_SCHEMA_V1, CALCULATOR_RESPONSES_V1, version="1.0.0"
    )
    fp_new = fingerprinter.fingerprint(
        "calculator", CALCULATOR_SCHEMA_V1, CALCULATOR_RESPONSES_V2, version="1.0.1"
    )

    alert = detector.detect_mutation(fp_old, fp_new)

    if alert:
        print(f"Silent drift detected!")
        print(f"  Change type : {alert.change_type}")  # "response_change"
        print(f"  Severity    : {alert.severity}")     # "medium"
        print("  The schema was unchanged, but the tool now returns additional keys.")
    else:
        print("No mutation detected.")


# ---------------------------------------------------------------------------
# Demo 4: WatchManager for multi-tool monitoring
# ---------------------------------------------------------------------------


def demo_watch_manager() -> None:
    """Use WatchManager to monitor multiple tools and accumulate alerts."""
    print("\n=== Demo 4: WatchManager Multi-Tool Monitoring ===")

    fingerprinter = ToolFingerprinter()
    manager = WatchManager()

    # Define a set of tools with their schemas
    tools: dict[str, tuple[dict[str, object], list[dict[str, object]]]] = {
        "calculator": (CALCULATOR_SCHEMA_V1, CALCULATOR_RESPONSES_V1),
        "search_api": (
            {"name": "search", "parameters": {"properties": {"query": {"type": "string"}}}},
            [{"hits": 5, "results": []}],
        ),
    }

    # First pass: establish baselines (no alerts expected)
    print("\nPass 1 — establishing baselines:")
    for tool_name, (schema, responses) in tools.items():
        fp = fingerprinter.fingerprint(tool_name, schema, responses)
        alert = manager.check(tool_name, fp)
        status = "baseline registered" if alert is None else f"ALERT: {alert.change_type}"
        print(f"  {tool_name}: {status}")

    # Second pass: calculator schema changed, search_api unchanged
    print("\nPass 2 — checking for mutations:")
    tools_v2: dict[str, tuple[dict[str, object], list[dict[str, object]]]] = {
        "calculator": (CALCULATOR_SCHEMA_V2, CALCULATOR_RESPONSES_V1),   # changed
        "search_api": (
            {"name": "search", "parameters": {"properties": {"query": {"type": "string"}}}},
            [{"hits": 5, "results": []}],
        ),  # unchanged
    }
    for tool_name, (schema, responses) in tools_v2.items():
        fp = fingerprinter.fingerprint(tool_name, schema, responses)
        alert = manager.check(tool_name, fp)
        if alert:
            print(f"  {tool_name}: ALERT — {alert.change_type} ({alert.severity})")
        else:
            print(f"  {tool_name}: OK — no changes")

    print(f"\nTotal alerts accumulated: {len(manager.get_alerts())}")


# ---------------------------------------------------------------------------
# Demo 5: Serializing and restoring baselines
# ---------------------------------------------------------------------------


def demo_baseline_persistence() -> None:
    """Show how to serialize baselines to JSON and restore them."""
    print("\n=== Demo 5: Baseline Serialization and Restoration ===")

    fingerprinter = ToolFingerprinter()
    manager = WatchManager()

    # Capture a baseline
    fp = fingerprinter.fingerprint("calculator", CALCULATOR_SCHEMA_V1, CALCULATOR_RESPONSES_V1)
    manager.add_baseline(fp)

    # Serialize all baselines to JSON (e.g., for writing to a file)
    serialized = [fp.model_dump(mode="json") for fp in manager.get_all_baselines()]
    json_string = json.dumps(serialized, indent=2)
    print(f"Serialized baseline (first 200 chars):\n{json_string[:200]}...")

    # Restore in a new manager
    new_manager = WatchManager()
    for entry in json.loads(json_string):
        restored_fp = ToolFingerprint.model_validate(entry)
        new_manager.add_baseline(restored_fp)

    restored = new_manager.get_baseline("calculator")
    assert restored is not None
    assert restored.schema_hash == fp.schema_hash
    print("\nRestoration check : PASSED (hashes match after round-trip)")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run all quickstart demos in sequence."""
    print("aumai-toolwatch quickstart")
    print("=" * 50)

    demo_basic_fingerprinting()
    demo_schema_drift_detection()
    demo_response_pattern_drift()
    demo_watch_manager()
    demo_baseline_persistence()

    print("\n" + "=" * 50)
    print("All demos completed successfully.")


if __name__ == "__main__":
    main()
