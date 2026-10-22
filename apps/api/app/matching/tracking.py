"""Record actual recommendations once; receipts alone are not recommendations."""
from importlib.metadata import version
from app.analysis.prompts import TEXT_PROMPT_VERSION, VISION_PROMPT_VERSION
from app.analysis.service import utcnow
from app.core.config import settings
from app.embeddings.specs import openclip_spec,pet_reid_spec
from app.models import MatchFeedbackEvent


def record_recommendation(match, source, *, visual_provider=None, db=None):
    if match.recommended_at is not None:
        return
    match.recommended_at = utcnow()
    match.recommendation_source = source
    match.recommended_score = match.final_score
    match.recommendation_snapshot = {
        "legacy": False, "tracking_version": "matching-tracking-v2", "scoring_version":"weighted-evidence-v1",
        "visual_provider":visual_provider or "NONE",
        "actual_visual_space":(pet_reid_spec() if visual_provider=="pet_reid" else openclip_spec()).to_dict() if visual_provider else None,
        "ai_enabled": settings.ai_enabled, "embeddings_enabled": settings.embeddings_enabled,
        "text_model": settings.ai_text_model, "vision_model": settings.ai_vision_model,
        "text_prompt": TEXT_PROMPT_VERSION, "vision_prompt": VISION_PROMPT_VERSION,
        "embedding_spaces": [openclip_spec().to_dict(),pet_reid_spec().to_dict()],
        "pet_reid_enabled": settings.pet_reid_enabled,
        "visual_best_weight":settings.visual_best_weight,
        "visual_calibration":{"open_clip":[settings.openclip_visual_floor,settings.openclip_visual_ceiling],
                              "pet_reid":[settings.pet_reid_visual_floor,settings.pet_reid_visual_ceiling]},
        "candidate_threshold": settings.matching_candidate_threshold,
        "notify_threshold": settings.matching_notify_threshold,
        "linked_threshold": settings.linked_match_threshold,
        "notify_gate":{"minimum_coverage":settings.matching_notify_min_coverage,"minimum_feature":settings.matching_notify_min_feature,
                       "minimum_geo":settings.matching_notify_min_geo},
        "geography":{"maximum_radius_meters":settings.matching_max_radius_meters},"temporal_days":settings.matching_temporal_days,
        "runtime_versions":{"pillow":version("Pillow")},
    }
    if db is not None:
        from sqlalchemy import or_, select
        from app.analysis.service import is_current
        from app.models import AnalysisJob, FeatureSet, LostCase
        case=db.get(LostCase,match.lost_case_id)
        jobs=db.scalars(select(AnalysisJob).join(FeatureSet,FeatureSet.analysis_job_id==AnalysisJob.id).where(
            AnalysisJob.status=="SUCCEEDED",or_(
                (AnalysisJob.owner_type=="observation")&(AnalysisJob.owner_id==match.observation_id),
                (AnalysisJob.owner_type=="lost_case")&(AnalysisJob.owner_id==case.id),
                (AnalysisJob.owner_type=="pet")&(AnalysisJob.owner_id==case.pet_id))).order_by(AnalysisJob.created_at.desc()).limit(30))
        match.recommendation_snapshot["evidence_versions"]=[{"provider":job.provider,"model":job.model,
            "revision":(job.metrics or {}).get("model_revision","unknown"),"source":job.source_type,
            "prompt_version":job.prompt_version,"preprocessing_version":job.preprocessing_version} for job in jobs if is_current(db,job)]


def record_feedback(db, match, user, payload, *, already_recovered=False):
    if match.feedback_at is None or match.status != payload.status or (payload.recovered and not already_recovered):
        db.add(MatchFeedbackEvent(match_id=match.id, actor_id=user.id,
            previous_status=match.status, status=payload.status, recovered=payload.recovered,
            score=match.final_score, legacy=False, created_at=utcnow(),context_snapshot={
                "recommendation":match.recommendation_snapshot,"first_viewed_rank":match.first_viewed_rank,
                "first_viewed_at":match.first_viewed_at.isoformat() if match.first_viewed_at else None}))
        return True
    return False
