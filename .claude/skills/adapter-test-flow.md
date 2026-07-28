# Adapter Test Flow — raw → IO_Rule → normalized

## When to use

After writing or modifying any model adapter (`models/*/adapter.py`), run this skill to validate the full pipeline: raw inference → IO_Rule compliance → normalized output.

## Flow

```
tests/fixtures/videos/{model}/        ← 1. Place test videos
    ↓ run_benchmark.py
tests/fixtures/raw_outputs/{model}/   ← 2. Raw model output
    ↓ run_adapter.py
tests/fixtures/normalized_outputs/{model}/  ← 3. Normalized + IO_Rule validated
```

## Steps

### 1. Raw inference (model SPIKE)

```bash
python -m scripts.experiments.{model}.run_benchmark
# or use the universal script (recommended):
python -m scripts.experiments.run_model_test --model {model}
```

Produces: `tests/fixtures/raw_outputs/{model}/{video}_raw.json`

Each raw file contains: raw_ranges, confidences, fps, frame_count, runtime.

### 2. IO_Rule check

Read `IO_Rule.md` and confirm the adapter's output conforms to:

| Spec | Required fields |
|------|----------------|
| §1 通用输入外壳 | schema_version, task_id, video_id, model{name,version}, input, parameters |
| §2 通用成功输出 | status:"SUCCEEDED", artifacts:{key: URI}, metrics:{shot_count, runtime_ms}, error:null |
| §3 通用失败输出 | status:"FAILED", artifacts:{}, metrics:{}, error:{code, message, retryable} |
| §4 模型特定 | Per-model artifact format (e.g. §4.1 shots.json for shot detectors) |
| §5 时间坐标 | integer ms, [start_ms, end_ms), fps_num/fps_den |
| §6 Artifact URI | storage://projects/{project}/videos/{video}/artifacts/{model}/{version}/{file} |

### 3. Adapter validation

```bash
PYTHONPATH=. python scripts/experiments/{model}/run_adapter.py
```

Produces:
- `tests/fixtures/normalized_outputs/{model}/{video}.task_result.json` — IO_Rule §2 wrapper
- `tests/fixtures/normalized_outputs/{model}/{video}.shots.json` — IO_Rule §4 artifact

### 4. Compliance report

Check each task_result.json for:

```
[ ] schema_version = "1.0"
[ ] status = "SUCCEEDED"
[ ] artifacts URI is non-empty, follows storage:// format
[ ] metrics contains shot_count (or equivalent) + runtime_ms
[ ] error is null
[ ] model.name and model.version match registry.yaml
[ ] No forbidden fields (action_score, plot_score)
[ ] All timestamps in integer ms
[ ] Shots are continuous (end_ms[i] == start_ms[i+1])
```

Check each shots.json for:

```
[ ] video_id present
[ ] shots[]: shot_id, index, start_ms, end_ms, start_frame, end_frame_exclusive
[ ] All confidence values in [0,1] or null
[ ] end_frame_exclusive > start_frame
[ ] start_ms < end_ms
```

### 5. Compare with expected (if exists)

```bash
# Human reviews raw output and creates expected files:
tests/fixtures/expected/{model}/{video}.expected.json

# Then compare:
python -c "
import json
# Load expected vs normalized, compare shot counts and boundaries
"
```

## Previous run reference (omnishotcut)

```bash
# Raw
PYTHONPATH=. python scripts/experiments/omnishotcut/run_benchmark.py
# Adapter
PYTHONPATH=. python scripts/experiments/omnishotcut/run_adapter.py
```
