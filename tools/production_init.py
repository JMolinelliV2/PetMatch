"""Generate private deployment files. Never overwrite an existing installation."""
import argparse
import base64
import os
from pathlib import Path
import re
import secrets
import json
from urllib.parse import quote


def prepare_b2_secrets(root: Path, secrets_directory: Path | None = None):
    """Add empty dedicated placeholders to an existing installation; never replace a key."""
    directory=secrets_directory if secrets_directory is not None else root.resolve()/".secrets"
    if not directory.is_dir() or directory.is_symlink():raise ValueError("Initialize the private secrets directory first")
    for name in ("b2_key_id","b2_application_key"):
        path=directory/name
        if path.exists() or path.is_symlink():continue
        with open(path,"x",encoding="utf-8",opener=lambda name,flags:os.open(name,flags,0o600)) as stream:stream.write("\n")
        path.chmod(0o444)


def prepare_payment_secrets(root: Path, secrets_directory: Path | None = None):
    """Prepare only empty payment placeholders; preserve installed credentials."""
    directory = secrets_directory if secrets_directory is not None else root.resolve() / ".secrets"
    if not directory.is_dir() or directory.is_symlink():
        raise ValueError("Initialize the private secrets directory first")
    for name in ("mp_access_token", "mp_webhook_secret"):
        path = directory / name
        if path.exists() or path.is_symlink():
            continue
        with open(path, "x", encoding="utf-8", opener=lambda name, flags: os.open(name, flags, 0o600)) as stream:
            stream.write("\n")
        path.chmod(0o444)


def initialize(root: Path, domain="mascomatch.com"):
    root = root.resolve()
    if not re.fullmatch(r"[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?", domain) or "." not in domain:
        raise ValueError("Use a domain name without protocol, path or port")
    directory = root / ".secrets"
    configuration = root / ".env.production"
    if directory.exists() or configuration.exists():
        raise FileExistsError("Private production files already exist; refusing to replace keys")
    root.mkdir(parents=True, exist_ok=True)
    directory.mkdir(mode=0o700)
    owner_password, app_password, redis_password = [secrets.token_urlsafe(32) for _ in range(3)]
    data = {
        "db_owner_password": owner_password,
        "app_db_password": app_password,
        "database_url": f"postgresql+psycopg://mascomatch_app:{quote(app_password)}@db:5432/mascomatch",
        "migrator_database_url": f"postgresql+psycopg://mascomatch_owner:{quote(owner_password)}@db:5432/mascomatch",
        "jwt_secret": secrets.token_urlsafe(48),
        "redis_password": redis_password,
        "redis_url": f"redis://:{quote(redis_password)}@redis:6379/0",
        "redis_config": f"bind 0.0.0.0\nprotected-mode yes\nrequirepass {redis_password}\nappendonly yes\nmaxmemory 256mb\nmaxmemory-policy noeviction\n",
        "photos_admin_secret": secrets.token_urlsafe(32),
        "s3_secret_key": secrets.token_urlsafe(32),
        "vision_s3_secret": secrets.token_urlsafe(32),
        "smtp_password": "",
        "mp_access_token": "",
        "mp_webhook_secret": "",
        "metrics_token": secrets.token_urlsafe(48),
        "backup_key": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
        "b2_key_id":"",
        "b2_application_key":"",
    }
    data["photos_config"] = json.dumps({"identities":[
        {"name":"operator","credentials":[{"accessKey":"mascomatch_admin","secretKey":data["photos_admin_secret"]}],"actions":["Admin","Read","Write","List"]},
        {"name":"application","credentials":[{"accessKey":"mascomatch_app","secretKey":data["s3_secret_key"]}],"actions":["Read:pet-photos","Write:pet-photos","List:pet-photos"]},
        {"name":"vision","credentials":[{"accessKey":"mascomatch_vision","secretKey":data["vision_s3_secret"]}],"actions":["Read:pet-photos","List:pet-photos"]}
    ]})
    for name, value in data.items():
        with open(directory / name, "x", encoding="utf-8", newline="\n", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
            stream.write(value + "\n")
        # Docker mounts individual files into non-root services. The host parent
        # stays private (0700); no container receives that directory as a mount.
        (directory / name).chmod(0o444)
    public = f"""# Private keys live in .secrets/, not in this file.
SITE_DOMAIN={domain}
WEB_ORIGIN=https://{domain}
PUBLIC_SITE_URL=https://{domain}
ANALYTICS_ENABLED=true
RATE_LIMIT_ANALYTICS=120
RATE_LIMIT_ANALYTICS_DAILY=200000
ANALYTICS_VISITOR_DAYS=180
ANALYTICS_SESSION_MINUTES=30
ANALYTICS_RAW_DAYS=90
ANALYTICS_DAILY_DAYS=730
ALLOWED_HOSTS={domain},localhost,127.0.0.1,api
AI_ENABLED=false
EMBEDDINGS_ENABLED=false
PET_REID_ENABLED=true
OPENCLIP_ENABLED=true
PET_CROP_ENABLED=true
PET_CROP_CONFIDENCE=0.75
PET_CROP_MARGIN=0.18
EMBEDDING_CPU_THREADS=2
AI_TEXT_MODEL=gemma3:4b
AI_VISION_MODEL=gemma3:4b
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_PREDICT=768
OLLAMA_NUM_THREADS=3
OLLAMA_KEEP_ALIVE=15m
OLLAMA_PREWARM=true
OLLAMA_MEMORY_LIMIT=10g
VISUAL_WORKER_MEMORY_LIMIT=4g
DATABASE_MEMORY_LIMIT=2g
STORAGE_MEMORY_LIMIT=1g
BACKUP_MEMORY_LIMIT=3g
AI_TEXT_REQUEST_TIMEOUT_SECONDS=120
AI_VISION_REQUEST_TIMEOUT_SECONDS=240
VLM_IMAGE_MAX_SIDE=1024
VLM_IMAGE_JPEG_QUALITY=88
OPENCLIP_VISUAL_FLOOR=0.55
OPENCLIP_VISUAL_CEILING=0.95
PET_REID_VISUAL_FLOOR=0.50
PET_REID_VISUAL_CEILING=0.90
VISUAL_BEST_WEIGHT=0.7
MATCHING_ANALYSIS_WAIT_SECONDS=30
MATCHING_NOTIFY_MIN_COVERAGE=0.35
MATCHING_NOTIFY_MIN_FEATURE=0.65
MATCHING_NOTIFY_MIN_GEO=0.35
MAIL_DELIVERY_MODE=disabled
SMTP_HOST=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_FROM=MascoMatch <info@{domain}>
SMTP_TLS_MODE=starttls
MP_ENABLED=false
MP_ENVIRONMENT=test
MP_COLLECTOR_ID=
MP_APPLICATION_ID=
MP_PUBLIC_BASE_URL=https://{domain}
RATE_LIMIT_DONATION=6
RATE_LIMIT_PAYMENT_WEBHOOK=180
NEXT_PUBLIC_SEARCH_COUNTRY=UY
BACKUP_INTERVAL_SECONDS=21600
BACKUP_LOCAL_KEEP=14
OFFSITE_BACKUP_ENABLED=false
OFFSITE_RETRY_INTERVAL_SECONDS=900
OFFSITE_DEEP_VERIFY_INTERVAL_SECONDS=604800
B2_ENDPOINT=
B2_REGION=
B2_BUCKET=
B2_OBJECT_LOCK_ENABLED=true
B2_OBJECT_LOCK_DAYS=30
B2_OPERATION_TIMEOUT_SECONDS=900
"""
    with open(configuration, "x", encoding="utf-8", newline="\n", opener=lambda path, flags: os.open(path, flags, 0o600)) as stream:
        stream.write(public)
    return configuration


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path.cwd())
    parser.add_argument("--domain", default="mascomatch.com")
    parser.add_argument("--prepare-b2-secrets",action="store_true",help="Add missing empty B2 secret files to an existing installation")
    parser.add_argument("--prepare-payment-secrets", action="store_true", help="Add missing empty payment secret files without replacing credentials")
    parser.add_argument("--secrets-directory",type=Path,help="Existing private secrets directory, for upgrade preparation only")
    args = parser.parse_args()
    if args.prepare_b2_secrets:
        prepare_b2_secrets(args.directory,args.secrets_directory)
        print("Dedicated B2 secret placeholders ready; existing keys preserved.")
    elif args.prepare_payment_secrets:
        prepare_payment_secrets(args.directory, args.secrets_directory)
        print("Payment secret placeholders ready; existing credentials preserved.")
    else:
        print("Created private deployment files:", initialize(args.directory, args.domain))
        print("Store backup_key separately from the server; losing it makes backups unrecoverable.")
