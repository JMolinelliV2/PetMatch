import asyncio
import math
from datetime import timedelta, timezone
import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.analysis.logging import log_event
from app.analysis.prompts import TEXT_PROMPT_VERSION, VISION_PROMPT_VERSION
from app.analysis.service import is_current, utcnow
from app.core.config import settings
from app.matching.tracking import record_recommendation
from app.db.session import SessionLocal
from app.models import AnalysisJob, FeatureSet, LostCase, Match, Notification, Observation, Pet, Photo

UNKNOWN = {"unknown", "uncertain", "not_visible", ""}
WEIGHTS = {"species": .35, "primary_color": .3, "size": .1, "coat_length": .1, "coat_pattern": .1, "breed_type": .05}
LABELS = {"species": "Especie compatible", "primary_color": "Color compatible", "size": "Tamaño compatible", "coat_length": "Pelaje compatible", "coat_pattern": "Patrón del pelaje compatible", "breed_type": "Tipo o raza compatible"}
REPORTED_STATUSES = {"PENDING", "UNVERIFIED", "POSSIBLE_MATCH", "NOT_COMPATIBLE", "NEEDS_REVIEW"}
PENDING_REPORT_BODY = "Una persona envió un avistamiento desde tu aviso. La comparación está en curso; ya podés revisar el lugar y las fotos. La identidad está por confirmar."


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def distance_meters(lat1, lon1, lat2, lon2):
    lat1, lat2 = math.radians(lat1), math.radians(lat2)
    dlat, dlon = lat2 - lat1, math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6_371_000 * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))


def current_jobs(db, owner_type, owner_id, source=None):
    query = select(AnalysisJob).where(AnalysisJob.owner_type == owner_type, AnalysisJob.owner_id == owner_id, AnalysisJob.provider == settings.ai_provider)
    if source:
        query = query.where(AnalysisJob.source_type == source)
    return [job for job in db.scalars(query)
            if job.model == (settings.ai_vision_model if job.source_type == "image" else settings.ai_text_model)
            and job.prompt_version == (VISION_PROMPT_VERSION if job.source_type == "image" else TEXT_PROMPT_VERSION)
            and is_current(db, job)]


def traits_from_result(result: FeatureSet | None):
    traits = {}
    if result:
        for name in WEIGHTS:
            attribute = result.features.get(name, {})
            value = attribute.get("value")
            if isinstance(value, str) and value.lower() not in UNKNOWN and attribute.get("confidence", 0) >= settings.linked_feature_confidence:
                traits[name] = value.strip().casefold()
    return traits


def target_traits(db, case, pet):
    # Explicit owner declarations outrank AI suggestions. The sighting itself never copies these traits.
    traits = {}
    for field, attribute in (("species", "species"), ("primary_color", "primary_color"), ("size", "size"), ("coat_length", "coat_type"), ("breed_type", "breed")):
        value = getattr(pet, attribute)
        if value and value.casefold() not in UNKNOWN:
            traits[field] = value.strip().casefold()
    jobs = current_jobs(db, "lost_case", case.id) + current_jobs(db, "pet", pet.id)
    for job in sorted(jobs, key=lambda item: aware(item.created_at), reverse=True):
        if job.status == "SUCCEEDED":
            result = db.scalar(select(FeatureSet).where(FeatureSet.analysis_job_id == job.id))
            for field, value in traits_from_result(result).items():
                traits.setdefault(field, value)
    return traits, jobs


def compare_traits(target: dict, observed: dict):
    available = sum(weight for name, weight in WEIGHTS.items() if name in target and name in observed)
    reasons = [LABELS[name] for name in WEIGHTS if name in target and target.get(name) == observed.get(name)]
    matched = sum(weight for name, weight in WEIGHTS.items() if name in target and target.get(name) == observed.get(name))
    contradiction = "species" in target and "species" in observed and target["species"] != observed["species"]
    # A clear black/white or single-color mismatch is evidence against the proposed identity.
    if target.get("primary_color") not in (None, "multicolor") and observed.get("primary_color") not in (None, "multicolor"):
        contradiction = contradiction or target["primary_color"] != observed["primary_color"]
    score = matched / available if available else 0
    compatible = not contradiction and matched + 1e-9 >= .5 and score >= settings.linked_match_threshold
    return compatible, score, reasons, contradiction


def set_result(db, observation, case, pet, status, reasons, score=None, evidence=None):
    match=db.scalar(select(Match).where(Match.observation_id==observation.id,Match.lost_case_id==case.id))
    if status in REPORTED_STATUSES:
        if match is None:
            match=Match(observation_id=observation.id,lost_case_id=case.id)
            db.add(match)
        match.feature_score=score or 0
        match.visual_score=match.visual_similarity=None
        match.geo_score=1 if "Ubicación dentro de la zona de búsqueda" in reasons else 0
        match.temporal_score=1 if "Fecha compatible con el aviso" in reasons else 0
        match.final_score=score or 0
        match.evidence_coverage=.5 if score is not None else 0
        coordinates=(case.latitude,case.longitude,observation.latitude,observation.longitude)
        match.distance_meters=distance_meters(*coordinates) if all(value is not None and math.isfinite(value) for value in coordinates) else 0
        match.explanation=reasons
        if evidence:
            for field,value in evidence.items():
                if field!="visual_provider":setattr(match,field,value)
        match.is_active=True
        if status == "POSSIBLE_MATCH":
            record_recommendation(match, "LINKED",visual_provider=(evidence or {}).get("visual_provider"),db=db)
        db.flush()
    elif match:
        match.is_active=False
    observation.matching_status = status
    observation.matching_score = score
    observation.matching_reasons = reasons
    notification = db.scalar(select(Notification).where(Notification.observation_id == observation.id, Notification.lost_case_id == case.id))
    # A report explicitly submitted for this notice reaches its owner independently of AI compatibility.
    notify = status in REPORTED_STATUSES and observation.author_id != pet.owner_id and (not match or match.status not in {"FALSE_MATCH","RESOLVED"})
    if not notify:
        if notification:
            notification.is_active = False
        return status
    kind = "POSSIBLE_MATCH" if status == "POSSIBLE_MATCH" else "REPORTED_SIGHTING"
    title = (f"Posible coincidencia con {pet.name}" if status == "POSSIBLE_MATCH" else f"Reportaron un avistamiento para {pet.name}")[:180]
    if status == "PENDING":
        body = PENDING_REPORT_BODY
    elif status == "NOT_COMPATIBLE":
        body = "Una persona envió un avistamiento desde tu aviso. La comparación automática detectó diferencias o datos que no encajan con el aviso. Revisá el lugar, las fotos y los motivos; la identidad necesita revisión humana."
    elif status == "NEEDS_REVIEW":
        body = "Una persona envió un avistamiento desde tu aviso. Falta información para compararlo automáticamente; revisá el reporte. La identidad está por confirmar."
    elif status == "UNVERIFIED":
        has_photo = db.scalar(select(Photo.id).where(Photo.owner_type == "observation", Photo.owner_id == observation.id).limit(1)) is not None
        body = "Una persona envió un avistamiento desde tu aviso. " + ("Las fotos necesitan revisión por una persona. La identidad está por confirmar." if has_photo else "No adjuntó fotos; la identidad está por confirmar.")
    else:
        body = "Las características de la foto son compatibles con tu aviso, junto con la ubicación y la fecha. Podría tratarse de tu animal; revisá el avistamiento."
    if notification is None:
        notification = Notification(owner_id=pet.owner_id, lost_case_id=case.id, observation_id=observation.id, match_id=match.id if match else None, kind=kind, title=title, body=body, email_available_at=utcnow()+timedelta(seconds=settings.mail_group_seconds))
        db.add(notification)
    else:
        notification.kind, notification.title, notification.body, notification.is_active = kind, title, body, True
        notification.match_id=match.id if match else None
    return status


def evaluate_sighting(db: Session, observation_id: UUID) -> str:
    observation = db.get(Observation, observation_id)
    if observation is None or observation.linked_case_id is None:
        return "NOT_REQUESTED"
    # All evaluators lock the case first, then its sighting, to serialize notification creation.
    case = db.scalar(select(LostCase).where(LostCase.id == observation.linked_case_id).with_for_update())
    observation = db.scalar(select(Observation).where(Observation.id == observation_id).with_for_update().execution_options(populate_existing=True))
    if case is None or observation is None:
        return "INACTIVE"
    pet = db.get(Pet, case.pet_id)
    if case.status != "ACTIVE" or case.moderation_status!="VISIBLE" or observation.moderation_status!="VISIBLE":
        return set_result(db, observation, case, pet, "INACTIVE", ["El aviso ya no está activo"])
    if aware(observation.observed_at) < aware(case.lost_at) or aware(observation.observed_at) > utcnow() + timedelta(minutes=1):
        return set_result(db, observation, case, pet, "NOT_COMPATIBLE", ["La fecha no es compatible con el aviso"])
    coordinates = (case.latitude, case.longitude, observation.latitude, observation.longitude)
    if any(value is None or not math.isfinite(value) for value in coordinates):
        return set_result(db, observation, case, pet, "NEEDS_REVIEW", ["Falta una ubicación para comparar"])
    distance = distance_meters(*coordinates)
    allowance = min(case.location_accuracy_meters or 0, 1000) + min(observation.location_accuracy_meters or 0, 1000)
    if distance > case.search_radius_meters + allowance:
        return set_result(db, observation, case, pet, "NOT_COMPATIBLE", ["El avistamiento está fuera del radio de búsqueda"])
    geographic = ["Fecha compatible con el aviso", "Ubicación dentro de la zona de búsqueda"]
    photos = list(db.scalars(select(Photo).where(Photo.owner_type == "observation", Photo.owner_id == observation.id)))
    if not photos:
        return set_result(db, observation, case, pet, "UNVERIFIED", geographic + ["Avistamiento declarado por una persona, sin foto"])
    jobs = current_jobs(db, "observation", observation.id, "image")
    expected = target_traits(db, case, pet)
    target, target_jobs = expected
    pending = {"PENDING", "DISPATCHING", "QUEUED", "RUNNING"}
    from app.matching.engine import should_wait,vectors,visual_evidence,evidence as collect_evidence
    from app.matching.scoring import feature_similarity,combine,notification_evidence
    visual_jobs=list(db.scalars(select(AnalysisJob).where(AnalysisJob.owner_type=="observation",AnalysisJob.owner_id==observation.id,AnalysisJob.source_type=="embedding")))
    if any(should_wait(job) for job in jobs + target_jobs + [job for job in visual_jobs if is_current(db,job)]):
        return set_result(db, observation, case, pet, "PENDING", geographic + ["Analizando las fotos y las características del aviso"])
    observed_results = []
    for photo in photos:
        photo_jobs = [job for job in jobs if job.photo_id == photo.id and job.status == "SUCCEEDED"]
        photo_jobs.sort(key=lambda item: aware(item.created_at), reverse=True)
        result = db.scalar(select(FeatureSet).where(FeatureSet.analysis_job_id == photo_jobs[0].id)) if photo_jobs else None
        traits = traits_from_result(result)
        if traits:
            observed_results.append(traits)
    comparisons = [compare_traits(target, traits) for traits in observed_results]
    if any(item[3] for item in comparisons):
        return set_result(db, observation, case, pet, "NOT_COMPATIBLE", ["Las fotos muestran una especie o un color diferente al aviso"])
    # A linked report inherits the proposed species; that alone is not independent evidence.
    observed,_=collect_evidence(db,"observation",observation.id,{})
    target,_=collect_evidence(db,"lost_case",case.id,{"species":pet.species,"sex":pet.sex,
        "primary_color":pet.primary_color,"size":pet.size,"distinctive_features":pet.distinctive_features})
    target,_=collect_evidence(db,"pet",pet.id,target)
    feature,coverage,reasons,contradiction=feature_similarity(target,observed)
    if contradiction or target.get("_species_conflict") or observed.get("_species_conflict"):
        return set_result(db,observation,case,pet,"NOT_COMPATIBLE",["Las características presentan contradicciones con el aviso"])
    observed_vectors=vectors(db,(Photo.owner_type=="observation") & (Photo.owner_id==observation.id)) if settings.embeddings_enabled else []
    raw,provider,quality=visual_evidence(db,observed_vectors,case)
    days=(aware(observation.observed_at)-aware(case.lost_at)).total_seconds()/86400
    score,visual,geo,temporal=combine(feature,raw,distance,min(case.search_radius_meters,settings.matching_max_radius_meters),days,allowance,provider=provider or "open_clip",quality=quality)
    if raw is not None and notification_evidence(score,coverage,feature,geo):
        return set_result(db,observation,case,pet,"POSSIBLE_MATCH",geographic+reasons+["Similitud visual entre las fotos"],score,
            {"feature_score":feature,"visual_score":visual,"visual_similarity":raw,"geo_score":geo,
             "temporal_score":temporal,"evidence_coverage":coverage,"visual_provider":provider})
    return set_result(db, observation, case, pet, "UNVERIFIED", geographic + ["Las fotos no aportaron suficientes rasgos para una comparación automática"])


def related_ids(db, owner_type, owner_id):
    if owner_type == "observation":
        return [owner_id]
    cases = [owner_id] if owner_type == "lost_case" else list(db.scalars(select(LostCase.id).where(LostCase.pet_id == owner_id)))
    return list(db.scalars(select(Observation.id).where(Observation.linked_case_id.in_(cases)).order_by(Observation.linked_case_id, Observation.id)))


def mark_related_pending(db, owner_type, owner_id):
    from app.matching.engine import request_matching
    request_matching(db, owner_type, owner_id)
    identities = related_ids(db, owner_type, owner_id)
    if identities:
        linked_identities = select(Observation.id).where(Observation.id.in_(identities), Observation.linked_case_id.is_not(None))
        db.execute(update(Observation).where(Observation.id.in_(linked_identities)).values(matching_status="PENDING"))
        db.execute(update(Match).where(Match.observation_id.in_(linked_identities)).values(explanation=["La comparación está en curso; el avistamiento sigue disponible para revisión"]))
        db.execute(update(Notification).where(Notification.observation_id.in_(linked_identities)).values(kind="REPORTED_SIGHTING",title="Avistamiento reportado · comparación en curso",body=PENDING_REPORT_BODY))


def reconcile_related(owner_type, owner_id, session_factory=None):
    factory = session_factory or SessionLocal
    with factory() as db:
        identities = related_ids(db, owner_type, owner_id)
    for identity in identities:
        with factory() as db:
            evaluate_sighting(db, identity)
            db.commit()


def reconcile_pending(session_factory=None):
    factory = session_factory or SessionLocal
    with factory() as db:
        identities = list(db.scalars(select(Observation.id).where(Observation.linked_case_id.is_not(None), Observation.matching_status == "PENDING").order_by(Observation.created_at).limit(50)))
    for identity in identities:
        with factory() as db:
            evaluate_sighting(db, identity)
            db.commit()


async def reconciliation_loop():
    while True:
        try:
            await asyncio.to_thread(reconcile_pending)
        except Exception:
            log_event("linked_matching_unavailable", level=logging.WARNING)
        await asyncio.sleep(5)
