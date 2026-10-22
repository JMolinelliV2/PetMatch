"""Non-secret backup telemetry shared through existing Redis, never B2 credentials."""
import json
import math
from redis import Redis
from app.core.config import settings

STATUS_KEY="mascomatch:backup:status"
CODES={"LOCAL_BACKUP_FAILED","LOCAL_VERIFY_FAILED","OFFSITE_UPLOAD_FAILED","OFFSITE_VERIFY_FAILED",
       "OFFSITE_AUTH_FAILED","OFFSITE_CONFIGURATION_ERROR","OFFSITE_RETENTION_ERROR"}
NUMBERS=("local_last_success","offsite_last_success","offsite_last_attempt","pending_count","failures_total",
         "consecutive_failures","last_size_bytes","last_duration_seconds","latest_capture","last_deep_verify",
         "object_count","stored_bytes","inventory_at","heartbeat","local_free_bytes","local_interval")


def public_status(value):
    result={"known":True,"enabled":bool(value.get("enabled",False)),"inventory_truncated":bool(value.get("inventory_truncated",False))}
    for name in NUMBERS:
        number=value.get(name,0)
        result[name]=number if isinstance(number,(int,float)) and math.isfinite(number) and number>=0 else 0
    result["error_code"]=value.get("error_code") if value.get("error_code") in CODES else None
    result["local_error_code"]=value.get("local_error_code") if value.get("local_error_code") in CODES else None
    return result


def publish(value):
    try:
        with Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2) as redis:
            redis.set(STATUS_KEY,json.dumps(public_status(value),allow_nan=False))
            if value.get("local_last_success"):redis.set("mascomatch:backup:last_success",value["local_last_success"])
    except Exception:
        pass  # Redis outage cannot invalidate a completed local archive.


def read_status():
    try:
        with Redis.from_url(settings.redis_url,socket_connect_timeout=1,socket_timeout=1) as redis:
            payload=redis.get(STATUS_KEY)
            if payload and len(payload)<=16384:
                return public_status(json.loads(payload))
            return {**public_status({"local_last_success":float(redis.get("mascomatch:backup:last_success") or 0)}),"known":False}
    except Exception:
        pass
    return {**public_status({}),"known":False}


def metric_values(status):
    fields={"local_last_success":"mascomatch_backup_last_success_unixtime",
        "local_interval":"mascomatch_backup_interval_seconds","local_free_bytes":"mascomatch_backup_free_bytes",
        "heartbeat":"mascomatch_backup_heartbeat_unixtime","offsite_last_success":"mascomatch_offsite_backup_last_success_unixtime",
        "offsite_last_attempt":"mascomatch_offsite_backup_last_attempt_unixtime","pending_count":"mascomatch_offsite_backup_pending_count",
        "failures_total":"mascomatch_offsite_backup_failures_total","consecutive_failures":"mascomatch_offsite_backup_consecutive_failures",
        "last_size_bytes":"mascomatch_offsite_backup_last_size_bytes","last_duration_seconds":"mascomatch_offsite_backup_last_duration_seconds",
        "latest_capture":"mascomatch_offsite_backup_latest_capture_unixtime","last_deep_verify":"mascomatch_offsite_backup_last_deep_verify_unixtime",
        "object_count":"mascomatch_offsite_backup_objects","stored_bytes":"mascomatch_offsite_backup_stored_bytes",
        "inventory_at":"mascomatch_offsite_backup_inventory_unixtime"}
    clean=public_status(status)
    result={metric:clean[field] for field,metric in fields.items()}
    result.update(mascomatch_offsite_backup_enabled=int(clean["enabled"]),mascomatch_backup_status_known=int(bool(status.get("known"))),
                  mascomatch_offsite_backup_inventory_truncated=int(clean["inventory_truncated"]))
    return result
