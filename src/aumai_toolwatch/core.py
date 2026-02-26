"""Core logic for aumai-toolwatch."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from aumai_toolwatch.models import MutationAlert, ToolFingerprint

__all__ = ["ToolFingerprinter", "MutationDetector", "WatchManager"]

# Severity rules: how many fields changed -> severity level
_SEVERITY_MAP: dict[int, str] = {0: "low", 1: "medium", 2: "high"}


def _stable_json(data: object) -> str:
    """Serialise *data* to a canonical, sorted JSON string for stable hashing."""
    return json.dumps(data, sort_keys=True, default=str)


def _sha256(text: str) -> str:
    """Return the hex-encoded SHA-256 digest of *text*."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ToolFingerprinter:
    """Generate deterministic fingerprints for tools based on schema + responses.

    Fingerprinting is intentionally model-free: it only hashes the schema
    structure and the set of keys/types observed across sample responses.
    """

    def fingerprint(
        self,
        tool_name: str,
        schema: dict[str, object],
        sample_responses: list[dict[str, object]],
        version: str = "unknown",
    ) -> ToolFingerprint:
        """Create a :class:`ToolFingerprint` for a tool.

        Args:
            tool_name: Unique tool identifier.
            schema: The tool's JSON schema (input/output parameter definition).
            sample_responses: A list of representative response dicts.
            version: Optional version string for the tool.

        Returns:
            A :class:`ToolFingerprint` capturing the current state of the tool.
        """
        schema_hash = _sha256(_stable_json(schema))
        response_pattern_hash = _sha256(self._summarise_responses(sample_responses))

        return ToolFingerprint(
            tool_name=tool_name,
            version=version,
            schema_hash=schema_hash,
            response_pattern_hash=response_pattern_hash,
            captured_at=datetime.now(tz=timezone.utc),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _summarise_responses(self, responses: list[dict[str, object]]) -> str:
        """Reduce a list of response dicts to a structural fingerprint string.

        We collect the sorted union of top-level keys and their value types
        across all responses.  This captures behavioural shape without relying
        on specific values.
        """
        key_types: dict[str, set[str]] = {}
        for response in responses:
            for key, value in response.items():
                key_types.setdefault(key, set()).add(type(value).__name__)

        # Produce a stable representation
        summary = {k: sorted(v) for k, v in sorted(key_types.items())}
        return _stable_json(summary)


class MutationDetector:
    """Compare two fingerprints and emit a :class:`MutationAlert` when they differ."""

    def detect_mutation(
        self, old: ToolFingerprint, new: ToolFingerprint
    ) -> MutationAlert | None:
        """Compare *old* and *new* fingerprints and return an alert if they differ.

        Args:
            old: The baseline fingerprint.
            new: The freshly captured fingerprint.

        Returns:
            A :class:`MutationAlert` when a difference is detected, or *None*.
        """
        schema_changed = old.schema_hash != new.schema_hash
        response_changed = old.response_pattern_hash != new.response_pattern_hash

        if not schema_changed and not response_changed:
            return None

        # Determine the most specific change type
        if schema_changed and response_changed:
            change_type = "behavior_change"
        elif schema_changed:
            change_type = "schema_change"
        else:
            change_type = "response_change"

        num_changes = int(schema_changed) + int(response_changed)
        severity = _SEVERITY_MAP.get(num_changes, "high")

        return MutationAlert(
            tool_name=old.tool_name,
            change_type=change_type,
            old_fingerprint=old,
            new_fingerprint=new,
            detected_at=datetime.now(tz=timezone.utc),
            severity=severity,
        )


class WatchManager:
    """Maintain a registry of baseline fingerprints and check for mutations.

    All state is in-memory.  Baselines persist for the lifetime of the object.
    """

    def __init__(self) -> None:
        self._baselines: dict[str, ToolFingerprint] = {}
        self._alerts: list[MutationAlert] = []
        self._detector = MutationDetector()

    def add_baseline(self, fingerprint: ToolFingerprint) -> None:
        """Store *fingerprint* as the trusted baseline for its tool.

        Args:
            fingerprint: Fingerprint to register as the new baseline.
        """
        self._baselines[fingerprint.tool_name] = fingerprint

    def check(self, tool_name: str, current: ToolFingerprint) -> MutationAlert | None:
        """Compare *current* against the stored baseline for *tool_name*.

        If no baseline exists, the current fingerprint is registered as the
        baseline and *None* is returned.

        Args:
            tool_name: Name of the tool to check.
            current: The freshly captured fingerprint to compare.

        Returns:
            A :class:`MutationAlert` if a mutation is detected, otherwise *None*.
        """
        baseline = self._baselines.get(tool_name)
        if baseline is None:
            self._baselines[tool_name] = current
            return None

        alert = self._detector.detect_mutation(baseline, current)
        if alert is not None:
            self._alerts.append(alert)
        return alert

    def get_alerts(self) -> list[MutationAlert]:
        """Return all alerts accumulated since the manager was created.

        Returns:
            List of :class:`MutationAlert` objects in detection order.
        """
        return list(self._alerts)

    def get_baseline(self, tool_name: str) -> ToolFingerprint | None:
        """Return the stored baseline for *tool_name*, or *None*.

        Args:
            tool_name: Name of the tool to look up.

        Returns:
            The baseline :class:`ToolFingerprint`, or *None* if not registered.
        """
        return self._baselines.get(tool_name)

    def get_all_baselines(self) -> list[ToolFingerprint]:
        """Return all stored baseline fingerprints.

        Returns:
            A list of all :class:`ToolFingerprint` objects in the registry.
        """
        return list(self._baselines.values())
