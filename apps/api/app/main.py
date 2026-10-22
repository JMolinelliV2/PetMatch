import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.background import BackgroundTasks
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.rate_limit import RateLimitMiddleware
from app.core.observability import ObservabilityMiddleware
from app.routers import analysis, auth, contact, dashboard, linked_sightings, lost_cases, map, matches, moderation, notifications, observations, operations, pets, photos, public_lost_dogs, public_observations, reviews, upload_admission
from app.routers import admin_matching, admin_operations
from app.routers import analytics, admin_analytics


@asynccontextmanager
async def lifespan(application: FastAPI):
    from app.matching.linked import reconciliation_loop
    from app.notifications.email import delivery_loop
    from app.matching.engine import general_matching_loop
    from app.account_mail import delivery_loop as account_delivery_loop
    from app.photo_reminders import delivery_loop as photo_reminder_loop
    from app.account_management import cleanup_loop
    from app.contact_mail import delivery_loop as contact_delivery_loop
    tasks = [asyncio.create_task(reconciliation_loop()), asyncio.create_task(delivery_loop()), asyncio.create_task(general_matching_loop()),asyncio.create_task(account_delivery_loop()), asyncio.create_task(photo_reminder_loop())]
    tasks.append(asyncio.create_task(cleanup_loop()))
    tasks.append(asyncio.create_task(contact_delivery_loop()))
    from app.operational_tracking import cleanup_loop as tracking_cleanup_loop
    tasks.append(asyncio.create_task(tracking_cleanup_loop()))
    from app.product_analytics import cleanup_loop as analytics_cleanup_loop
    tasks.append(asyncio.create_task(analytics_cleanup_loop()))
    if settings.ai_enabled or settings.embeddings_enabled:
        from app.analysis.queue import dispatch_loop
        tasks.append(asyncio.create_task(dispatch_loop()))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

app = FastAPI(
    title="MascoMatch API",
    description="Mascotas, reportes y extracción de características de textos y fotos.",
    version="0.2.0",
    lifespan=lifespan,
    openapi_url=None if settings.app_env == "production" else "/api/v1/openapi.json",
    docs_url=None if settings.app_env == "production" else "/api/v1/docs",
    redoc_url=None,
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=[value.strip() for value in settings.allowed_hosts.split(",") if value.strip()])
app.add_middleware(ObservabilityMiddleware)


@app.middleware("http")
async def analytics_body_limit(request,call_next):
    if request.url.path.rstrip("/")=="/api/v1/analytics/events":
        body=bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body)>4096:return JSONResponse({"detail":"Evento demasiado grande."},status_code=413)
        request._body=bytes(body)
    return await call_next(request)


@app.middleware("http")
async def activity_tracking(request, call_next):
    response = await call_next(request)
    identity = getattr(request.state, "activity_user_id", None)
    from app.db.session import get_db
    if identity and response.status_code < 400 and settings.app_env != "test" and get_db not in app.dependency_overrides:
        from app.operational_tracking import record_activity
        tasks = BackgroundTasks()
        if response.background is not None:
            tasks.add_task(response.background)
        tasks.add_task(record_activity, identity)
        response.background = tasks
    return response

app.include_router(auth.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(admin_analytics.router, prefix="/api/v1")
app.include_router(pets.router, prefix="/api/v1")
app.include_router(lost_cases.router, prefix="/api/v1")
app.include_router(observations.router, prefix="/api/v1")
app.include_router(photos.router, prefix="/api/v1")
app.include_router(analysis.router, prefix="/api/v1")
app.include_router(public_lost_dogs.router, prefix="/api/v1")
app.include_router(public_lost_dogs.legacy_router, prefix="/api/v1")
app.include_router(public_observations.router, prefix="/api/v1")
app.include_router(linked_sightings.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(matches.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(map.router, prefix="/api/v1")
app.include_router(moderation.router, prefix="/api/v1")
app.include_router(admin_matching.router, prefix="/api/v1")
app.include_router(admin_operations.router, prefix="/api/v1")
app.include_router(reviews.router, prefix="/api/v1")
app.include_router(contact.router, prefix="/api/v1")
app.include_router(operations.router)
app.include_router(upload_admission.router)


@app.get("/health", tags=["health"])
def health():
    return {"status": "ok"}

