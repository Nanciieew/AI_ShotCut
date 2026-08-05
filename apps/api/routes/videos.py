"""
Video management routes.

POST   /api/v1/videos              — Upload a video
POST   /api/v1/videos/{id}/analyze-shots — Start shot analysis pipeline
GET    /api/v1/videos/{id}          — Get video metadata
"""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.dependencies import get_db
from apps.api.services.analysis_service import submit_full_pipeline

router = APIRouter(tags=["videos"])


@router.post("/videos")
async def upload_video(
    file: UploadFile = File(...),
    project_id: str = Form(default="default"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a video file, auto-create project + video records.

    Saves to: data/projects/{project_id}/videos/{video_id}/source/{filename}
    Returns video_id for subsequent pipeline submission.
    """
    import os, uuid, shutil

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    video_id = uuid.uuid4().hex[:12]
    filename = file.filename or "untitled.mp4"

    # Ensure safe filename
    safe_name = "".join(c for c in filename if c.isalnum() or c in "._- ")
    if not safe_name.lower().endswith(".mp4"):
        safe_name += ".mp4"

    # Auto-create project directory
    project_dir = os.path.join(storage_root, "projects", project_id)
    video_dir = os.path.join(project_dir, "videos", video_id, "source")
    os.makedirs(video_dir, exist_ok=True)

    # Save file
    dest_path = os.path.join(video_dir, safe_name)
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Build storage URI
    source_uri = f"storage://projects/{project_id}/videos/{video_id}/source/{safe_name}"
    file_size = os.path.getsize(dest_path)

    # Create DB records (sync)
    from core.database.repositories import VideoRepository
    from core.database.session_sync import get_sync_session

    with get_sync_session() as session:
        video_repo = VideoRepository(session)
        video_repo.ensure_project(project_id, name=project_id)
        video_repo.create(video_id=video_id, project_id=project_id, source_uri=source_uri)
        session.commit()

    return {
        "video_id": video_id,
        "project_id": project_id,
        "filename": safe_name,
        "source_uri": source_uri,
        "size_bytes": file_size,
        "upload_status": "SUCCEEDED",
        "message": f"Uploaded. Submit pipeline: POST /videos/{video_id}/analyze-shots",
    }


@router.post("/videos/{video_id}/analyze-shots")
async def start_shot_analysis(
    video_id: str,
    video_path: str = Form(default="", description="Path to video file (auto-resolved if empty)"),
    project_id: str = Form(default="default"),
    extract_keyframes: bool = Form(default=False),
    scene_analysis: bool = Form(default=False),
    shot_model: str = Form(default="ffmpeg_scene"),
    score_mode: str = Form(default="weighted"),
    location_weight: int = Form(default=35, ge=1, le=10),
    character_weight: int = Form(default=35, ge=1, le=10),
    plot_weight: int = Form(default=30, ge=1, le=10),
    cut_intensity: str = Form(default="medium"),
    min_distance_s: int = Form(default=12, ge=5, le=60),
    db: AsyncSession = Depends(get_db),
):
    """Start video analysis pipeline.

    Pipeline: normalize_video → detect_shots
      → [extract_keyframes + subtitle.transcribe]
        → [scene.score_vlm + scene.score_plot]
          → scene.merge_scores → pipeline_complete

    Set scene_analysis=True to enable full scene scoring.
    score_mode: location_only | character_only | plot_only | custom | weighted
    video_path can be empty — auto-resolved from the uploaded video's source_uri.
    """
    # Auto-resolve video_path from uploaded video if empty
    if not video_path:
        from sqlalchemy import select
        from core.database.models import Video as VideoModel
        result = await db.execute(select(VideoModel).where(VideoModel.video_id == video_id))
        video_row = result.scalar_one_or_none()
        if video_row is None:
            raise HTTPException(status_code=404, detail=f"Video {video_id} not found. Upload first via POST /videos.")
        video_path = video_row.source_uri
        project_id = video_row.project_id or project_id

    result = await submit_full_pipeline(
        db=db,
        video_path=video_path,
        project_id=project_id,
        extract_keyframes=extract_keyframes,
        scene_analysis=scene_analysis,
        score_mode=score_mode,
        location_weight=location_weight,
        character_weight=character_weight,
        plot_weight=plot_weight,
        cut_intensity=cut_intensity,
        min_distance_s=min_distance_s,
    )
    return result


@router.get("/videos/{video_id}")
async def get_video(
    video_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get video metadata and analysis status."""
    from sqlalchemy import select

    from core.database.models import Video

    result = await db.execute(select(Video).where(Video.video_id == video_id))
    video = result.scalar_one_or_none()

    if video is None:
        raise HTTPException(status_code=404, detail=f"Video {video_id} not found")

    return {
        "video_id": video.video_id,
        "project_id": video.project_id,
        "source_uri": video.source_uri,
        "normalized_uri": video.normalized_uri,
        "duration_ms": video.duration_ms,
        "fps_num": video.fps_num,
        "fps_den": video.fps_den,
        "width": video.width,
        "height": video.height,
        "created_at": video.created_at.isoformat() if video.created_at else None,
    }
