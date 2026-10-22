"""Private outcome counts over distinct recommendations, including closed searches."""
from datetime import timedelta
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import case, func, select
from pydantic import AwareDatetime
from app.admin_period import period_filters
from app.admin_access import administrator
from app.analysis.service import utcnow
from app.db.session import get_db
from app.models import LostCase, Match, MatchFeedbackEvent, Observation, Pet

router = APIRouter(prefix="/admin/matching", tags=["admin-matching"])
SOURCE = Literal["all", "GENERAL", "LINKED"]
OUTCOME = Literal["all", "positive", "false", "uncertain", "pending"]
DATASET = Literal["all", "live", "legacy"]
latest_status = select(MatchFeedbackEvent.status).where(MatchFeedbackEvent.match_id == Match.id)\
    .order_by(MatchFeedbackEvent.created_at.desc(), MatchFeedbackEvent.id.desc()).limit(1).correlate(Match).scalar_subquery()
latest_response_at = select(MatchFeedbackEvent.created_at).where(MatchFeedbackEvent.match_id == Match.id)\
    .order_by(MatchFeedbackEvent.created_at.desc(), MatchFeedbackEvent.id.desc()).limit(1).correlate(Match).scalar_subquery()
outcome = case(
    (latest_status == "RESOLVED", "positive"),
    (latest_status == "FALSE_MATCH", "false"),
    (latest_status == "CONFIRMED_RELEVANT", "uncertain"),
    else_="pending")


def scope(days, source, dataset, from_at=None, to_at=None,provider="all",model=None,revision=None):
    filters = [Match.recommended_at.is_not(None)]
    if from_at is not None or to_at is not None:
        filters.extend(period_filters(Match.recommended_at, from_at, to_at))
    elif days:
        filters.append(Match.recommended_at >= utcnow() - timedelta(days=days))
    if source != "all":
        filters.append(Match.recommendation_source == source)
    if dataset != "all":
        filters.append(Match.recommendation_snapshot["legacy"].as_boolean().is_(dataset == "legacy"))
    if provider!="all":filters.append(Match.recommendation_snapshot["visual_provider"].as_string()==provider)
    if model:filters.append(Match.recommendation_snapshot["actual_visual_space"]["model"].as_string()==model)
    if revision:filters.append(Match.recommendation_snapshot["actual_visual_space"]["revision"].as_string()==revision)
    return filters


def counters(db, filters):
    counts = {"total": 0, "positive": 0, "false": 0, "uncertain": 0, "pending": 0}
    rows = db.execute(select(outcome.label("outcome"), func.count()).where(*filters).group_by(outcome))
    for category, total in rows:
        counts[category] = total
        counts["total"] += total
    decided = counts["positive"] + counts["false"]
    reviewed = decided + counts["uncertain"]
    return {**counts, "decided": decided, "reviewed": reviewed,
        "positive_rate": round(100 * counts["positive"] / decided, 1) if decided else None,
        "review_rate": round(100 * reviewed / counts["total"], 1) if counts["total"] else None}


@router.get("")
def dashboard(response: Response, days: int = Query(default=30, ge=0, le=3650),
              source: SOURCE = "all", dataset: DATASET = "all", result: OUTCOME = "all",
              provider: Literal["all","pet_reid","open_clip","NONE"]="all",model: str | None=Query(default=None,max_length=120),
              revision: str | None=Query(default=None,max_length=80),
              from_at: AwareDatetime | None = None, to_at: AwareDatetime | None = None,
              limit: int = Query(default=25, ge=1, le=100), offset: int = Query(default=0, ge=0, le=100000),
              db=Depends(get_db), user=Depends(administrator)):
    response.headers["Cache-Control"] = "no-store"
    filters = scope(days, source, dataset, from_at, to_at,provider,model,revision)
    summary = counters(db, filters)
    sources = [{"source": name, **counters(db, [*filters, Match.recommendation_source == name])} for name in ("GENERAL", "LINKED")]
    legacy_count = db.scalar(select(func.count()).select_from(Match).where(*filters, Match.recommendation_snapshot["legacy"].as_boolean().is_(True))) or 0
    list_filters = [*filters, *([outcome == result] if result != "all" else [])]
    total = db.scalar(select(func.count()).select_from(Match).where(*list_filters)) or 0
    history_count = select(func.count()).select_from(MatchFeedbackEvent).where(MatchFeedbackEvent.match_id == Match.id).correlate(Match).scalar_subquery()
    query = select(Match, LostCase, Observation, Pet, outcome.label("outcome"), history_count.label("history_count"), latest_response_at.label("last_response_at"))\
        .join(LostCase, Match.lost_case_id == LostCase.id).join(Observation, Match.observation_id == Observation.id)\
        .join(Pet, LostCase.pet_id == Pet.id).where(*list_filters)\
        .order_by(Match.recommended_at.desc(), Match.id.desc()).offset(offset).limit(limit)
    items = [{"id": match.id, "lost_case_public_id": case_record.public_id, "observation_public_id": observation.public_id,
              "pet_name": pet.name, "species": pet.species, "source": match.recommendation_source,
              "outcome": category, "recommended_score": match.recommended_score, "current_score": match.final_score,
              "feature_score":match.feature_score,"visual_score":match.visual_score,"raw_visual_similarity":match.visual_similarity,
              "geo_score":match.geo_score,"temporal_score":match.temporal_score,"evidence_coverage":match.evidence_coverage,
              "distance_meters":match.distance_meters,"recommendation_snapshot":match.recommendation_snapshot,
              "first_viewed_at":match.first_viewed_at,"first_viewed_rank":match.first_viewed_rank,"best_viewed_rank":match.best_viewed_rank,
              "recommended_at": match.recommended_at, "feedback_at": last_response_at,
              "case_status": case_record.status, "active": match.is_active, "history_count": event_count,
              "legacy": bool(match.recommendation_snapshot.get("legacy"))}
             for match, case_record, observation, pet, category, event_count, last_response_at in db.execute(query)]
    return {"summary": summary, "sources": sources, "legacy_count": legacy_count,
            "items": items, "total": total, "limit": limit, "offset": offset,
            "period_days": days, "generated_at": utcnow()}


@router.get("/{identity}/history")
def history(identity: UUID, response: Response, db=Depends(get_db), user=Depends(administrator)):
    if db.get(Match, identity) is None:
        raise HTTPException(status_code=404, detail="Coincidencia no encontrada.")
    response.headers["Cache-Control"] = "no-store"
    events = db.scalars(select(MatchFeedbackEvent).where(MatchFeedbackEvent.match_id == identity)
        .order_by(MatchFeedbackEvent.created_at.desc(), MatchFeedbackEvent.id.desc()).limit(50))
    return {"items": [{"id": event.id, "status": event.status, "previous_status": event.previous_status,
        "recovered": event.recovered, "score": event.score, "legacy": event.legacy, "created_at": event.created_at} for event in events]}
