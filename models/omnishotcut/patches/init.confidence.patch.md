# \_\_init\_\_.py Patch: Confidence Pass-through

## File
omnishotcut/__init__.py (commit 23ad6fb)

## Changes
- : now returns  instead of 
- : now returns  instead of 
- Unpacks 4 values from  instead of 3

## Rationale
Expose confidence scores from engine.py to the public API for downstream filtering.

## Status
Applied 2026-07-28. Backward-incompatible ¡ª all callers must update.
