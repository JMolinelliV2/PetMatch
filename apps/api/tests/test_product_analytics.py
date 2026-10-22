from datetime import timedelta
from uuid import UUID,uuid4
import json
import pytest
from sqlalchemy import func,select
from app.analysis.service import utcnow
from app.core.config import settings
from app.models import (AdminAccess,AnalyticsSession,AnalyticsTracking,AnalyticsVisitor,LostCase,Match,MatchExposure,
    MatchFeedbackEvent,Observation,Pet,Photo,ProductDaily,ProductEvent,ProductMilestone,RecoveryOutcome,User,UserActivity)
from app.product_analytics import cleanup,digest,photo_milestones,record,ZONE
from app.routers.admin_analytics import distribution
from app.matching.tracking import record_recommendation
from app.matching.visibility import presentation
from app.models import AnalysisJob


def browser(client,name="page_view",page="HOME",headers=None,**kwargs):
    return client.post("/api/v1/analytics/events",headers={"Origin":settings.web_origin,**(headers or {})},
        json={"name":name,"page":page,"event_id":str(uuid4()),**kwargs})


def publication(client,headers):
    pet=client.post("/api/v1/pets",headers=headers,json={"name":"Luna","species":"dog"})
    assert pet.status_code==201,pet.text
    case=client.post("/api/v1/lost-cases",headers=headers,json={"pet_id":pet.json()["id"],"lost_at":utcnow().isoformat(),
        "analytics_geo":{"country":"UY","department":"Montevideo","locality":"Montevideo"}})
    assert case.status_code==201,case.text
    return pet.json(),case.json()


def matching_fixture(client,headers,db_factory):
    pet,case=publication(client,headers)
    with db_factory() as db:
        observation=Observation(species="dog",description="Test sighting",observed_at=utcnow(),linked_case_id=UUID(case["id"]))
        db.add(observation);db.flush()
        match=Match(lost_case_id=UUID(case["id"]),observation_id=observation.id,feature_score=.9,visual_score=.8,visual_similarity=.82,
            geo_score=.9,temporal_score=.9,final_score=.87,evidence_coverage=.8,distance_meters=100,explanation=[])
        record_recommendation(match,"GENERAL",visual_provider="pet_reid")
        db.add(match);db.commit();identity=str(match.id)
    return pet,case,identity


def promote(client,headers,db_factory):
    user=client.get("/api/v1/auth/me",headers=headers).json()
    with db_factory() as db:
        account=db.get(User,UUID(user["id"]));account.role="ADMIN"
        db.add(AdminAccess(id=1,owner=account));db.commit()
    return user


def test_first_party_identity_session_and_page_idempotence(client,db_factory,monkeypatch):
    event_id=str(uuid4())
    first=browser(client,event_id=event_id)
    assert first.status_code==204,first.text
    assert "HttpOnly" in first.headers["set-cookie"] and "SameSite=lax" in first.headers["set-cookie"]
    raw=client.cookies.get("mm_visitor")
    assert len(raw)==43
    assert browser(client,event_id=event_id).status_code==204
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.name=="page_view"))==1
        visitor=db.scalar(select(AnalyticsVisitor));assert visitor.id==digest("visitor:"+raw) and visitor.id!=raw
        visit=db.scalar(select(AnalyticsSession));assert not visit.returning
        now=utcnow();visit.last_seen_at=now-timedelta(minutes=31);db.commit()
    assert browser(client).status_code==204
    assert client.cookies.get("mm_visitor")==raw
    with db_factory() as db:
        sessions=list(db.scalars(select(AnalyticsSession).order_by(AnalyticsSession.started_at)))
        assert len(sessions)==2 and sessions[-1].returning
        assert db.scalar(select(func.count()).select_from(ProductDaily).where(ProductDaily.name=="page_view"))==2


@pytest.mark.parametrize("agent",["Googlebot","crawler","HeadlessChrome","Prometheus","mascomatch-smoke"])
def test_obvious_bots_are_not_product_visits(client,db_factory,agent):
    assert browser(client,headers={"User-Agent":agent}).status_code==204
    with db_factory() as db:assert db.scalar(select(func.count()).select_from(ProductEvent))==0


def test_api_and_health_calls_are_not_views(client,db_factory):
    client.get("/health");client.get("/api/v1/public/lost-animals")
    with db_factory() as db:assert db.scalar(select(func.count()).select_from(ProductEvent))==0


@pytest.mark.parametrize("extra",[{"name":"account_created"},{"page":"https://site.test/?token=secret"},
    {"email":"private@example.test"},{"properties":{"latitude":-34.1234}}, {"user_id":str(uuid4())}])
def test_browser_cannot_forge_authoritative_events_or_pii(client,extra):
    assert browser(client,**extra).status_code==422


def test_cross_origin_and_oversized_event_are_rejected(client):
    assert browser(client,headers={"Origin":"https://other.example"}).status_code==403
    assert client.post("/api/v1/analytics/events",content="x"*5000).status_code==413


def test_cookie_is_secure_in_production(client,monkeypatch):
    monkeypatch.setattr(settings,"app_env","production")
    result=browser(client)
    assert result.status_code==204 and "; Secure" in result.headers["set-cookie"]


def test_login_keeps_browser_identity_and_only_links_future_facts(client,auth_headers,db_factory):
    browser(client)
    raw=client.cookies.get("mm_visitor")
    browser(client,headers=auth_headers)
    assert client.cookies.get("mm_visitor")==raw
    with db_factory() as db:
        rows=list(db.scalars(select(ProductEvent).where(ProductEvent.name=="page_view").order_by(ProductEvent.created_at)))
        assert rows[0].user_id is None and rows[1].user_id is not None
        assert rows[0].visitor_id==rows[1].visitor_id


def test_server_milestones_distinguish_users_from_pets_and_are_durable(client,auth_headers,db_factory):
    pet,_=publication(client,auth_headers)
    client.post("/api/v1/pets",headers=auth_headers,json={"name":"Otra","species":"cat"})
    with db_factory() as db:
        user=db.scalar(select(User));animal=db.get(Pet,UUID(pet["id"]))
        for i in range(5):
            photo=Photo(owner_type="pet",owner_id=animal.id,storage_key=f"real-upload-{i}.jpg",mime_type="image/jpeg")
            db.add(photo);db.flush();photo_milestones(db,photo,user);db.commit()
        photo_milestones(db,photo,user);db.commit()
        for name in ("first_photo_uploaded","three_photos_uploaded","five_photos_uploaded"):
            assert db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.name==name))==1
        assert db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.name=="pet_created"))==2
        assert db.scalar(select(func.count(func.distinct(ProductEvent.user_id))).where(ProductEvent.name=="pet_created"))==1
        db.query(ProductEvent).delete();db.commit()
        photo_milestones(db,photo,user);db.commit()
        assert not db.scalar(select(ProductEvent).where(ProductEvent.name=="five_photos_uploaded"))


def test_analytics_failure_does_not_break_successful_product_write(client,auth_headers,monkeypatch):
    def unavailable(*args,**kwargs):raise RuntimeError("Unavailable")
    monkeypatch.setattr("app.product_analytics.event",unavailable)
    result=client.post("/api/v1/pets",headers=auth_headers,json={"name":"Valid","species":"dog"})
    assert result.status_code==201


def test_getting_matches_does_not_count_a_view_and_signed_rank_is_used(client,auth_headers,db_factory):
    _,case,identity=matching_fixture(client,auth_headers,db_factory)
    response=client.get(f"/api/v1/matches/lost-cases/{case['id']}",headers=auth_headers)
    token=response.json()["items"][0]["match"]["presentation"]
    with db_factory() as db:assert db.get(Match,UUID(identity)).first_viewed_at is None
    assert browser(client,"match_shown","MATCHES",headers=auth_headers,presentation=token).status_code==204
    with db_factory() as db:
        match=db.get(Match,UUID(identity));assert match.first_shown_at and match.first_viewed_at is None
    for _ in range(2):assert browser(client,"match_viewed","MATCHES",headers=auth_headers,presentation=token).status_code==204
    with db_factory() as db:
        match=db.get(Match,UUID(identity));assert match.first_viewed_rank==match.best_viewed_rank==1
        assert db.scalar(select(func.count()).select_from(MatchExposure))==1
        assert db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.name=="match_viewed"))==1
    assert browser(client,"match_viewed","MATCHES",headers=auth_headers,presentation=token+"f").status_code==422
    assert browser(client,"match_viewed","MATCHES",presentation=token).status_code==401


@pytest.mark.parametrize("path",["case","dashboard","feedback"])
def test_all_recovery_paths_share_attribution_and_retries_are_idempotent(client,auth_headers,db_factory,path):
    _,case,identity=matching_fixture(client,auth_headers,db_factory)
    payload={"status":"FOUND","recovery_reason":"MASCOMATCH_MATCH","recovery_match_id":identity}
    if path=="case":url=f"/api/v1/lost-cases/{case['id']}";body=payload
    elif path=="dashboard":url=f"/api/v1/me/cases/{case['id']}";body={"pet":{},"case":payload}
    else:url=f"/api/v1/matches/{identity}/feedback";body={"status":"RESOLVED","recovered":True,"recovery_reason":"MASCOMATCH_MATCH"}
    for _ in range(2):
        response=client.patch(url,headers=auth_headers,json=body)
        assert response.status_code==200,response.text
    with db_factory() as db:
        recovery=db.get(RecoveryOutcome,UUID(case["id"]))
        assert recovery and recovery.reason=="MASCOMATCH_MATCH" and recovery.match_id==UUID(identity)
        assert db.scalar(select(func.count()).select_from(RecoveryOutcome))==1
        assert db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.name=="recovery"))==1
        if path=="feedback":assert db.scalar(select(func.count()).select_from(MatchFeedbackEvent))==1
        assert db.get(LostCase,UUID(case["id"])).status=="FOUND"


def test_recovery_does_not_invent_legacy_attribution_or_accept_other_case_match(client,auth_headers,db_factory):
    _,_,identity=matching_fixture(client,auth_headers,db_factory)
    _,case=publication(client,auth_headers)
    result=client.patch(f"/api/v1/lost-cases/{case['id']}",headers=auth_headers,json={"status":"FOUND","recovery_reason":"MASCOMATCH_MATCH","recovery_match_id":identity})
    assert result.status_code==422
    with db_factory() as db:
        db.get(LostCase,UUID(case["id"])).status="FOUND";db.commit()
    assert client.patch(f"/api/v1/lost-cases/{case['id']}",headers=auth_headers,json={"status":"FOUND"}).status_code==200
    with db_factory() as db:assert db.get(RecoveryOutcome,UUID(case["id"])) is None


@pytest.mark.parametrize("section",["growth","usage","matching","impact","inventory"])
def test_admin_sections_keep_access_control_and_empty_data_honest(client,auth_headers,db_factory,section):
    assert client.get(f"/api/v1/admin/analytics/{section}").status_code==401
    assert client.get(f"/api/v1/admin/analytics/{section}",headers=auth_headers).status_code==403
    promote(client,auth_headers,db_factory)
    response=client.get(f"/api/v1/admin/analytics/{section}?days=0",headers=auth_headers)
    assert response.status_code==200,response.text
    assert response.json()["analytics_started_at"]
    assert response.json()["metrics"]


def test_admin_matching_counts_versions_outcomes_topk_and_preserves_first_recommendation(client,auth_headers,db_factory):
    _,case,identity=matching_fixture(client,auth_headers,db_factory)
    token=client.get(f"/api/v1/matches/lost-cases/{case['id']}",headers=auth_headers).json()["items"][0]["match"]["presentation"]
    browser(client,"match_viewed","MATCHES",headers=auth_headers,presentation=token)
    client.patch(f"/api/v1/matches/{identity}/feedback",headers=auth_headers,json={"status":"RESOLVED"})
    promote(client,auth_headers,db_factory)
    with db_factory() as db:
        match=db.get(Match,UUID(identity));original=match.recommended_at;snapshot=match.recommendation_snapshot.copy()
        match.final_score=.6;record_recommendation(match,"LINKED",visual_provider="open_clip");db.commit()
        assert match.recommended_at==original and match.recommendation_snapshot==snapshot
    response=client.get("/api/v1/admin/analytics/matching?days=0&provider=pet_reid",headers=auth_headers)
    assert response.status_code==200,response.text
    data=response.json();assert data["topk"]["1"]["count"]==1 and data["topk"]["1"]["percent"]==100
    assert data["versions"][0]["provider"]=="pet_reid"
    assert data["utility"]["with_recommendation"]==1
    other=client.get("/api/v1/admin/analytics/matching?days=0&provider=open_clip",headers=auth_headers).json()
    assert not other["versions"]


def test_retention_keeps_daily_counts_and_operational_truth(client,auth_headers,db_factory,monkeypatch):
    publication(client,auth_headers)
    browser(client)
    with db_factory() as db:
        daily=db.scalar(select(func.sum(ProductDaily.count)));row=db.scalar(select(ProductEvent).where(ProductEvent.name=="page_view"));row.created_at=utcnow()-timedelta(days=91);db.commit()
    cleanup(db_factory);cleanup(db_factory)
    with db_factory() as db:
        assert db.scalar(select(func.sum(ProductDaily.count)))==daily
        assert not db.scalar(select(ProductEvent).where(ProductEvent.name=="page_view"))
        assert db.scalar(select(func.count()).select_from(LostCase))==1


def test_metrics_by_hour_grouping_geography_and_activity_windows(client,auth_headers,db_factory):
    _,case=publication(client,auth_headers)
    browser(client,page="LOST_CASE",entity_id=case["id"])
    user=promote(client,auth_headers,db_factory)
    now=utcnow()
    with db_factory() as db:
        db.add(UserActivity(user_id=UUID(user["id"]),occurred_at=now));db.commit()
    for group in ("day","week","month"):
        response=client.get(f"/api/v1/admin/analytics/inventory?group={group}",headers=auth_headers)
        assert response.status_code==200,response.text
        assert any(row["country"]=="UY" and row["department"]=="Montevideo" for row in response.json()["geography"])
    usage=client.get("/api/v1/admin/analytics/usage",headers=auth_headers).json()
    assert all(next(m["value"] for m in usage["metrics"] if m["label"]==name)==1 for name in ("DAU","WAU","MAU"))
    excluded=client.get("/api/v1/admin/analytics/growth",params={"from_at":(now+timedelta(hours=1)).isoformat(),"to_at":(now+timedelta(hours=2)).isoformat()},headers=auth_headers).json()
    assert next(m["value"] for m in excluded["metrics"] if m["label"]=="Vistas de página")==0


def test_distribution_hides_p95_for_small_samples():
    assert distribution([1,2,3])["p95_seconds"] is None
    assert distribution(range(20))["p95_seconds"]==18


@pytest.mark.parametrize("reason",["MASCOMATCH_MATCH","MASCOMATCH_SIGHTING","SOCIAL_MEDIA","WHATSAPP","VET_OR_SHELTER",
                                    "STREET_OR_POSTERS","RETURNED_ALONE","OTHER","PREFER_NOT_TO_SAY"])
def test_every_recovery_reason_is_valid_and_sighting_context_is_retained(client,auth_headers,db_factory,reason):
    _,case,identity=matching_fixture(client,auth_headers,db_factory)
    response=client.patch(f"/api/v1/matches/{identity}/feedback",headers=auth_headers,json={"status":"RESOLVED","recovered":True,"recovery_reason":reason})
    assert response.status_code==200,response.text
    with db_factory() as db:
        outcome=db.get(RecoveryOutcome,UUID(case["id"]))
        assert outcome.reason==reason
        assert bool(outcome.match_id)==(reason=="MASCOMATCH_MATCH")
        assert bool(outcome.observation_id)==(reason in {"MASCOMATCH_MATCH","MASCOMATCH_SIGHTING"})


def test_identity_does_not_depend_on_ip_or_user_agent(client,db_factory):
    browser(client,headers={"User-Agent":"Browser A","X-Forwarded-For":"192.0.2.1"})
    cookie=client.cookies.get("mm_visitor")
    browser(client,headers={"User-Agent":"Browser B","X-Forwarded-For":"198.51.100.1"})
    assert client.cookies.get("mm_visitor")==cookie
    client.cookies.clear()
    browser(client,headers={"User-Agent":"Browser A","X-Forwarded-For":"192.0.2.1"})
    assert client.cookies.get("mm_visitor")!=cookie
    with db_factory() as db:assert db.scalar(select(func.count()).select_from(AnalyticsVisitor))==2


@pytest.mark.parametrize("headers",[{"Purpose":"prefetch"},{"Next-Router-Prefetch":"1"},{"Sec-Purpose":"prefetch"},{"X-MascoMatch-Synthetic":"1"}])
def test_prefetch_and_explicit_internal_checks_do_not_create_visits(client,db_factory,headers):
    assert browser(client,headers=headers).status_code==204
    with db_factory() as db:assert not db.scalar(select(ProductEvent))


def test_rank_changes_new_matches_and_new_sessions_have_defined_deduplication(client,auth_headers,db_factory):
    _,case,identity=matching_fixture(client,auth_headers,db_factory)
    with db_factory() as db:
        match=db.get(Match,UUID(identity));user=db.get(User,match.lost_case.pet.owner_id) if hasattr(match,"lost_case") else db.scalar(select(User))
        shown=presentation(match,user,6);viewed=presentation(match,user,3);best=presentation(match,user,1)
    browser(client,"match_shown","MATCHES",headers=auth_headers,presentation=shown)
    browser(client,"match_viewed","MATCHES",headers=auth_headers,presentation=viewed)
    browser(client,"match_viewed","MATCHES",headers=auth_headers,presentation=best)
    with db_factory() as db:
        match=db.get(Match,UUID(identity));assert match.first_viewed_rank==3 and match.best_viewed_rank==1
        session=db.scalar(select(AnalyticsSession));session.last_seen_at=utcnow()-timedelta(minutes=31);db.commit()
    browser(client,"match_viewed","MATCHES",headers=auth_headers,presentation=best)
    _,other,second=matching_fixture(client,auth_headers,db_factory)
    token=client.get(f"/api/v1/matches/lost-cases/{other['id']}",headers=auth_headers).json()["items"][0]["match"]["presentation"]
    browser(client,"match_viewed","MATCHES",headers=auth_headers,presentation=token)
    with db_factory() as db:
        assert db.scalar(select(func.count()).select_from(ProductEvent).where(ProductEvent.name=="match_viewed"))==3
        assert db.get(Match,UUID(identity)).first_viewed_rank==3


def test_feedback_changes_preserve_history_and_one_statistical_recommendation(client,auth_headers,db_factory):
    _,_,identity=matching_fixture(client,auth_headers,db_factory)
    for status in ("CONFIRMED_RELEVANT","FALSE_MATCH","RESOLVED","RESOLVED"):
        assert client.patch(f"/api/v1/matches/{identity}/feedback",headers=auth_headers,json={"status":status}).status_code==200
    promote(client,auth_headers,db_factory)
    data=client.get("/api/v1/admin/analytics/matching?days=0",headers=auth_headers).json()
    metrics={m["label"]:m["value"] for m in data["metrics"]}
    assert metrics["Recomendaciones"]==metrics["Confirmadas"]==metrics["Revisadas"]==1
    assert metrics["Tasa de confirmación entre decididas"]==100
    with db_factory() as db:
        events=list(db.scalars(select(MatchFeedbackEvent)))
        assert len(events)==3 and all(e.context_snapshot["recommendation"]["visual_provider"]=="pet_reid" for e in events)
    other=client.post("/api/v1/auth/register",json={"email":"other-reader@example.test","password":"test-only-passphrase","name":"Other"}).json()
    headers={"Authorization":"Bearer "+other["access_token"]}
    assert client.patch(f"/api/v1/matches/{identity}/feedback",headers=headers,json={"status":"FALSE_MATCH"}).status_code==404


def test_failed_secondary_rollup_preserves_facts_and_is_retried_once(client,auth_headers,db_factory,monkeypatch):
    import app.product_analytics as analytics
    original=analytics.insert
    def unavailable_daily(db,model,*args,**kwargs):
        if model is ProductDaily:raise RuntimeError("Secondary aggregate unavailable")
        return original(db,model,*args,**kwargs)
    monkeypatch.setattr(analytics,"insert",unavailable_daily)
    result=client.post("/api/v1/pets",headers=auth_headers,json={"name":"Photo-free","species":"cat"})
    assert result.status_code==201
    with db_factory() as db:
        event=db.scalar(select(ProductEvent).where(ProductEvent.name=="pet_created"))
        assert event and not event.aggregated
    monkeypatch.setattr(analytics,"insert",original)
    cleanup(db_factory);cleanup(db_factory)
    with db_factory() as db:
        assert db.scalar(select(func.sum(ProductDaily.count)).where(ProductDaily.name=="pet_created"))==1
        assert db.scalar(select(ProductEvent).where(ProductEvent.name=="pet_created")).aggregated


def test_csv_is_private_aggregated_and_formula_safe(client,auth_headers,db_factory):
    from app.routers.admin_analytics import csv_cell
    assert csv_cell("=1+1")=="'=1+1"
    assert csv_cell("-formula").startswith("'")
    assert client.get("/api/v1/admin/analytics/growth?export_csv=true",headers=auth_headers).status_code==403
    promote(client,auth_headers,db_factory)
    response=client.get("/api/v1/admin/analytics/growth?export_csv=true",headers=auth_headers)
    assert response.status_code==200 and "text/csv" in response.headers["content-type"]
    assert "owner@example.com" not in response.text and "password" not in response.text


def test_job_filters_use_actual_revision_and_measurements_without_models(client,auth_headers,db_factory):
    promote(client,auth_headers,db_factory)
    now=utcnow()
    with db_factory() as db:
        for index,(provider,model,source,revision) in enumerate((("ollama","gemma3:4b","text","g1"),("pet_reid","pet-model","embedding","p1"))):
            db.add(AnalysisJob(deduplication_key=str(index),owner_type="pet",owner_id=uuid4(),source_type=source,provider=provider,model=model,
                prompt_version="prompt-v1",input_hash="input",input_snapshot={"spec":{"revision":revision}} if source=="embedding" else {},
                status="SUCCEEDED",attempts=1,created_at=now-timedelta(hours=3),started_at=now-timedelta(hours=2),finished_at=now-timedelta(hours=1),
                metrics={"model_revision":revision,"cold_start":1,"model_load_ms":1000,"cpu_ms":2000,"total_ms":3000}))
        db.commit()
    result=client.get("/api/v1/admin/analytics/matching?job_provider=ollama&job_source=text&job_revision=g1",headers=auth_headers)
    assert result.status_code==200,result.text
    data=result.json()["operations"]
    assert data["total"]==1 and data["segments"][0]["revision"]=="g1"
    assert data["timings"]["model_load_ms"]["p50_seconds"]==1
    assert data["cold_start_rate"]==100 and data["throughput_completed"]==1


def test_resource_readings_are_bounded_and_do_not_require_privileged_mounts(tmp_path):
    from app.ops.resources import container_resources
    (tmp_path/"memory.current").write_text("1024");(tmp_path/"memory.max").write_text("2048")
    (tmp_path/"cpu.stat").write_text("usage_usec 2000000\nuser_usec 1000000\n")
    (tmp_path/"cpu.max").write_text("200000 100000")
    result=container_resources(tmp_path)
    assert result=={"memory_bytes":1024,"memory_limit_bytes":2048,"cpu_seconds_total":2,"cpu_limit_cores":2}
    (tmp_path/"memory.max").write_text("max")
    assert "memory_limit_bytes" not in container_resources(tmp_path)


def test_existing_photos_do_not_backdate_milestones(client,auth_headers,db_factory):
    pet,_=publication(client,auth_headers)
    with db_factory() as db:
        for index in range(2):db.add(Photo(owner_type="pet",owner_id=UUID(pet["id"]),storage_key=f"legacy-{index}",mime_type="image/jpeg"))
        db.commit()
        photo=Photo(owner_type="pet",owner_id=UUID(pet["id"]),storage_key="new-third",mime_type="image/jpeg")
        db.add(photo);db.flush();photo_milestones(db,photo,db.scalar(select(User)));db.commit()
        assert db.scalar(select(ProductEvent).where(ProductEvent.name=="three_photos_uploaded"))
        assert not db.scalar(select(ProductEvent).where(ProductEvent.name=="first_photo_uploaded"))


def test_unavailable_public_notice_is_not_counted_as_lost_case_inventory(client,auth_headers,db_factory):
    _,case=publication(client,auth_headers)
    client.patch(f"/api/v1/lost-cases/{case['id']}",headers=auth_headers,json={"status":"FOUND"})
    assert browser(client,page="LOST_CASE",entity_id=case["id"]).status_code==404


def test_dashboard_cache_is_bounded_filtered_expiring_and_best_effort(monkeypatch):
    import app.routers.admin_analytics as analytics
    store={};writes=[]
    class FakeRedis:
        @classmethod
        def from_url(cls,*args,**kwargs):
            assert kwargs["socket_timeout"]<=.25 and kwargs["socket_connect_timeout"]<=.25
            return cls()
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def get(self,key):return store.get(key)
        def set(self,key,value,ex):
            writes.append((key,len(value.encode()),ex));store[key]=value
    monkeypatch.setattr(analytics,"Redis",FakeRedis)
    monkeypatch.setattr(settings,"app_env","production")
    for section in ("growth","usage","matching","impact","inventory"):
        for fingerprint in ("filter-a","filter-b"):
            analytics.cached_dashboard(section,fingerprint,{"generated_at":utcnow(),"metrics":[]})
        assert analytics.cached_dashboard(section,"filter-a") is None
        assert analytics.cached_dashboard(section,"filter-b")["metrics"]==[]
    assert len(store)==5 and all(size<=524288 and ttl==60 for _,size,ttl in writes)
    analytics.cached_dashboard("growth","large",{"value":"x"*524288})
    assert analytics.cached_dashboard("growth","large") is None and len(store)==5
    def unavailable(*args,**kwargs):raise RuntimeError("Cache unavailable")
    monkeypatch.setattr(FakeRedis,"from_url",unavailable)
    assert analytics.cached_dashboard("growth","filter-b") is None
    assert analytics.cached_dashboard("growth","filter-b",{}) is None
    monkeypatch.setattr(settings,"app_env","development")
    assert analytics.cached_dashboard("growth","filter-b") is None


def test_cached_admin_analytics_still_requires_admin_and_respects_filters(client,auth_headers,db_factory,monkeypatch):
    import app.routers.admin_analytics as analytics
    calls=[]
    cached={"metrics":[{"label":"Vistas de página","value":12}],"series":[],"generated_at":utcnow().isoformat()}
    def cache(section,fingerprint,data=None):
        calls.append((section,fingerprint));return cached
    monkeypatch.setattr(analytics,"cached_dashboard",cache)
    assert client.get("/api/v1/admin/analytics/growth",headers=auth_headers).status_code==403
    assert not calls
    promote(client,auth_headers,db_factory)
    for query in ("days=7","days=30","days=30&country=UY","days=30&provider=pet_reid"):
        result=client.get("/api/v1/admin/analytics/growth?"+query,headers=auth_headers)
        assert result.status_code==200 and result.json()["metrics"][0]["value"]==12
        assert result.headers["cache-control"]=="no-store"
    assert len({fingerprint for _,fingerprint in calls})==4
    result=client.get("/api/v1/admin/analytics/growth?days=7&export_csv=true",headers=auth_headers)
    assert result.status_code==200 and "text/csv" in result.headers["content-type"]
    assert "Vistas de página,12" in result.text and calls[0]==calls[-1]
