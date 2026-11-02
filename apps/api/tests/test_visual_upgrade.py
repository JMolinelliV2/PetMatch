"""Contract tests use synthetic vectors/images: no weights, internet, Redis or SMTP."""
import asyncio
from dataclasses import replace
from datetime import timedelta
from io import BytesIO
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx2 as httpx
from PIL import Image
import pytest
from sqlalchemy import select

from app.analysis import tasks
from app.analysis.providers import OllamaProvider, ProviderError
from app.analysis.queue import queue_name
from app.analysis.service import is_current, schedule_photo, utcnow
from app.core.config import settings
from app.embeddings.backfill import backfill
from app.embeddings.cropper import PetCropper, decode_image, image_quality
from app.embeddings.provider import EmbeddingResult, normalize
from app.embeddings.service import schedule_embedding
from app.embeddings.specs import compatible, openclip_spec, pet_reid_spec, select_spec, spec_for_photo
from app.matching import engine, linked
from app.matching.scoring import aggregate_visual_similarity, combine, notification_evidence
from app.models import AnalysisJob, Embedding, FeatureSet, LostCase, Observation, Pet, Photo, User
from tests.test_analysis import evidence


def jpeg(size=(512,300)):
    stream=BytesIO()
    Image.new("RGB",size,"brown").save(stream,format="JPEG")
    return stream.getvalue()


def records(db, species="dog"):
    user=User(email="visual@example.test",name="Owner",password_hash="unused",email_verified_at=utcnow())
    db.add(user);db.flush()
    pet=Pet(owner_id=user.id,name="Luna",species=species,primary_color="brown",size="medium")
    db.add(pet);db.flush()
    case=LostCase(pet_id=pet.id,lost_at=utcnow()-timedelta(hours=2),latitude=-34.9,longitude=-56.1)
    obs=Observation(species=species,description="",observed_at=utcnow(),latitude=-34.901,longitude=-56.101)
    db.add_all([case,obs]);db.flush()
    photos=[Photo(owner_type=kind,owner_id=owner.id,storage_key=kind+".jpg",mime_type="image/jpeg")
            for kind,owner in [("pet",pet),("lost_case",case),("observation",obs)]]
    db.add_all(photos);db.flush()
    return pet,case,obs,photos


def embedding(db,photo,vector=None,spec=None):
    job=schedule_embedding(db,photo)
    job.status="SUCCEEDED"
    spec=spec or spec_for_photo(db,photo)
    row=Embedding(analysis_job_id=job.id,photo_id=photo.id,input_hash=job.input_hash,
        vector=vector or [1.0]+[0.0]*511,quality={"visual_reliability":1},space_id=spec.space_id,**spec.to_dict())
    db.add(row);db.flush()
    return row


@pytest.mark.parametrize("species,provider",[("dog","pet_reid"),("cat","pet_reid"),("rabbit",None),
    ("bird",None),("other",None),("unknown",None)])
def test_selection_for_every_owner(db_factory,monkeypatch,species,provider):
    monkeypatch.setattr(settings,"pet_reid_enabled",True)
    monkeypatch.setattr(settings,"openclip_enabled",True)
    if provider is None:
        assert select_spec(species) is None
        return
    with db_factory() as db:
        *_,photos=records(db,species)
        assert all(spec_for_photo(db,p).provider==provider for p in photos)


@pytest.mark.parametrize("field,value",[("provider","open_clip"),("model","another-model"),("revision","other"),
    ("dimension",256),("preprocessing_version","new-crop")])
def test_each_space_component_prevents_comparison(field,value):
    spec=pet_reid_spec()
    other=replace(spec,**{field:value})
    assert not compatible(spec,other) and spec.space_id!=other.space_id


def test_cross_space_vectors_never_reach_cosine(db_factory,monkeypatch):
    monkeypatch.setattr(settings,"embeddings_enabled",True)
    with db_factory() as db:
        pet,case,obs,photos=records(db)
        target=embedding(db,photos[0])
        observed=embedding(db,photos[2],spec=openclip_spec())
        monkeypatch.setattr(engine,"cosine",lambda *_: pytest.fail("Incompatible vectors compared"))
        assert engine.visual_evidence(db,[observed],case)==(None,None,0.0)
        # Forging a row space ID is insufficient: its job provenance must also match.
        assert engine.vectors(db,Photo.id==photos[2].id)==[]


def test_all_photo_pairs_use_best_and_second(db_factory,monkeypatch):
    monkeypatch.setattr(settings,"embeddings_enabled",True)
    with db_factory() as db:
        _,case,_,photos=records(db)
        embedding(db,photos[0])
        embedding(db,photos[1],normalize([.8,.6]+[0.0]*510))
        observed=embedding(db,photos[2])
        score,provider,quality=engine.visual_evidence(db,[observed],case)
        assert score==pytest.approx(.94) and provider=="pet_reid" and quality==1


@pytest.mark.parametrize("values,result",[([],None),([.6],.6),([.6,.9],.81),([.1,.9,.6],.81)])
def test_aggregation(values,result):
    value=aggregate_visual_similarity(values)
    assert value is None if result is None else value==pytest.approx(result)


def test_changes_invalidate_and_backfill_is_idempotent(db_factory,monkeypatch):
    monkeypatch.setattr(settings,"embeddings_enabled",True)
    with db_factory() as db:
        pet,_,obs,photos=records(db,"dog")
        old=embedding(db,photos[0]);old_id=old.analysis_job_id
        pet.species="cat";db.flush()
        assert not is_current(db,db.get(AnalysisJob,old_id))
        assert schedule_embedding(db,photos[0]).provider=="pet_reid"
        obs.species="cat";db.commit()
    first=backfill(db_factory,batch_size=1)
    second=backfill(db_factory,batch_size=1)
    assert first["created"]==2 and second["created"]==0
    with db_factory() as db:
        assert db.get(Embedding,old_id) is not None
        assert all(j.priority==10 for j in db.scalars(select(AnalysisJob).where(AnalysisJob.owner_type!="pet")))
    monkeypatch.setattr(settings,"pet_reid_enabled",False)
    assert select_spec("dog")==openclip_spec()
    third=backfill(db_factory)
    assert third["created"]==3  # New species snapshots, without deleting the historical dog vector.


def test_worker_persists_provenance_and_never_repeats_success(db_factory,monkeypatch):
    from app.embeddings import provider
    monkeypatch.setattr(settings,"embeddings_enabled",True)
    with db_factory() as db:
        *_,photos=records(db)
        job=schedule_embedding(db,photos[0]);job_id=job.id;db.commit()
    calls=[]
    def encode(image,species):
        calls.append(species)
        return EmbeddingResult(normalize([1]*512),pet_reid_spec(),{"visual_reliability":.8})
    monkeypatch.setattr(provider,"get_embedding_provider",lambda spec:SimpleNamespace(encode_result=encode))
    monkeypatch.setattr(tasks,"SessionLocal",db_factory)
    monkeypatch.setattr(tasks,"load_analysis_image",lambda *_:(jpeg(),"image/jpeg"))
    assert tasks.process_analysis(str(job_id),0)=="SUCCEEDED"
    assert tasks.process_analysis(str(job_id),0)=="SUCCEEDED"
    with db_factory() as db:
        row=db.get(Embedding,job_id)
        assert row.space_id==pet_reid_spec().space_id and len(row.vector)==512
        assert row.quality["visual_reliability"]==.8
    assert calls==["dog"]


def test_crop_margin_quality_and_detector_failure(monkeypatch):
    cropper=PetCropper()
    monkeypatch.setattr(cropper,"detect",lambda *_:((100,50,300,250),{"detected":True,"detection_confidence":.98}))
    cropped,meta=cropper.prepare(jpeg(),"dog")
    assert meta["crop_used"] and meta["bbox"][0]<100 and meta["bbox"][2]>300
    assert meta["animal_ratio"]==pytest.approx(40000/153600)
    assert 0<meta["visual_reliability"]<1
    def failure(*_): raise ProviderError("DETECTOR_TIMEOUT")
    monkeypatch.setattr(cropper,"detect",failure)
    full,meta=cropper.prepare(jpeg(),"cat")
    assert not meta["crop_used"] and decode_image(full).size==(512,300)
    assert meta["crop_reason"]=="DETECTOR_TIMEOUT"
    with pytest.raises(ProviderError,match="INVALID_IMAGE"):
        cropper.prepare(b"bad", "dog")
    assert image_quality(Image.new("RGB",(2,2)))["visual_reliability"]==.1


def test_ollama_cache_keepalive_limits_and_timeouts(monkeypatch):
    features=evidence().model_dump(mode="json")
    raw={name:value["value"] for name,value in features.items()}
    raw["confidence"]={name:value["confidence"] for name,value in features.items()}
    request=httpx.Request("POST","http://ollama:11434/api/chat")
    metadata=httpx.Response(200,json={"capabilities":["vision","completion"]},request=request)
    result=httpx.Response(200,json={"done":True,"message":{"content":json.dumps(raw)}},request=request)
    post=AsyncMock(side_effect=[metadata,result,result])
    monkeypatch.setattr(httpx.AsyncClient,"post",post)
    asyncio.run(OllamaProvider("gemma3:4b").extract_observation("dog"))
    asyncio.run(OllamaProvider("gemma3:4b").analyze_image(jpeg(),"image/jpeg"))
    assert sum(call.args[0].endswith("/api/show") for call in post.call_args_list)==1
    body=post.call_args.kwargs["json"]
    assert body["keep_alive"]==settings.ollama_keep_alive
    assert body["options"]["num_ctx"]==settings.ollama_num_ctx
    assert body["options"]["num_predict"]==settings.ollama_num_predict


def test_bounded_wait_and_priority():
    job=SimpleNamespace(source_type="image",status="PENDING",attempts=0,created_at=utcnow()-timedelta(minutes=2))
    assert not engine.should_wait(job)
    job.attempts=1;job.created_at=utcnow()
    assert not engine.should_wait(job)
    assert queue_name("embedding",100).endswith("visual-urgent")
    assert queue_name("image",10).endswith("semantic-backfill")
    assert queue_name("text",50).endswith("semantic-normal")


def test_quality_geography_and_coverage_gate_alerts():
    good=combine(1,.99,0,15000,0,provider="pet_reid",quality=1)
    bad=combine(1,.99,0,15000,0,provider="pet_reid",quality=.1)
    assert good[0]>bad[0]
    assert not notification_evidence(1,.15,1,1)
    assert not notification_evidence(1,1,1,.1)
    assert not notification_evidence(1,1,.1,1)
    assert combine(1,.7,0,15000,0,provider="pet_reid")[1]!=combine(1,.7,0,15000,0,provider="open_clip")[1]


def test_linked_visual_identity_requires_independent_traits(db_factory,monkeypatch):
    monkeypatch.setattr(settings,"embeddings_enabled",True)
    monkeypatch.setattr(settings,"ai_enabled",True)
    with db_factory() as db:
        _,case,obs,photos=records(db)
        obs.linked_case_id=case.id
        embedding(db,photos[0]);embedding(db,photos[2])
        assert linked.evaluate_sighting(db,obs.id)=="UNVERIFIED"
        job=schedule_photo(db,photos[2]);job.status="SUCCEEDED"
        db.add(FeatureSet(analysis_job_id=job.id,features={name:{"value":value,"confidence":.95,"source":"image"}
            for name,value in {"species":"dog","primary_color":"brown","size":"medium"}.items()}));db.flush()
        assert linked.evaluate_sighting(db,obs.id)=="POSSIBLE_MATCH"


@pytest.mark.parametrize("source,code,retryable",[("embedding","EMBEDDING_MODEL_NOT_INSTALLED",False),("image","PROVIDER_UNAVAILABLE",True)])
def test_provider_failure_keeps_report_and_partial_matching(db_factory,monkeypatch,source,code,retryable):
    from app.models import Notification
    from app.embeddings import provider
    monkeypatch.setattr(settings,"embeddings_enabled",True)
    monkeypatch.setattr(settings,"ai_enabled",True)
    with db_factory() as db:
        _,case,obs,photos=records(db)
        obs.linked_case_id=case.id
        job=schedule_embedding(db,photos[2]) if source=="embedding" else schedule_photo(db,photos[2])
        job_id,obs_id,case_id=job.id,obs.id,case.id
        db.commit()
    def unavailable(*_):raise ProviderError(code,retryable=retryable)
    monkeypatch.setattr(tasks,"SessionLocal",db_factory)
    monkeypatch.setattr(tasks,"load_analysis_image",lambda *_:(jpeg(),"image/jpeg"))
    monkeypatch.setattr(provider,"get_embedding_provider",unavailable)
    monkeypatch.setattr(tasks,"get_provider",unavailable)
    assert tasks.process_analysis(str(job_id),0)==("PENDING" if retryable else "FAILED")
    with db_factory() as db:
        assert db.get(LostCase,case_id).status=="ACTIVE"
        # Do not let other first-attempt jobs mask the partial-evidence fallback.
        for job in db.scalars(select(AnalysisJob)):
            job.created_at=utcnow()-timedelta(minutes=10)
        db.flush()
        assert linked.evaluate_sighting(db,obs_id)=="UNVERIFIED"
        notices=list(db.scalars(select(Notification)))
        assert notices and all(item.kind=="REPORTED_SIGHTING" for item in notices)
        assert db.get(AnalysisJob,job_id).error_code==code


def test_checkpoint_checksum_failure_is_atomic(tmp_path,monkeypatch):
    from app.embeddings import setup
    from io import BytesIO
    monkeypatch.setattr(setup,"model_path",lambda _:tmp_path/"model.onnx")
    monkeypatch.setattr(setup,"verify_artifact",lambda _:False)
    monkeypatch.setattr(setup.urllib.request,"urlopen",lambda *a,**kw:BytesIO(b"corrupt"))
    with pytest.raises(ValueError,match="checksum or size"):
        setup.install("pet_reid")
    assert not list(tmp_path.iterdir())


def test_current_semantic_backfill_is_deduplicated_and_low_priority(db_factory,monkeypatch):
    from app.analysis.backfill import backfill as semantic_backfill
    monkeypatch.setattr(settings,"ai_enabled",True)
    with db_factory() as db:
        _,case,obs,_=records(db)
        case.description="Perro con pecho blanco."
        obs.description="Tiene collar rojo."
        db.commit()
    assert semantic_backfill(db_factory)["created"]==5
    assert semantic_backfill(db_factory)["created"]==0
    with db_factory() as db:
        assert all(job.priority==10 for job in db.scalars(select(AnalysisJob)))
