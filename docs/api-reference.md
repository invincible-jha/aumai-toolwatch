# API Reference — aumai-toolwatch

Complete reference for all public classes, functions, and Pydantic models in `aumai_toolwatch`.

---

## Module: `aumai_toolwatch`

Top-level public exports (importable directly from `aumai_toolwatch`):

```python
from aumai_toolwatch import (
    ToolFingerprinter,
    MutationDetector,
    WatchManager,
    MutationAlert,
    ToolFingerprint,
    WatchConfig,
)
```

Package version is available as `aumai_toolwatch.__version__` (currently `"0.1.0"`).

---

## Classes

### `ToolFingerprinter`

```
aumai_toolwatch.core.ToolFingerprinter
```

Generates deterministic fingerprints for tools based on their schema and a set of observed sample responses.

Fingerprinting is intentionally value-free: only the schema structure and the structural shape of sample responses (key names and value types) are hashed, not specific values. This ensures that different legitimate response values for the same tool produce the same fingerprint.

**Constructor**

```python
ToolFingerprinter()
```

No parameters. The instance is stateless and safe to share across calls.

---

#### `ToolFingerprinter.fingerprint`

```python
def fingerprint(
    self,
    tool_name: str,
    schema: dict[str, object],
    sample_responses: list[dict[str, object]],
    version: str = "unknown",
) -> ToolFingerprint
```

Create a `ToolFingerprint` for a tool.

**Parameters**

| Parameter | Type | Description |
|---|---|---|
| `tool_name` | `str` | Unique identifier for the tool. Used as the registry key in `WatchManager`. |
| `schema` | `dict[str, object]` | The tool's JSON Schema definition (input/output parameter definition). Any dict structure is accepted. |
| `sample_responses` | `list[dict[str, object]]` | Representative response dictionaries from actual tool calls. Used to build the response-pattern hash. May be empty (`[]`). |
| `version` | `str` | Optional version label. Stored in the fingerprint for informational purposes; does not affect hashing. Default: `"unknown"`. |

**Returns**

`ToolFingerprint` — a fully populated fingerprint with `schema_hash`, `response_pattern_hash`, and `captured_at` set to the current UTC time.

**Example**

```python
from aumai_toolwatch import ToolFingerprinter

fingerprinter = ToolFingerprinter()
fp = fingerprinter.fingerprint(
    tool_name="calculator",
    schema={
        "name": "calculator",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string"}
            },
            "required": ["expression"],
        }
    },
    sample_responses=[
        {"result": 42, "error": None},
        {"result": 3.14, "error": None},
    ],
    version="1.0.0",
)
print(fp.schema_hash)           # SHA-256 hex digest of the schema
print(fp.response_pattern_hash) # SHA-256 hex digest of structural response summary
```

---

### `MutationDetector`

```
aumai_toolwatch.core.MutationDetector
```

Compares two `ToolFingerprint` objects and emits a `MutationAlert` when they differ. Stateless — no internal registry.

**Constructor**

```python
MutationDetector()
```

No parameters.

---

#### `MutationDetector.detect_mutation`

```python
def detect_mutation(
    self,
    old: ToolFingerprint,
    new: ToolFingerprint,
) -> MutationAlert | None
```

Compare two fingerprints and return an alert if they differ.

**Parameters**

| Parameter | Type | Description |
|---|---|---|
| `old` | `ToolFingerprint` | The baseline (trusted) fingerprint. |
| `new` | `ToolFingerprint` | The freshly captured fingerprint to compare against the baseline. |

**Returns**

`MutationAlert | None` — a `MutationAlert` when any difference is detected; `None` when both hashes are identical.

**Change type resolution**

| Schema hash changed | Response hash changed | `change_type` |
|---|---|---|
| Yes | No | `"schema_change"` |
| No | Yes | `"response_change"` |
| Yes | Yes | `"behavior_change"` |

**Severity resolution**

| Number of changed dimensions | `severity` |
|---|---|
| 1 | `"medium"` |
| 2 | `"high"` |

**Example**

```python
from aumai_toolwatch import MutationDetector, ToolFingerprinter

fp_old = ToolFingerprinter().fingerprint("my_tool", old_schema, [])
fp_new = ToolFingerprinter().fingerprint("my_tool", new_schema, [])

detector = MutationDetector()
alert = detector.detect_mutation(fp_old, fp_new)
if alert is not None:
    print(f"{alert.change_type} | {alert.severity}")
```

---

### `WatchManager`

```
aumai_toolwatch.core.WatchManager
```

Maintains an in-memory registry of baseline fingerprints and accumulates mutation alerts. All state is held for the lifetime of the object. For cross-process persistence, use the CLI or serialize/restore manually via `ToolFingerprint.model_dump()` and `ToolFingerprint.model_validate()`.

**Constructor**

```python
WatchManager()
```

No parameters. Internally holds a `dict[str, ToolFingerprint]` registry and a `list[MutationAlert]` accumulator.

---

#### `WatchManager.add_baseline`

```python
def add_baseline(self, fingerprint: ToolFingerprint) -> None
```

Store a fingerprint as the trusted baseline for its tool. If a baseline already exists for `fingerprint.tool_name`, it is overwritten.

**Parameters**

| Parameter | Type | Description |
|---|---|---|
| `fingerprint` | `ToolFingerprint` | Fingerprint to register as the new baseline. |

---

#### `WatchManager.check`

```python
def check(self, tool_name: str, current: ToolFingerprint) -> MutationAlert | None
```

Compare `current` against the stored baseline for `tool_name`. If no baseline exists, `current` is automatically registered as the baseline and `None` is returned.

**Parameters**

| Parameter | Type | Description |
|---|---|---|
| `tool_name` | `str` | Name of the tool to check. Must match `current.tool_name`. |
| `current` | `ToolFingerprint` | Freshly captured fingerprint to compare. |

**Returns**

`MutationAlert | None` — alert if a mutation is detected; `None` if the tool is unchanged or if this was the first check (baseline just registered).

**Side effects**

When a `MutationAlert` is produced, it is appended to the internal alert accumulator accessible via `get_alerts()`.

---

#### `WatchManager.get_alerts`

```python
def get_alerts(self) -> list[MutationAlert]
```

Return all `MutationAlert` objects accumulated since this manager was created, in detection order.

**Returns**

`list[MutationAlert]` — a copy of the internal alert list.

---

#### `WatchManager.get_baseline`

```python
def get_baseline(self, tool_name: str) -> ToolFingerprint | None
```

Retrieve the stored baseline for a specific tool.

**Parameters**

| Parameter | Type | Description |
|---|---|---|
| `tool_name` | `str` | Name of the tool to look up. |

**Returns**

`ToolFingerprint | None` — the baseline fingerprint, or `None` if `tool_name` is not registered.

---

#### `WatchManager.get_all_baselines`

```python
def get_all_baselines(self) -> list[ToolFingerprint]
```

Return all stored baseline fingerprints.

**Returns**

`list[ToolFingerprint]` — a copy of all registered baselines. Order is not guaranteed.

---

## Models

### `ToolFingerprint`

```
aumai_toolwatch.models.ToolFingerprint
```

Pydantic model. Stable fingerprint of a tool's schema and observed response patterns.

| Field | Type | Required | Description |
|---|---|---|---|
| `tool_name` | `str` | Yes | Unique name of the tool being fingerprinted. |
| `version` | `str` | Yes | Version string of the tool at capture time. |
| `schema_hash` | `str` | Yes | SHA-256 hex digest of the canonically sorted, JSON-serialized tool schema. |
| `response_pattern_hash` | `str` | Yes | SHA-256 hex digest of the aggregated structural summary of sample responses. |
| `captured_at` | `datetime` | Yes | UTC timestamp when this fingerprint was captured. |

**Example**

```python
from aumai_toolwatch.models import ToolFingerprint
from datetime import datetime, timezone

fp = ToolFingerprint(
    tool_name="my_tool",
    version="1.0.0",
    schema_hash="abc123...",
    response_pattern_hash="def456...",
    captured_at=datetime.now(tz=timezone.utc),
)

# Serialise for storage
data = fp.model_dump(mode="json")

# Restore from storage
restored = ToolFingerprint.model_validate(data)
```

---

### `MutationAlert`

```
aumai_toolwatch.models.MutationAlert
```

Pydantic model. Alert raised when a tool fingerprint changes from its stored baseline.

| Field | Type | Required | Description |
|---|---|---|---|
| `tool_name` | `str` | Yes | Name of the tool that mutated. |
| `change_type` | `str` | Yes | Type of change: `"schema_change"`, `"response_change"`, or `"behavior_change"`. |
| `old_fingerprint` | `ToolFingerprint` | Yes | The baseline fingerprint at the time the alert was detected. |
| `new_fingerprint` | `ToolFingerprint` | Yes | The current fingerprint that differed from the baseline. |
| `detected_at` | `datetime` | Yes | UTC timestamp when the mutation was detected. |
| `severity` | `str` | Yes | Severity level: `"low"`, `"medium"`, or `"high"`. |

**Example**

```python
# Alerts are produced by MutationDetector.detect_mutation() or WatchManager.check()
alert = manager.check("my_tool", current_fp)
if alert:
    print(alert.model_dump_json(indent=2))
```

---

### `WatchConfig`

```
aumai_toolwatch.models.WatchConfig
```

Pydantic model. Configuration for monitoring sessions. Used by external schedulers or orchestrators that drive `WatchManager`; not consumed internally by any core class.

| Field | Type | Default | Description |
|---|---|---|---|
| `tools` | `list[str]` | `[]` | Tool names to monitor in this session. |
| `check_interval_seconds` | `int` | `300` | How often (in seconds) an external scheduler should re-fingerprint tools. |
| `alert_on` | `list[str]` | `["schema_change", "behavior_change", "response_change"]` | Change types that should generate alerts. Other change types are silently ignored. |

**Example**

```python
from aumai_toolwatch.models import WatchConfig

config = WatchConfig(
    tools=["search_api", "email_sender"],
    check_interval_seconds=60,
    alert_on=["schema_change", "behavior_change"],
)

# Serialise to JSON for configuration files
print(config.model_dump_json(indent=2))
```

---

## CLI Commands

The `toolwatch` CLI is a `click` application. All commands share the `--version` flag (top-level).

### `toolwatch baseline`

Capture and persist a baseline fingerprint.

| Option | Type | Required | Default | Description |
|---|---|---|---|---|
| `--tool` | `str` | Yes | — | Tool name |
| `--schema` | `path` | Yes | — | Path to the JSON schema file |
| `--version` | `str` | No | `"unknown"` | Tool version label |

State written to: `~/.aumai/toolwatch/baselines.json`

### `toolwatch check`

Check a tool against its stored baseline.

| Option | Type | Required | Default | Description |
|---|---|---|---|---|
| `--tool` | `str` | Yes | — | Tool name |
| `--schema` | `path` | Yes | — | Path to the current JSON schema file |
| `--version` | `str` | No | `"unknown"` | Current version label |

State written to: `~/.aumai/toolwatch/baselines.json`, `~/.aumai/toolwatch/alerts.json`

### `toolwatch alerts`

Print all accumulated alerts as a JSON array to stdout.

No options. Reads from `~/.aumai/toolwatch/alerts.json`.

---

## Internal helpers (not public API)

The following module-level functions and constants exist in `core.py` but are not part of the public API. They are documented here for contributors:

| Name | Description |
|---|---|
| `_stable_json(data)` | Serialize `data` to canonical sorted JSON string using `json.dumps(sort_keys=True, default=str)`. |
| `_sha256(text)` | Return the hex-encoded SHA-256 digest of `text`. |
| `_SEVERITY_MAP` | `{0: "low", 1: "medium", 2: "high"}` — maps changed-dimension count to severity label. |
