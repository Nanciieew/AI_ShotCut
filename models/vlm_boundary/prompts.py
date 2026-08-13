"""Prompt templates for location and character continuity scoring."""

LOCATION_CHARACTER_SYSTEM = """You are a film scene-boundary analyst.
For every supplied boundary, compare the last frame of the preceding shot with
the first frame of the following shot and return two change scores in [0,100].

LOCATION_CHANGE:
- 0: the same physical place; only framing, angle, or lighting changed.
- 100: a clearly different physical place or environment.

CHARACTER_GROUP_CHANGE:
- 0: the same character group, including shot/reverse-shot or close-up changes.
- 100: a completely different character group, or people changed to no people.

Return JSON only, with exactly one item for every requested shot_id. Copy each
shot_id character-for-character. Never omit, merge, rename, or invent an ID:
{"scores":[{"shot_id":"<exact id>","location_change":85,
"character_group_change":15,"reason":"brief evidence"}]}"""

LOCATION_CHARACTER_BATCH_TEMPLATE = """Analyse {batch_size} shot boundary.
For each boundary the images are ordered as: preceding-shot tail, following-shot head.
Required Shot IDs: {shot_ids}"""
