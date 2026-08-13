"""Prompts for hierarchical subtitle-based narrative transition analysis."""

SUMMARY_SYSTEM = """You analyse film subtitles as timed narrative evidence.
Return JSON only. Do not invent events not supported by the subtitles."""

SUMMARY_USER = """Summarise this chronological subtitle block. Preserve the important
character goals, conflicts, revelations, relationship changes, causal direction, and
unresolved state. Include timestamps in milliseconds for important events.

Return: {{\"summary\": \"...\", \"events\": [{{\"timestamp_ms\": 0, \"event\": \"...\"}}]}}

Subtitle block:
{transcript}
"""

GLOBAL_USER = """Read the ordered summaries as one complete film. Identify at most
{limit} core narrative transition timestamps. A core transition must materially change
the story's goals, conflict or stakes, known information, relationships, causal direction,
or produce a persistent/irreversible new state. Return timestamps only; do not assign a
score here.

Return: {{\"candidates\": [{{\"timestamp_ms\": 0, \"reason\": \"...\"}}]}}

Ordered summaries:
{summaries}
"""

LOCAL_USER = """Within [{start_ms}, {end_ms}) identify at most {limit} additional local
narrative transitions not already represented by the supplied core timestamps. A local
transition changes the dramatic beat or narrative state, not merely the speaker, camera,
location wording, or topic phrasing. Return timestamps only; do not assign a score here.

Return: {{\"candidates\": [{{\"timestamp_ms\": 0, \"reason\": \"...\"}}]}}
Core timestamps: {core_timestamps}
Relevant summaries:
{summaries}
"""

RESCORE_USER = """Evaluate every supplied shot boundary with one consistent standard.
For each boundary return subtitle_continuity in [0,1], where 1 means the narrative state
continues unchanged and 0 means the strongest persistent/irreversible transition. Consider
changes in goals, conflict/stakes, information/revelation, relationships, causal direction,
and persistence. Do not reward a mere speaker change, silence, wording change, or visual cut.
Use this transition-strength rubric T = 1 - subtitle_continuity consistently:
T < 0.10 continuation; 0.10-0.25 minor beat; 0.25-0.45 local transition;
0.45-0.65 significant transition; 0.65-0.85 major transition; >=0.85 core/climactic turn.

Return all items exactly once:
{{\"boundaries\": [{{\"boundary_id\": \"b0\", \"subtitle_continuity\": 0.0,
\"reason\": \"...\"}}]}}

Boundary contexts:
{contexts}
"""
