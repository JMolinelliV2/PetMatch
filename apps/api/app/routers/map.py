from datetime import timedelta
from typing import Literal
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from sqlalchemy import and_,exists,select,text,or_
from app.analysis.service import utcnow
from app.db.session import get_db
from app.models import LostCase, Match, Observation, Pet, Photo
from app.report_text import observation_description
from app.routers.public_lost_dogs import active_dogs
from app.routers.public_observations import observation_photo_exists, public_photo_url, visible_observations
from app.matching.linked import distance_meters
router=APIRouter(prefix="/public/map",tags=["public-map"])


@router.get("")
def public_map(response:Response,species:Literal["", "dog", "cat"]=Query(default=""),days:int=Query(default=30,ge=0,le=3650),
    latitude:float|None=Query(default=None,ge=-90,le=90),longitude:float|None=Query(default=None,ge=-180,le=180),
    radius_km:int=Query(default=15,ge=1,le=200),compatible_only:bool=False,layer:Literal["all","lost"]="all",db=Depends(get_db)):
    if (latitude is None)!=(longitude is None):raise HTTPException(status_code=422,detail="Falta la referencia completa de ubicación.")
    points=[]
    case_query=active_dogs().where(LostCase.latitude.is_not(None),LostCase.longitude.is_not(None),LostCase.lost_at<=utcnow()+timedelta(minutes=1))
    obs_query=visible_observations().where(Observation.latitude.is_not(None),Observation.longitude.is_not(None))
    if species:
        case_query=case_query.where(Pet.species==species);obs_query=obs_query.where(Observation.species==species)
    if days:
        case_query=case_query.where(LostCase.lost_at>=utcnow()-timedelta(days=days))
        obs_query=obs_query.where(Observation.observed_at>=utcnow()-timedelta(days=days))
    if compatible_only:
        compatible_matches=select(Match.observation_id).join(Observation,Match.observation_id==Observation.id).where(Match.is_active.is_(True),Match.status.not_in(["FALSE_MATCH","RESOLVED"]),or_(Observation.linked_case_id.is_(None),Observation.matching_status=="POSSIBLE_MATCH",Match.status=="CONFIRMED_RELEVANT")).correlate(None)
        obs_query=obs_query.where(Observation.id.in_(compatible_matches))
    if latitude is not None:
        if db.bind.dialect.name=="postgresql":
            case_query=case_query.where(text("ST_DWithin(ST_SetSRID(ST_MakePoint(lost_cases.longitude,lost_cases.latitude),4326)::geography,ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,:radius)")).params(lon=longitude,lat=latitude,radius=radius_km*1000)
            obs_query=obs_query.where(text("ST_DWithin(ST_SetSRID(ST_MakePoint(observations.longitude,observations.latitude),4326)::geography,ST_SetSRID(ST_MakePoint(:lon,:lat),4326)::geography,:radius)")).params(lon=longitude,lat=latitude,radius=radius_km*1000)
        else:
            delta=radius_km/111
            case_query=case_query.where(LostCase.latitude.between(latitude-delta,latitude+delta))
            obs_query=obs_query.where(Observation.latitude.between(latitude-delta,latitude+delta))
    def include(lat,lon):return latitude is None or distance_meters(latitude,longitude,lat,lon)<=radius_km*1000
    photo_exists=exists().where(or_(
        and_(Photo.owner_type=="lost_case",Photo.owner_id==LostCase.id),
        and_(Photo.owner_type=="pet",Photo.owner_id==Pet.id),
    )).correlate(LostCase,Pet)
    for case,pet,has_photo in db.execute(case_query.add_columns(photo_exists).order_by(LostCase.lost_at.desc()).limit(500)):
        if include(case.latitude,case.longitude):points.append({"id":str(case.id),"public_id":case.public_id,"layer":"lost","title":pet.name,"species":pet.species,"latitude":round(case.latitude,2),"longitude":round(case.longitude,2),"area":case.public_location,"when":case.lost_at,"url":f"/perdidos/{case.id}","photo_url":f"/api/v1/public/lost-animals/{case.id}/photo" if has_photo else None})
    observations=db.execute(obs_query.add_columns(observation_photo_exists()).order_by(Observation.observed_at.desc()).limit(500)) if layer=="all" else ()
    for obs,has_photo in observations:
        description=observation_description(obs)
        if include(obs.latitude,obs.longitude):points.append({"id":str(obs.id),"public_id":obs.public_id,"layer":"found" if obs.source_type=="FOUND_ANIMAL" else "sighting","title":"Mascota encontrada" if obs.source_type=="FOUND_ANIMAL" else "Avistamiento","species":obs.species,"sex":obs.sex,"primary_color":obs.primary_color,"size":obs.size,"description_excerpt":description[:280]+("…" if len(description)>280 else ""),"latitude":round(obs.latitude,2),"longitude":round(obs.longitude,2),"area":obs.public_location,"when":obs.observed_at,"url":None,"photo_url":public_photo_url(obs.id,has_photo)})
    response.headers["Cache-Control"]="no-store"
    return {"points":points,"approximate":True,"limit_per_layer":500}
