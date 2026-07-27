# Scene Boundary Adapter

## Responsibility

Given shots, subtitles, visual features, and audio features, predict whether
each adjacent shot pair belongs to the same scene — i.e., identify scene
boundaries.

## Input

```json
{
  "video_id": "...",
  "artifacts": {
    "shots": "storage://.../shots.json",
    "subtitles": "storage://.../subtitles.json",
    "visual_embeddings": "storage://.../embeddings.npy",
    "audio_embeddings": "storage://.../embeddings.npy"
  }
}
```

## Output

`boundaries.json` — array of boundary decisions:
- `after_shot_id`
- `is_scene_boundary`
- `confidence`

## Constraints

- Must NOT write to the database.
- Must NOT produce final scene JSON — that is done by `merge_shots_to_scenes`.
- Must NOT compute scene_score — score is computed by a separate step.

## Access Method

See project root `third_party/README.md`.

## License

To be verified before commercial use.
