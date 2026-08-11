"""VLM/LLM Adapter factory — DEPRECATED (2026-08).

This factory is never imported by production code. Model instantiation
happens inline in analysis_service.py and worker tasks. Will be replaced
by core/mcp/registry.py in Phase 2 MCP migration.
"""

_ADAPTERS: dict[str, type] = {}


def _register():
    global _ADAPTERS
    if _ADAPTERS:
        return
    try:
        from models.vlm_boundary.adapter import VLMSceneBoundaryAdapter

        _ADAPTERS["vlm_scene_boundary"] = VLMSceneBoundaryAdapter
    except ImportError:
        pass
    try:
        from models.llm_plot.adapter import PlotEventAdapter

        _ADAPTERS["plot_event"] = PlotEventAdapter
    except ImportError:
        pass
    try:
        from models.ffmpeg_scene.adapter import FFmpegSceneAdapter

        _ADAPTERS["ffmpeg_scene"] = FFmpegSceneAdapter
    except ImportError:
        pass


def get_adapter_class(name: str):
    _register()
    cls = _ADAPTERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown model: {name}. Available: {list(_ADAPTERS.keys())}")
    return cls


def create_adapter(name: str, api_key: str | None = None):
    cls = get_adapter_class(name)
    adapter = cls()
    adapter.load(api_key=api_key)
    return adapter
