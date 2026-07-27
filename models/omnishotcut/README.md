# OmniShotCut Adapter

## Responsibility

Shot Boundary Detection only.

OmniShotCut detects natural shot boundaries (hard cuts, dissolves, etc.) and
outputs shot ranges with transition types and confidence scores.

## Input

Normalized video file (MP4).

## Output

`shots.json` — array of shot boundaries with:
- `shot_id`, `index`, `start_ms`, `end_ms`
- `start_frame`, `end_frame_exclusive`
- `boundary_type` (hard_cut, dissolve, etc.)
- `confidence` [0, 1]

## Constraints

- Must NOT perform scene merging.
- Must NOT compute scene_score, action_score, or plot_score.
- All timestamps in integer milliseconds.

## Access Method

See project root `third_party/README.md` for the 3 approved integration
strategies (fixed-commit pip install, git submodule, or patched copy).

## License

To be verified before commercial use.
