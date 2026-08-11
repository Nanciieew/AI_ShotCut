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
    import os
    import uuid

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
    score_mode: str = Form(default="location_only"),
    location_w: str = Form(default=""),
    character_w: str = Form(default=""),
    plot_w: str = Form(default=""),
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
    score_mode: location_only | character_only | plot_only | custom
    video_path can be empty — auto-resolved.
    """
    # Auto-resolve video_path from uploaded video if empty
    if not video_path:
        from sqlalchemy import select

        from core.database.models import Video as VideoModel

        db_result = await db.execute(select(VideoModel).where(VideoModel.video_id == video_id))
        video_row = db_result.scalar_one_or_none()
        if video_row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Video {video_id} not found. Upload first via POST /videos.",
            )
        video_path = video_row.source_uri
        project_id = video_row.project_id or project_id

    result = await submit_full_pipeline(
        db=db,
        video_path=video_path,
        project_id=project_id,
        extract_keyframes=extract_keyframes,
        scene_analysis=scene_analysis,
        score_mode=score_mode,
        location_weight=int(location_w) if location_w else 1,
        character_weight=int(character_w) if character_w else 1,
        plot_weight=int(plot_w) if plot_w else 1,
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


@router.get("/videos/{video_id}/keyframes/{shot_id}/{img_name}")
async def serve_keyframe(
    video_id: str,
    shot_id: str,
    img_name: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve a keyframe JPEG image from the project's artifacts."""
    import os

    from fastapi.responses import FileResponse
    from sqlalchemy import select

    from core.database.models import Video as VideoModel

    db_result = await db.execute(select(VideoModel).where(VideoModel.video_id == video_id))
    video = db_result.scalar_one_or_none()
    if video is None:
        raise HTTPException(404, "Video not found")

    storage_root = os.getenv("STORAGE_ROOT", "./data")
    project_id = video.project_id or "default"
    kf_dir = os.path.join(
        storage_root,
        "projects",
        project_id,
        "videos",
        video_id,
        "artifacts",
        "shot_keyframes",
        "1.0.0",
    )
    img_path = os.path.join(kf_dir, f"{shot_id}_{img_name}.jpg")

    # Fallback naming convention
    if not os.path.exists(img_path):
        # Try shot_000001_img_1.jpg format
        alt = os.path.join(kf_dir, f"{shot_id}_{img_name.replace('img_', '_img_')}.jpg")
        if os.path.exists(alt):
            img_path = alt
        else:
            # Try numeric suffix: img_2 → position 1/2 → _001_002
            idx = img_name.replace("img_", "")
            for suffix in [f"001_00{idx}", f"003_00{idx}"]:
                alt2 = os.path.join(kf_dir, f"{shot_id}_{suffix}.jpg")
                if os.path.exists(alt2):
                    img_path = alt2
                    break

    if not os.path.exists(img_path):
        raise HTTPException(404, f"Keyframe not found: {shot_id}/{img_name}")

    return FileResponse(img_path, media_type="image/jpeg")
