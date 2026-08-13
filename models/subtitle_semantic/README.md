# Subtitle Semantic Continuity Adapter

This Adapter converts timed ASR subtitles into narrative continuity evidence at shot
boundaries. It never decides final cuts and never writes the database or storage itself.

Processing is hierarchical:

1. Split a long subtitle timeline into bounded chunks and summarise each chunk.
2. Read the ordered summaries as one film and discover at most 10 core transitions.
3. Search each interval between core transitions for at most 5 additional local transitions.
4. Map candidates to the nearest shot boundary, deduplicate collisions, and apply one
   uniform semantic re-evaluation standard.
5. Return `subtitle_continuity` in `[0,1]`; `1` means narrative continuity is strongest.

The semantic standard considers persistent changes in goals, conflict/stakes,
information/revelations, relationships, and causal direction. Speaker changes or visual
cuts alone are not narrative transitions.

Configuration is supplied through `core.config.Settings`. The provider key is read from
`DEEPSEEK_API_KEY`. Code, weight, and dataset licences remain `unknown`; registry metadata
therefore marks commercial use as false.
