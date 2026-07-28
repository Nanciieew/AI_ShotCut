# Engine Patch: Confidence Exposure

## File
omnishotcut/engine.py (commit 23ad6fb)

## Changes

### 1. _run_on_numpy ¡ª return confidences
- Each boundary dict now includes  and  (softmax probability at argmax)
- Return type changed:  ¡ú 
-  list built alongside 

### 2. merge_predictions ¡ª confidence-aware merge
- When two boundaries collide (within duplicate_tolerance), keep the one with higher intra_conf
- Previously: simply skipped the duplicate

## Rationale
Model argmax-only output discards probability information that could help distinguish true positives from false positives.
This patch surfaces softmax confidences for downstream filtering and diagnostics.

## Status
Applied 2026-07-28. Required for OmniShotCutAdapter.
