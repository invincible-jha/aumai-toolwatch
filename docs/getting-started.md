# Getting Started with aumai-toolwatch

Detect runtime changes in tool behavior through cryptographic fingerprinting of schemas and response patterns.

---

## Prerequisites

- Python 3.11 or later
- `pip` (comes with Python)
- Basic familiarity with JSON and command-line tools

No external services, databases, or API keys are required.

---

## Installation

### From PyPI (recommended)

```bash
pip install aumai-toolwatch
```

Verify the installation:

```bash
toolwatch --version
```

### From source

```bash
git clone https://github.com/aumai/aumai-toolwatch
cd aumai-toolwatch
pip install -e .
```

### Development mode (with test dependencies)

```bash
git clone https://github.com/aumai/aumai-toolwatch
cd aumai-toolwatch
pip install -e ".[dev]"
pytest
```

---

## Your First Tool Watch

This tutorial walks through the full lifecycle of monitoring a tool for mutations: baseline capture, mutation detection, and alert review.

### Step 1 — Prepare a tool schema file

Create a file called `my_tool_schema.json` with your tool's JSON Schema definition:

```json
{
  "name": "get_customer_data",
  "description": "Retrieve customer record by ID",
  "parameters": {
    "type": "object",
    "properties": {
      "customer_id": {
        "type": "string",
        "description": "The unique customer identifier"
      },
      "include_history": {
        "type": "boolean",
        "description": "Whether to include transaction history",
        "default": false
      }
    },
    "required": ["customer_id"]
  }
}
```

### Step 2 — Capture a baseline

Run the `baseline` command to fingerprint the tool in its current, known-good state:

```bash
toolwatch baseline \
  --tool get_customer_data \
  --schema my_tool_schema.json \
  --version 1.2.0
```

You should see output like:

```json
{
  "tool_name": "get_customer_data",
  "schema_hash": "e3b0c44298fc1c14...",
  "response_pattern_hash": "0000000000000000...",
  "captured_at": "2026-02-27T12:00:00+00:00"
}
```

The baseline is persisted to `~/.aumai/toolwatch/baselines.json`.

### Step 3 — Simulate a schema change

Edit `my_tool_schema.json` and add a new required field to simulate a breaking change:

```json
{
  "name": "get_customer_data",
  "description": "Retrieve customer record by ID",
  "parameters": {
    "type": "object",
    "properties": {
      "customer_id": {"type": "string"},
      "include_history": {"type": "boolean", "default": false},
      "region": {"type": "string", "description": "Customer's region"}
    },
    "required": ["customer_id", "region"]
  }
}
```

### Step 4 — Run a check

```bash
toolwatch check \
  --tool get_customer_data \
  --schema my_tool_schema.json
```

The mutation is detected and reported:

```json
{
  "tool_name": "get_customer_data",
  "change_type": "schema_change",
  "severity": "medium",
  "detected_at": "2026-02-27T12:05:00+00:00"
}
```

### Step 5 — Review all alerts

```bash
toolwatch alerts
```

---

## Common Patterns

### Pattern 1 — CI pipeline integration

Add a check step to your CI workflow to catch tool schema regressions before deployment:

```bash
# .github/workflows/ci.yml (relevant excerpt)
# - name: Check tool schemas
#   run: |
toolwatch check --tool search_api --schema schemas/search_api.json
toolwatch check --tool email_sender --schema schemas/email_sender.json
toolwatch check --tool database_query --schema schemas/database_query.json
```

If any check detects a mutation, it prints the alert JSON to stdout. You can assert the exit code or parse the output to fail the build.

**Note:** If no baseline exists (e.g., first run in a fresh CI environment), `check` automatically registers the current state as the baseline and exits cleanly.

### Pattern 2 — Monitoring multiple tools from Python

```python
from aumai_toolwatch import ToolFingerprinter, WatchManager

TOOLS = {
    "search_api": (search_api_schema, search_api_sample_responses),
    "email_sender": (email_sender_schema, email_sender_sample_responses),
    "database_query": (db_query_schema, db_query_sample_responses),
}

fingerprinter = ToolFingerprinter()
manager = WatchManager()

# Load baselines from a previous run (or capture fresh ones)
for tool_name, (schema, samples) in TOOLS.items():
    fp = fingerprinter.fingerprint(
        tool_name=tool_name,
        schema=schema,
        sample_responses=samples,
        version="current",
    )
    alert = manager.check(tool_name, fp)
    if alert:
        print(f"[ALERT] {tool_name}: {alert.change_type} ({alert.severity})")
    else:
        print(f"[OK] {tool_name}: no changes")
```

### Pattern 3 — Response-pattern drift detection

Schema drift is easy to notice; behavioral drift is not. Use sample responses to detect silent changes in what a tool actually returns:

```python
from aumai_toolwatch import ToolFingerprinter, MutationDetector

fingerprinter = ToolFingerprinter()
detector = MutationDetector()

# Baseline: tool returns {score: int, label: str}
baseline_responses = [
    {"score": 95, "label": "positive"},
    {"score": 12, "label": "negative"},
]
baseline_fp = fingerprinter.fingerprint(
    "sentiment_analyzer",
    schema=sentiment_schema,
    sample_responses=baseline_responses,
    version="v1",
)

# Current: tool now also returns confidence float
current_responses = [
    {"score": 95, "label": "positive", "confidence": 0.97},
    {"score": 12, "label": "negative", "confidence": 0.88},
]
current_fp = fingerprinter.fingerprint(
    "sentiment_analyzer",
    schema=sentiment_schema,  # schema unchanged
    sample_responses=current_responses,
    version="v2",
)

alert = detector.detect_mutation(baseline_fp, current_fp)
# alert.change_type == "response_change"
# alert.severity == "medium"
```

### Pattern 4 — Persisting baselines across process restarts

The CLI persists state automatically. For library usage, serialize and restore baselines manually:

```python
import json
from aumai_toolwatch import WatchManager
from aumai_toolwatch.models import ToolFingerprint

# Save baselines
manager = WatchManager()
# ... populate manager with fingerprints ...

baselines_data = [fp.model_dump(mode="json") for fp in manager.get_all_baselines()]
with open("baselines.json", "w") as f:
    json.dump(baselines_data, f, indent=2)

# Restore baselines in a new process
new_manager = WatchManager()
with open("baselines.json") as f:
    for entry in json.load(f):
        fp = ToolFingerprint.model_validate(entry)
        new_manager.add_baseline(fp)
```

### Pattern 5 — Alert filtering and routing

```python
alerts = manager.get_alerts()

high_severity = [a for a in alerts if a.severity == "high"]
schema_changes = [a for a in alerts if a.change_type == "schema_change"]

# Send high-severity alerts to a notification channel
for alert in high_severity:
    notify_oncall(
        message=f"Tool mutation: {alert.tool_name} changed ({alert.change_type})",
        severity=alert.severity,
    )
```

---

## Troubleshooting FAQ

**Q: `toolwatch: command not found` after install**

Ensure your Python scripts directory is in `PATH`. With `pip install --user`, add `~/.local/bin` to your `PATH`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

---

**Q: The baseline command runs but nothing appears in `~/.aumai/toolwatch/`**

Check write permissions on your home directory. The directory is created automatically on first use. Run:

```bash
toolwatch baseline --tool test --schema my_schema.json && ls ~/.aumai/toolwatch/
```

---

**Q: I'm getting different schema hashes for the same schema**

The hash is computed over a canonically sorted JSON string. If you are generating the schema programmatically, ensure you pass the same Python dict structure each time. Key ordering does not matter — but the key names, values, and nested structure must be identical.

---

**Q: My sample responses are empty — will fingerprinting still work?**

Yes. If `sample_responses=[]` is passed, the response-pattern hash is computed over an empty structural summary. Any non-empty sample on a subsequent run will trigger a `response_change` alert. Pass at least one representative response to establish a meaningful baseline.

---

**Q: I updated a tool intentionally. How do I update the baseline?**

Run `toolwatch baseline` again with the new schema. This overwrites the stored baseline for that tool. The old fingerprint is not archived automatically — if you need a history of baselines, save them to version control.

---

**Q: Can I use toolwatch with non-JSON schemas?**

The fingerprinter accepts any Python `dict`. Convert your schema to a dict before calling `fingerprint()`. Only the top-level value must be a dict; nested values can be any JSON-serializable type.

---

**Q: How do I disable alerting for a specific change type?**

Use `WatchConfig.alert_on` to declare which change types you care about. For library usage, you can filter `manager.get_alerts()` by `alert.change_type`. The detector always computes both hashes; filtering happens at the consumer level.
