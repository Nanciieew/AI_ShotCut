"""Concise prompts for hierarchical subtitle narrative-transition analysis."""

SUMMARY_SYSTEM = """Analyse timed film subtitles as narrative evidence. Return valid JSON
only. Use only supported events. Keep every reason at 80 Chinese characters or fewer."""

SUMMARY_USER = """Summarise goals, conflicts, revelations, relationship changes, causal
direction and unresolved state. Preserve important millisecond timestamps.
Schema: {{"summary":"...","events":[{{"timestamp_ms":0,"event":"..."}}]}}
Subtitles:
{transcript}"""

GLOBAL_USER = """From these ordered summaries, return at most {limit} persistent core
narrative turns. A core turn changes goals, stakes, known information, relationships or
causal direction; exclude speaker/topic/camera changes.
Schema: {{"candidates":[{{"timestamp_ms":0,"reason":"..."}}]}}
Summaries: {summaries}"""

LOCAL_BATCH_USER = """Find additional local narrative turns for every interval. Do not
repeat core timestamps. Return every interval_id exactly once; timestamps must remain
inside its [start_ms,end_ms). An interval may have zero candidates.
Schema: {{"intervals":[{{"interval_id":"i0","candidates":[
{{"timestamp_ms":0,"reason":"..."}}]}}]}}
Core timestamps: {core_timestamps}
Intervals: {intervals}"""

RESCORE_USER = """Score every boundary once using one standard. subtitle_continuity is
in [0,1]: 1=unchanged narrative state, 0=strongest persistent turn. Ignore mere speaker,
silence, wording or visual-cut changes. Transition strength T=1-continuity:
<0.10 continuation; 0.10-0.25 minor; 0.25-0.45 local; 0.45-0.65 significant;
0.65-0.85 major; >=0.85 core/climactic.
Schema: {{"boundaries":[{{"boundary_id":"b0","subtitle_continuity":0.0,
"reason":"..."}}]}}
Contexts: {contexts}"""

JSON_REPAIR_USER = """Convert the following malformed model output into valid JSON that
matches this schema. Preserve values; do not add analysis or markdown.
Schema: {schema}
Malformed output:
{raw}"""
