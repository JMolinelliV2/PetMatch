"""Authenticated encrypted backups of one PostgreSQL snapshot and its private photos."""
import argparse
import base64
from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import tarfile
import tempfile
import time
from uuid import uuid4

from botocore.exceptions import ClientError
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
import psycopg
from redis import Redis
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.core.image_storage import _client

MAGIC = b"MASCOMATCH-BACKUP\x01"
CHUNK = 1024 * 1024
MAX_BYTES = 1024 * 1024 * 1024


def key():
    value = base64.urlsafe_b64decode(settings.backup_key.get_secret_value())
    if len(value) != 32:
        raise ValueError("A separate 32-byte backup key is required")
    return value


class EncryptWriter:
    def __init__(self, stream, secret):
        nonce = secrets.token_bytes(12)
        self.stream, self.count = stream, 0
        self.cipher = Cipher(algorithms.AES(secret), modes.GCM(nonce)).encryptor()
        self.cipher.authenticate_additional_data(MAGIC)
        stream.write(MAGIC + nonce)

    def write(self, payload):
        self.count += len(payload)
        if self.count > MAX_BYTES:
            raise ValueError("Backup exceeds the configured MVP size limit")
        self.stream.write(self.cipher.update(payload))
        return len(payload)

    def finish(self):
        self.stream.write(self.cipher.finalize())
        self.stream.write(self.cipher.tag)


def decrypt(source, destination, secret):
    size = Path(source).stat().st_size
    header_size = len(MAGIC) + 12
    if size > MAX_BYTES + header_size + 16 or size < header_size + 16:
        raise ValueError("Invalid backup size")
    with Path(source).open("rb") as stream:
        if stream.read(len(MAGIC)) != MAGIC:
            raise ValueError("Unsupported backup format")
        nonce = stream.read(12)
        stream.seek(-16, os.SEEK_END)
        tag = stream.read(16)
        stream.seek(header_size)
        cipher = Cipher(algorithms.AES(secret), modes.GCM(nonce, tag)).decryptor()
        cipher.authenticate_additional_data(MAGIC)
        left = size-header_size-16
        try:
            with Path(destination).open("xb") as result:
                while left:
                    payload = stream.read(min(CHUNK, left))
                    if not payload:
                        raise ValueError("Truncated backup")
                    result.write(cipher.update(payload))
                    left -= len(payload)
                result.write(cipher.finalize())
        except InvalidTag as exc:
            raise ValueError("Backup integrity check failed") from exc


def connection_url(value):
    return make_url(value).set(drivername="postgresql").render_as_string(hide_password=False)


def pg_environment(value, directory):
    url = make_url(value)
    def escape(part):
        return str(part).replace("\\", "\\\\").replace(":", "\\:")
    password = Path(directory) / "pgpass"
    password.write_text(":".join(escape(part) for part in (url.host or "localhost", url.port or 5432, url.database, url.username, url.password or ""))+"\n")
    password.chmod(0o600)
    return {**os.environ, "PGHOST":url.host or "localhost", "PGPORT":str(url.port or 5432),
            "PGDATABASE":url.database, "PGUSER":url.username, "PGPASSFILE":str(password)}


def run_pg(arguments, environment):
    result = subprocess.run(arguments, env=environment, capture_output=True)
    if result.returncode:
        # Subprocess details may contain SQL evidence or connection information.
        raise RuntimeError("PostgreSQL backup/restore command failed")


class HashReader:
    def __init__(self, stream):
        self.stream, self.digest = stream, sha256()

    def read(self, size=-1):
        payload = self.stream.read(size)
        self.digest.update(payload)
        return payload


def photo_object(client, storage_key, mime):
    try:
        return client.get_object(Bucket=settings.s3_bucket, Key=storage_key)
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") not in {"NoSuchKey","404"}:
            raise
        # Production keys are immutable UUIDs and deletes retain their versions.
        versions = client.list_object_versions(Bucket=settings.s3_bucket, Prefix=storage_key).get("Versions", [])
        versions = [item for item in versions if item["Key"] == storage_key]
        if not versions:
            raise ValueError("A referenced photo is missing") from exc
        latest = max(versions, key=lambda item:item["LastModified"])
        return client.get_object(Bucket=settings.s3_bucket, Key=storage_key, VersionId=latest["VersionId"])


def safe_name(name):
    path = PurePosixPath(name)
    return not path.is_absolute() and not any(part in {"..", "."} for part in path.parts) and "\\" not in name


def file_hash(path):
    digest = sha256()
    with Path(path).open("rb") as stream:
        for payload in iter(lambda:stream.read(CHUNK), b""):
            digest.update(payload)
    return digest.hexdigest()


def create_backup(directory):
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    filename = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex + ".mbak"
    target, temporary = directory / filename, directory / (filename + ".partial")
    secret = key()
    client = _client(settings.s3_endpoint)
    manifest = {"format":1, "created_at":datetime.now(timezone.utc).isoformat(), "photos":[]}
    try:
        with tempfile.TemporaryDirectory(prefix="mascomatch-backup-") as workspace:
            dump = Path(workspace) / "database.dump"
            with psycopg.connect(connection_url(settings.database_url)) as db:
                db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                snapshot = db.execute("SELECT pg_export_snapshot()").fetchone()[0]
                rows = db.execute("SELECT storage_key,mime_type FROM photos ORDER BY id").fetchall()
                rows += db.execute("SELECT avatar_storage_key,'image/jpeg' FROM users WHERE avatar_storage_key IS NOT NULL ORDER BY id").fetchall()
                run_pg(["pg_dump", "--format=custom", "--no-owner", "--no-acl", "--snapshot="+snapshot, "--file="+str(dump)], pg_environment(settings.database_url, workspace))
            manifest["database_sha256"] = file_hash(dump)
            with temporary.open("xb") as stream:
                temporary.chmod(0o600)
                writer = EncryptWriter(stream, secret)
                with tarfile.open(fileobj=writer, mode="w|") as archive:
                    archive.add(dump, arcname="database.dump", recursive=False)
                    for storage_key, mime in rows:
                        name = "photos/" + storage_key
                        if not safe_name(name) or len(manifest["photos"]) >= 20000:
                            raise ValueError("Invalid or excessive photo evidence")
                        photo = photo_object(client, storage_key, mime)
                        try:
                            info = tarfile.TarInfo(name)
                            info.size, info.mode = photo["ContentLength"], 0o600
                            reader = HashReader(photo["Body"])
                            archive.addfile(info, reader)
                            manifest["photos"].append({"key":storage_key, "mime":mime, "sha256":reader.digest.hexdigest()})
                        finally:
                            photo["Body"].close()
                    payload = json.dumps(manifest).encode()
                    info = tarfile.TarInfo("manifest.json")
                    info.size, info.mode = len(payload), 0o600
                    archive.addfile(info, BytesIO(payload))
                writer.finish()
                stream.flush()
                os.fsync(stream.fileno())
            temporary.replace(target)
        # A completed file is only a successful backup after authentication and hashes.
        try:
            with tempfile.TemporaryDirectory(prefix="mascomatch-verify-") as workspace:
                verified_archive(target,workspace)
        except Exception:
            from app.ops.offsite import OffsiteError
            raise OffsiteError("LOCAL_VERIFY_FAILED") from None
        try:
            with Redis.from_url(settings.redis_url,socket_connect_timeout=2,socket_timeout=2) as redis:
                redis.set("mascomatch:backup:last_success",time.time())
        except Exception:pass
        return target
    finally:
        temporary.unlink(missing_ok=True)


def verified_archive(source, workspace):
    decrypted = Path(workspace) / "archive.tar"
    decrypt(source, decrypted, key())
    with tarfile.open(decrypted, "r:") as archive:
        members = archive.getmembers()
        names = [item.name for item in members]
        if len(members) > 20002 or len(set(names)) != len(names) or any(not item.isreg() or not safe_name(item.name) for item in members):
            raise ValueError("Unsafe backup archive")
        manifest_member = archive.getmember("manifest.json")
        if manifest_member.size > 10*1024*1024:
            raise ValueError("Excessive manifest")
        manifest = json.loads(archive.extractfile(manifest_member).read())
        expected = {"database.dump":manifest["database_sha256"], **{"photos/"+item["key"]:item["sha256"] for item in manifest["photos"]}}
        if set(names) != {*expected, "manifest.json"}:
            raise ValueError("Manifest does not match backup evidence")
        for name, digest in expected.items():
            stream = archive.extractfile(name)
            hasher = sha256()
            with stream:
                for payload in iter(lambda:stream.read(CHUNK), b""):
                    hasher.update(payload)
            if hasher.hexdigest() != digest:
                raise ValueError("Evidence checksum failed")
    return decrypted, manifest


def restore_backup(source, target_database_url):
    # Authenticate every byte before touching either recovery destination.
    with tempfile.TemporaryDirectory(prefix="mascomatch-restore-") as workspace:
        decrypted, manifest = verified_archive(source, workspace)
        client = _client(settings.s3_endpoint)
        with psycopg.connect(connection_url(target_database_url)) as db:
            existing = db.execute("""SELECT 1 FROM pg_class c JOIN pg_namespace n ON c.relnamespace=n.oid
                WHERE c.relkind IN ('r','p') AND n.nspname NOT IN ('pg_catalog','information_schema')
                AND NOT EXISTS (SELECT 1 FROM pg_depend d WHERE d.objid=c.oid AND d.classid='pg_class'::regclass AND d.deptype='e') LIMIT 1""").fetchone()
            if existing:
                raise ValueError("Recovery database must contain no application tables")
        if client.list_objects_v2(Bucket=settings.s3_bucket, MaxKeys=1).get("KeyCount", 0):
            raise ValueError("Recovery photo bucket must be empty")
        uploaded = []
        try:
            with tarfile.open(decrypted, "r:") as archive:
                dump = Path(workspace) / "database.dump"
                with archive.extractfile("database.dump") as payload, dump.open("xb") as output:
                    for block in iter(lambda:payload.read(CHUNK), b""):
                        output.write(block)
                for item in manifest["photos"]:
                    with archive.extractfile("photos/"+item["key"]) as payload:
                        client.upload_fileobj(payload, settings.s3_bucket, item["key"], ExtraArgs={"ContentType":item["mime"]})
                    uploaded.append(item["key"])
            run_pg(["pg_restore", "--no-owner", "--no-acl", "--exit-on-error", "--single-transaction", "--dbname="+make_url(target_database_url).database, str(dump)], pg_environment(target_database_url, workspace))
        except Exception:
            for storage_key in uploaded:
                client.delete_object(Bucket=settings.s3_bucket, Key=storage_key)
            raise
    print("Backup restored to empty recovery destinations")


def cycle(state,config,*,create=True,local_only=False):
    from app.ops.offsite import Offsite,OffsiteError,classify,deep_verify,exclusive,prune_local,reconcile
    import shutil
    remote=Offsite(config) if config.offsite_backup_enabled and not local_only else None
    with exclusive(state.directory):
        state.value.update(enabled=config.offsite_backup_enabled,local_interval=max(3600,int(os.getenv("BACKUP_INTERVAL_SECONDS","21600"))))
        if create:
            try:
                result=create_backup(state.directory)
                state.value.update(local_last_success=time.time(),local_error_code=None)
                print("backup_completed",result.name,flush=True)
            except Exception as exc:
                code=exc.code if isinstance(exc,OffsiteError) else "LOCAL_BACKUP_FAILED"
                state.value["local_error_code"]=code;print(code,flush=True)
        state.save()
        if remote:
            try:
                reconcile(state,remote)
                if (not state.value.get("error_code") and
                    time.time()-state.value.get("last_deep_verify",0)>=config.offsite_deep_verify_interval_seconds):
                    deep_verify(state,remote)
            except Exception as exc:state.failed(classify(exc,"OFFSITE_VERIFY_FAILED"))
        elif not local_only:state.value.update(pending_count=0,error_code=None,consecutive_failures=0)
        if not local_only and not state.value.get("local_error_code") and (not remote or not state.value.get("error_code")):
            prune_local(state,max(1,int(os.getenv("BACKUP_LOCAL_KEEP","14"))),remote)
        state.value["local_free_bytes"]=shutil.disk_usage(state.directory).free;state.save()


def serve(directory,config):
    from app.ops.offsite import BackupBusy,State
    state=State(directory)
    interval=max(3600,int(os.getenv("BACKUP_INTERVAL_SECONDS","21600")))
    retry=max(60,min(3600,int(os.getenv("OFFSITE_RETRY_INTERVAL_SECONDS","900"))))
    due=0
    while True:
        started=time.monotonic();create=started>=due;busy=False
        try:cycle(state,config,create=create)
        except BackupBusy:busy=True;print("Backup writer already running; retry later",flush=True)
        except Exception:print("LOCAL_BACKUP_FAILED",flush=True)
        if create:due=started+(retry if busy or state.value.get("local_error_code") else interval)
        time.sleep(min(retry,max(1,due-time.monotonic())))


def main():
    from app.ops.offsite import BackupBusy,Offsite,OffsiteError,State,deep_verify,exclusive,load_config,validate_key
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create","verify","restore","serve","sync-offsite","check-offsite","verify-offsite","list-offsite","restore-offsite"])
    parser.add_argument("path", nargs="?")
    parser.add_argument("--directory",type=Path,default=Path("/backups"))
    parser.add_argument("--target-database-file", type=Path)
    parser.add_argument("--deep",action="store_true")
    parser.add_argument("--local-only",action="store_true",help="Create/verify a deployment safety copy without waiting for B2; no pruning")
    parser.add_argument("--version-id")
    parser.add_argument("--limit",type=int,default=100,choices=range(1,1001),metavar="1..1000")
    parser.add_argument("--retention",action="store_true",help="Read retention for each listed version (additional API calls)")
    args = parser.parse_args()
    if args.local_only and args.action!="create":parser.error("--local-only is restricted to create")
    state=None if args.action in {"verify","restore"} else State(Path(args.path) if args.action in {"create","serve"} and args.path else args.directory)
    try:
        if args.local_only:
            from types import SimpleNamespace
            config=SimpleNamespace(offsite_backup_enabled=os.getenv("OFFSITE_BACKUP_ENABLED","false").lower() in {"true","1"})
        else:config=load_config() if args.action not in {"verify","restore"} else None
        if args.action=="serve":serve(state.directory,config)
        elif args.action=="create":
            cycle(state,config,local_only=args.local_only)
            if state.value.get("local_error_code") or (not args.local_only and state.value.get("error_code")):raise SystemExit(1)
        elif args.action=="sync-offsite":
            if not config.offsite_backup_enabled:raise OffsiteError("OFFSITE_CONFIGURATION_ERROR")
            cycle(state,config,create=False)
            if state.value.get("error_code"):raise SystemExit(1)
        elif args.action=="verify":
            if not args.path:parser.error("Provide a local encrypted archive")
            with tempfile.TemporaryDirectory() as directory:
                _,manifest=verified_archive(Path(args.path),directory)
                print("Backup authenticated; photo count:",len(manifest["photos"]))
        elif args.action=="restore":
            if not args.path or not args.target_database_file:parser.error("Provide an archive and explicit empty recovery database file")
            restore_backup(Path(args.path),args.target_database_file.read_text().strip())
        else:
            remote=Offsite(config);remote.check()
            if args.action=="check-offsite":print("B2 private bucket and retention configuration verified")
            elif args.action=="list-offsite":
                rows,truncated=remote.objects()
                for item in sorted(rows,key=lambda row:row["Key"],reverse=True)[:args.limit]:
                    info=remote.verify(item["Key"],version=item["VersionId"]) if args.retention else {}
                    print(json.dumps({"key":item["Key"],"version_id":item["VersionId"],"created_at":item["LastModified"].isoformat(),
                        "size":item["Size"],"retained_until":info.get("retained_until"),"latest":item.get("IsLatest")},sort_keys=True))
                print(json.dumps({"listed_objects":len(rows),"inventory_truncated":truncated}))
            elif args.action=="verify-offsite":
                with exclusive(state.directory):
                    item=None if args.path else remote.latest()
                    key=validate_key(args.path or item["Key"]);version=args.version_id or (item["VersionId"] if item else None)
                    info=deep_verify(state,remote,key,version) if args.deep else remote.verify(key,version=version)
                    print(json.dumps({"verified":True,"deep":args.deep,**info},sort_keys=True))
            elif args.action=="restore-offsite":
                if not args.path or not args.target_database_file:parser.error("Provide an object key and explicit empty recovery database file")
                with exclusive(state.directory),tempfile.TemporaryDirectory(prefix=".b2-restore-",dir=state.directory) as directory:
                    archive,_=remote.download(validate_key(args.path),directory,args.version_id)
                    restore_backup(archive,args.target_database_file.read_text().strip())
    except BackupBusy:
        print("Backup writer already running; retry later",flush=True)
        raise SystemExit(2) from None
    except OffsiteError as exc:
        if state:
            state.value["enabled"]=os.getenv("OFFSITE_BACKUP_ENABLED","false").lower() in {"true","1"}
            state.failed(exc)
        else:print(exc.code,flush=True)
        raise SystemExit(1) from None
    except Exception:
        print("LOCAL_VERIFY_FAILED" if args.action in {"verify","restore"} else "OFFSITE_VERIFY_FAILED",flush=True)
        raise SystemExit(1) from None


if __name__=="__main__":main()
