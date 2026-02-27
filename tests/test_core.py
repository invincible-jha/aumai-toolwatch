"""Comprehensive tests for aumai_toolwatch core module."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

import pytest

from aumai_toolwatch.core import (
    MutationDetector,
    ToolFingerprinter,
    WatchManager,
    _sha256,
    _stable_json,
)
from aumai_toolwatch.models import MutationAlert, ToolFingerprint, WatchConfig


# ===========================================================================
# Module-level helpers
# ===========================================================================


class TestStableJson:
    def test_returns_string(self) -> None:
        assert isinstance(_stable_json({"a": 1}), str)

    def test_dict_keys_sorted(self) -> None:
        result = _stable_json({"z": 1, "a": 2, "m": 3})
        parsed = json.loads(result)
        assert list(parsed.keys()) == sorted(parsed.keys())

    def test_identical_dicts_produce_same_json(self) -> None:
        d1 = {"b": 2, "a": 1}
        d2 = {"a": 1, "b": 2}
        assert _stable_json(d1) == _stable_json(d2)

    def test_empty_dict(self) -> None:
        assert _stable_json({}) == "{}"

    def test_list_serialised(self) -> None:
        result = _stable_json([1, 2, 3])
        assert result == "[1, 2, 3]"

    def test_none_value(self) -> None:
        result = _stable_json(None)
        assert result == "null"


class TestSha256:
    def test_returns_hex_string(self) -> None:
        result = _sha256("hello")
        assert isinstance(result, str)
        assert all(c in "0123456789abcdef" for c in result)

    def test_returns_64_char_hex(self) -> None:
        result = _sha256("hello")
        assert len(result) == 64

    def test_same_input_same_output(self) -> None:
        assert _sha256("test") == _sha256("test")

    def test_different_inputs_different_outputs(self) -> None:
        assert _sha256("hello") != _sha256("world")

    def test_known_hash(self) -> None:
        expected = hashlib.sha256("hello".encode("utf-8")).hexdigest()
        assert _sha256("hello") == expected


# ===========================================================================
# ToolFingerprinter.fingerprint
# ===========================================================================


class TestToolFingerprinter:
    def test_returns_tool_fingerprint(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict, sample_responses: list[dict]
    ) -> None:
        fp = fingerprinter.fingerprint("tool", simple_schema, sample_responses)
        assert isinstance(fp, ToolFingerprint)

    def test_tool_name_preserved(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        fp = fingerprinter.fingerprint("my-tool", simple_schema, [])
        assert fp.tool_name == "my-tool"

    def test_version_preserved(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        fp = fingerprinter.fingerprint("tool", simple_schema, [], version="2.5.1")
        assert fp.version == "2.5.1"

    def test_version_default_unknown(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        fp = fingerprinter.fingerprint("tool", simple_schema, [])
        assert fp.version == "unknown"

    def test_schema_hash_is_64_char_hex(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        fp = fingerprinter.fingerprint("tool", simple_schema, [])
        assert len(fp.schema_hash) == 64

    def test_response_pattern_hash_is_64_char_hex(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict, sample_responses: list[dict]
    ) -> None:
        fp = fingerprinter.fingerprint("tool", simple_schema, sample_responses)
        assert len(fp.response_pattern_hash) == 64

    def test_captured_at_is_datetime(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        fp = fingerprinter.fingerprint("tool", simple_schema, [])
        assert isinstance(fp.captured_at, datetime)

    def test_captured_at_is_utc(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        fp = fingerprinter.fingerprint("tool", simple_schema, [])
        assert fp.captured_at.tzinfo is not None

    def test_same_schema_same_schema_hash(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        fp1 = fingerprinter.fingerprint("tool", simple_schema, [])
        fp2 = fingerprinter.fingerprint("tool", simple_schema, [])
        assert fp1.schema_hash == fp2.schema_hash

    def test_different_schema_different_hash(
        self,
        fingerprinter: ToolFingerprinter,
        simple_schema: dict,
        modified_schema: dict,
    ) -> None:
        fp1 = fingerprinter.fingerprint("tool", simple_schema, [])
        fp2 = fingerprinter.fingerprint("tool", modified_schema, [])
        assert fp1.schema_hash != fp2.schema_hash

    def test_same_responses_same_response_hash(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict, sample_responses: list[dict]
    ) -> None:
        fp1 = fingerprinter.fingerprint("tool", simple_schema, sample_responses)
        fp2 = fingerprinter.fingerprint("tool", simple_schema, sample_responses)
        assert fp1.response_pattern_hash == fp2.response_pattern_hash

    def test_different_responses_different_hash(
        self,
        fingerprinter: ToolFingerprinter,
        simple_schema: dict,
        sample_responses: list[dict],
        modified_responses: list[dict],
    ) -> None:
        fp1 = fingerprinter.fingerprint("tool", simple_schema, sample_responses)
        fp2 = fingerprinter.fingerprint("tool", simple_schema, modified_responses)
        assert fp1.response_pattern_hash != fp2.response_pattern_hash

    def test_empty_schema_fingerprint_works(
        self, fingerprinter: ToolFingerprinter, empty_schema: dict
    ) -> None:
        fp = fingerprinter.fingerprint("tool", empty_schema, [])
        assert isinstance(fp, ToolFingerprint)

    def test_empty_responses_fingerprint_works(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict, empty_responses: list[dict]
    ) -> None:
        fp = fingerprinter.fingerprint("tool", simple_schema, empty_responses)
        assert isinstance(fp, ToolFingerprint)

    def test_schema_key_order_invariant(
        self, fingerprinter: ToolFingerprinter
    ) -> None:
        schema_a = {"b": 2, "a": 1}
        schema_b = {"a": 1, "b": 2}
        fp_a = fingerprinter.fingerprint("t", schema_a, [])
        fp_b = fingerprinter.fingerprint("t", schema_b, [])
        assert fp_a.schema_hash == fp_b.schema_hash


class TestSummariseResponses:
    def test_empty_returns_stable_string(self, fingerprinter: ToolFingerprinter) -> None:
        result = fingerprinter._summarise_responses([])
        assert isinstance(result, str)

    def test_single_response_captures_keys(self, fingerprinter: ToolFingerprinter) -> None:
        responses = [{"name": "Alice", "age": 30}]
        summary = fingerprinter._summarise_responses(responses)
        parsed = json.loads(summary)
        assert "name" in parsed
        assert "age" in parsed

    def test_value_types_captured(self, fingerprinter: ToolFingerprinter) -> None:
        responses = [{"value": 42, "label": "x"}]
        summary = fingerprinter._summarise_responses(responses)
        parsed = json.loads(summary)
        assert "int" in parsed["value"]
        assert "str" in parsed["label"]

    def test_multiple_types_for_same_key(self, fingerprinter: ToolFingerprinter) -> None:
        responses = [{"x": 1}, {"x": "string"}]
        summary = fingerprinter._summarise_responses(responses)
        parsed = json.loads(summary)
        assert "int" in parsed["x"]
        assert "str" in parsed["x"]

    def test_sorted_output_stable(self, fingerprinter: ToolFingerprinter) -> None:
        responses = [{"z": 1, "a": 2}]
        summary = fingerprinter._summarise_responses(responses)
        parsed = json.loads(summary)
        assert list(parsed.keys()) == sorted(parsed.keys())


# ===========================================================================
# MutationDetector.detect_mutation
# ===========================================================================


class TestMutationDetector:
    def test_identical_fingerprints_returns_none(
        self, baseline_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        result = detector.detect_mutation(baseline_fingerprint, baseline_fingerprint)
        assert result is None

    def test_schema_change_returns_alert(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, schema_changed_fingerprint)
        assert alert is not None

    def test_schema_change_type_is_schema_change(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, schema_changed_fingerprint)
        assert alert is not None
        assert alert.change_type == "schema_change"

    def test_response_change_type_is_response_change(
        self, baseline_fingerprint: ToolFingerprint, response_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, response_changed_fingerprint)
        assert alert is not None
        assert alert.change_type == "response_change"

    def test_both_changed_type_is_behavior_change(
        self, baseline_fingerprint: ToolFingerprint, both_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, both_changed_fingerprint)
        assert alert is not None
        assert alert.change_type == "behavior_change"

    def test_schema_only_change_severity_medium(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, schema_changed_fingerprint)
        assert alert is not None
        assert alert.severity == "medium"

    def test_both_changed_severity_high(
        self, baseline_fingerprint: ToolFingerprint, both_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, both_changed_fingerprint)
        assert alert is not None
        assert alert.severity == "high"

    def test_alert_contains_tool_name(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, schema_changed_fingerprint)
        assert alert is not None
        assert alert.tool_name == "search-tool"

    def test_alert_contains_old_and_new(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, schema_changed_fingerprint)
        assert alert is not None
        assert alert.old_fingerprint is baseline_fingerprint
        assert alert.new_fingerprint is schema_changed_fingerprint

    def test_alert_has_detected_at(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, schema_changed_fingerprint)
        assert alert is not None
        assert isinstance(alert.detected_at, datetime)

    def test_alert_returns_mutation_alert_type(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        detector = MutationDetector()
        alert = detector.detect_mutation(baseline_fingerprint, schema_changed_fingerprint)
        assert isinstance(alert, MutationAlert)


# ===========================================================================
# WatchManager
# ===========================================================================


class TestWatchManagerAddBaseline:
    def test_add_baseline_stores_fingerprint(self, baseline_fingerprint: ToolFingerprint) -> None:
        manager = WatchManager()
        manager.add_baseline(baseline_fingerprint)
        assert manager.get_baseline("search-tool") is baseline_fingerprint

    def test_add_baseline_overwrites_existing(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        manager = WatchManager()
        manager.add_baseline(baseline_fingerprint)
        manager.add_baseline(schema_changed_fingerprint)
        stored = manager.get_baseline("search-tool")
        assert stored is schema_changed_fingerprint

    def test_add_multiple_tools(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        manager = WatchManager()
        fp1 = fingerprinter.fingerprint("tool-a", simple_schema, [])
        fp2 = fingerprinter.fingerprint("tool-b", simple_schema, [])
        manager.add_baseline(fp1)
        manager.add_baseline(fp2)
        assert manager.get_baseline("tool-a") is fp1
        assert manager.get_baseline("tool-b") is fp2


class TestWatchManagerCheck:
    def test_check_no_baseline_registers_as_baseline(
        self, baseline_fingerprint: ToolFingerprint
    ) -> None:
        manager = WatchManager()
        result = manager.check("search-tool", baseline_fingerprint)
        assert result is None
        assert manager.get_baseline("search-tool") is baseline_fingerprint

    def test_check_identical_returns_none(
        self, baseline_fingerprint: ToolFingerprint
    ) -> None:
        manager = WatchManager()
        manager.add_baseline(baseline_fingerprint)
        result = manager.check("search-tool", baseline_fingerprint)
        assert result is None

    def test_check_schema_change_returns_alert(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        manager = WatchManager()
        manager.add_baseline(baseline_fingerprint)
        alert = manager.check("search-tool", schema_changed_fingerprint)
        assert alert is not None

    def test_check_adds_alert_to_history(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        manager = WatchManager()
        manager.add_baseline(baseline_fingerprint)
        manager.check("search-tool", schema_changed_fingerprint)
        assert len(manager.get_alerts()) == 1

    def test_check_no_mutation_no_alert_added(
        self, baseline_fingerprint: ToolFingerprint
    ) -> None:
        manager = WatchManager()
        manager.add_baseline(baseline_fingerprint)
        manager.check("search-tool", baseline_fingerprint)
        assert len(manager.get_alerts()) == 0


class TestWatchManagerGetAlerts:
    def test_get_alerts_empty_initially(self) -> None:
        manager = WatchManager()
        assert manager.get_alerts() == []

    def test_get_alerts_returns_copy(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        manager = WatchManager()
        manager.add_baseline(baseline_fingerprint)
        manager.check("search-tool", schema_changed_fingerprint)
        alerts = manager.get_alerts()
        alerts.clear()
        assert len(manager.get_alerts()) == 1  # internal list not mutated

    def test_multiple_checks_accumulate_alerts(
        self,
        fingerprinter: ToolFingerprinter,
        simple_schema: dict,
        modified_schema: dict,
    ) -> None:
        manager = WatchManager()
        for i in range(3):
            tool = f"tool-{i}"
            baseline = fingerprinter.fingerprint(tool, simple_schema, [])
            mutated = fingerprinter.fingerprint(tool, modified_schema, [])
            manager.add_baseline(baseline)
            manager.check(tool, mutated)
        assert len(manager.get_alerts()) == 3


class TestWatchManagerGetBaseline:
    def test_get_baseline_nonexistent_returns_none(self) -> None:
        manager = WatchManager()
        assert manager.get_baseline("unknown-tool") is None

    def test_get_all_baselines_empty(self) -> None:
        manager = WatchManager()
        assert manager.get_all_baselines() == []

    def test_get_all_baselines_returns_all(
        self, fingerprinter: ToolFingerprinter, simple_schema: dict
    ) -> None:
        manager = WatchManager()
        fp1 = fingerprinter.fingerprint("a", simple_schema, [])
        fp2 = fingerprinter.fingerprint("b", simple_schema, [])
        manager.add_baseline(fp1)
        manager.add_baseline(fp2)
        baselines = manager.get_all_baselines()
        assert len(baselines) == 2

    def test_get_all_baselines_returns_copy(
        self, baseline_fingerprint: ToolFingerprint
    ) -> None:
        manager = WatchManager()
        manager.add_baseline(baseline_fingerprint)
        baselines = manager.get_all_baselines()
        baselines.clear()
        assert len(manager.get_all_baselines()) == 1


# ===========================================================================
# WatchConfig model
# ===========================================================================


class TestWatchConfigModel:
    def test_default_tools_empty(self) -> None:
        config = WatchConfig()
        assert config.tools == []

    def test_default_check_interval(self) -> None:
        config = WatchConfig()
        assert config.check_interval_seconds == 300

    def test_default_alert_on_all_types(self) -> None:
        config = WatchConfig()
        assert "schema_change" in config.alert_on
        assert "behavior_change" in config.alert_on
        assert "response_change" in config.alert_on

    def test_custom_config(self) -> None:
        config = WatchConfig(tools=["tool-a"], check_interval_seconds=60)
        assert config.tools == ["tool-a"]
        assert config.check_interval_seconds == 60


# ===========================================================================
# ToolFingerprint model
# ===========================================================================


class TestToolFingerprintModel:
    def test_fields_present(self, baseline_fingerprint: ToolFingerprint) -> None:
        assert baseline_fingerprint.tool_name
        assert baseline_fingerprint.version
        assert baseline_fingerprint.schema_hash
        assert baseline_fingerprint.response_pattern_hash
        assert baseline_fingerprint.captured_at

    def test_model_serialisation(self, baseline_fingerprint: ToolFingerprint) -> None:
        dumped = baseline_fingerprint.model_dump(mode="json")
        restored = ToolFingerprint.model_validate(dumped)
        assert restored.schema_hash == baseline_fingerprint.schema_hash


# ===========================================================================
# MutationAlert model
# ===========================================================================


class TestMutationAlertModel:
    def test_mutation_alert_fields(
        self, baseline_fingerprint: ToolFingerprint, schema_changed_fingerprint: ToolFingerprint
    ) -> None:
        alert = MutationAlert(
            tool_name="test-tool",
            change_type="schema_change",
            old_fingerprint=baseline_fingerprint,
            new_fingerprint=schema_changed_fingerprint,
            detected_at=datetime.now(tz=timezone.utc),
            severity="medium",
        )
        assert alert.tool_name == "test-tool"
        assert alert.change_type == "schema_change"
        assert alert.severity == "medium"


# ===========================================================================
# Parametrize: fingerprint stability
# ===========================================================================


@pytest.mark.parametrize("tool_name", ["tool-a", "search-web", "my_tool_123", "T"])
def test_fingerprint_tool_name_preserved(
    fingerprinter: ToolFingerprinter, tool_name: str, simple_schema: dict
) -> None:
    fp = fingerprinter.fingerprint(tool_name, simple_schema, [])
    assert fp.tool_name == tool_name


@pytest.mark.parametrize("version", ["1.0.0", "v2", "unknown", "2024.01.05"])
def test_fingerprint_version_preserved(
    fingerprinter: ToolFingerprinter, version: str, simple_schema: dict
) -> None:
    fp = fingerprinter.fingerprint("tool", simple_schema, [], version=version)
    assert fp.version == version
