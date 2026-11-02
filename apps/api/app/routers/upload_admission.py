"""Bound memory used by concurrent web uploads before reading their bodies."""
from ipaddress import ip_address, ip_network
import time
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from redis import Redis
from redis.exceptions import RedisError
from app.core.config import settings
from app.core.rate_limit import RATE_SCRIPT, private_key, client_address
from app.dependencies import optional_user

router = APIRouter(prefix="/internal/uploads", include_in_schema=False)
SLOTS = "mascomatch:uploads:leases"
SLOT_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
if redis.call('ZCARD', KEYS[1]) >= tonumber(ARGV[3]) then return 0 end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[4])
redis.call('EXPIRE', KEYS[1], 150)
return 1
"""


def internal_caller(request: Request):
    if settings.app_env != "production":
        return
    try:
        peer = ip_address(request.client.host)
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if not any(peer in ip_network(value.strip(), strict=False) for value in settings.trusted_proxy_ips.split(",") if value.strip()):
        raise HTTPException(status_code=404, detail="Not found")


class Release(BaseModel):
    lease: UUID


@router.post("/admit", dependencies=[Depends(internal_caller)])
def admit(request: Request, user=Depends(optional_user)):
    if settings.app_env != "production":
        return {"lease":None}
    lease = uuid4().hex
    try:
        with Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1) as redis:
            count, _ = redis.eval(RATE_SCRIPT, 1, private_key("upload", str(user.id) if user else client_address(request.scope)))
            if count > settings.rate_limit_publish:
                raise HTTPException(status_code=429, detail="Esperá un momento antes de enviar más fotos.", headers={"Retry-After":"60"})
            accepted = redis.eval(SLOT_SCRIPT, 1, SLOTS, time.time(), time.time()+240, settings.upload_slots, lease)
            if not accepted:
                raise HTTPException(status_code=429, detail="Estamos recibiendo otras fotos. Intentá de nuevo en unos segundos.", headers={"Retry-After":"10"})
    except (RedisError, OSError) as exc:
        raise HTTPException(status_code=503, detail="La carga de fotos está temporalmente ocupada.") from exc
    return {"lease":lease}


@router.post("/release", dependencies=[Depends(internal_caller)])
def release(payload: Release):
    if settings.app_env == "production":
        try:
            with Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1) as redis:
                redis.zrem(SLOTS, payload.lease.hex)
        except (RedisError, OSError):
            pass  # A crashed web request cannot hold a slot beyond its lease.
    return {"ok":True}
