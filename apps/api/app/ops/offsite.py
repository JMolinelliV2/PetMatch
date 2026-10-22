"""B2 S3 disaster-recovery copies of verified encrypted archives; no operational photos."""
from contextlib import contextmanager
from datetime import datetime,timedelta,timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlsplit

import boto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError
from pydantic import Field,SecretStr,model_validator
from pydantic_settings import BaseSettings,SettingsConfigDict

UTC=timezone.utc
NAME=re.compile(r"(?P<stamp>[0-9]{8}T[0-9]{6}Z)-[a-f0-9]{32}\.mbak")
PREFIX="backups/"
MAX_OBJECTS=10000
MAX_ARCHIVE_BYTES=1024**3+128


class OffsiteError(RuntimeError):
    def __init__(self,code):
        self.code=code
        super().__init__(code)  # Never copy SDK messages/URLs/credentials into logs.


class BackupBusy(OffsiteError):
    def __init__(self):super().__init__("OFFSITE_UPLOAD_FAILED")


class OffsiteConfig(BaseSettings):
    model_config=SettingsConfigDict(extra="ignore",hide_input_in_errors=True)
    offsite_backup_enabled:bool=False
    b2_endpoint:str=""
    b2_region:str=""
    b2_bucket:str=""
    b2_key_id_file:str|None=Field(default=None,repr=False)
    b2_application_key_file:str|None=Field(default=None,repr=False)
    b2_key_id:SecretStr=Field(default=SecretStr(""),repr=False)
    b2_application_key:SecretStr=Field(default=SecretStr(""),repr=False)
    b2_object_lock_enabled:bool=True
    b2_object_lock_days:int=Field(default=30,ge=1,le=3000)
    b2_operation_timeout_seconds:int=Field(default=900,ge=30,le=3600)
    offsite_deep_verify_interval_seconds:int=Field(default=604800,ge=86400,le=2592000)

    @model_validator(mode="after")
    def validate_destination(self):
        if not self.offsite_backup_enabled:return self
        endpoint=urlsplit(self.b2_endpoint)
        if (endpoint.scheme!="https" or endpoint.username or endpoint.password or endpoint.port not in (None,443)
            or endpoint.path not in ("","/") or endpoint.query or endpoint.fragment
            or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+",self.b2_region)
            or endpoint.hostname!=f"s3.{self.b2_region}.backblazeb2.com"
            or not re.fullmatch(r"[a-z0-9][a-z0-9-]{4,61}[a-z0-9]",self.b2_bucket)):
            raise ValueError("Configure an explicit B2 HTTPS endpoint, matching region and private backup bucket")
        from app.core.config import settings
        if self.b2_bucket==settings.s3_bucket:raise ValueError("Backup destination must differ from the operational photo bucket")
        for name in ("b2_key_id","b2_application_key"):
            filename=getattr(self,name+"_file")
            if not filename or getattr(self,name).get_secret_value():raise ValueError("B2 credentials require dedicated secret files")
            try:
                with Path(filename).open("rb") as stream:payload=stream.read(16385)
                value=payload.decode().strip()
                if not value or len(payload)>16384:raise ValueError("Invalid B2 secret file")
            except (OSError,UnicodeError) as exc:
                raise ValueError("Cannot read dedicated B2 secret file") from exc
            setattr(self,name,SecretStr(value))
        return self

    @property
    def destination(self):
        return sha256((self.b2_endpoint.rstrip("/")+"|"+self.b2_bucket+"|"+PREFIX).encode()).hexdigest()


def load_config():
    try:return OffsiteConfig(_env_file=None)
    except Exception:raise OffsiteError("OFFSITE_CONFIGURATION_ERROR") from None


def classify(exc,default):
    if isinstance(exc,OffsiteError):return exc
    nested=exc.__cause__ or exc.__context__
    if nested is not None and nested is not exc and isinstance(nested,(ClientError,OffsiteError)):
        return classify(nested,default)
    if isinstance(exc,ClientError):
        code=exc.response.get("Error",{}).get("Code","")
        if code in {"AccessDenied","InvalidAccessKeyId","SignatureDoesNotMatch","ExpiredToken","InvalidToken","Unauthorized","403","401"}:
            return OffsiteError("OFFSITE_AUTH_FAILED")
        if code in {"NoSuchBucket","InvalidBucketName","AuthorizationHeaderMalformed","PermanentRedirect"}:
            return OffsiteError("OFFSITE_CONFIGURATION_ERROR")
    return OffsiteError(default)


def client_for(config):
    # No default credential chain, bucket creation, SDK debug logging or insecure transport.
    return boto3.client("s3",endpoint_url=config.b2_endpoint,region_name=config.b2_region,
        aws_access_key_id=config.b2_key_id.get_secret_value(),aws_secret_access_key=config.b2_application_key.get_secret_value(),
        verify=True,config=Config(signature_version="s3v4",connect_timeout=10,read_timeout=60,
            retries={"mode":"standard","total_max_attempts":3},s3={"addressing_style":"path"},
            request_checksum_calculation="when_required",response_checksum_validation="when_required"))


def archive_paths(directory):
    return sorted(p for p in Path(directory).iterdir() if NAME.fullmatch(p.name) and p.is_file() and not p.is_symlink())


def object_key(filename):
    match=NAME.fullmatch(filename)
    if not match:raise OffsiteError("OFFSITE_CONFIGURATION_ERROR")
    try:date=datetime.strptime(match["stamp"],"%Y%m%dT%H%M%SZ")
    except ValueError:raise OffsiteError("OFFSITE_CONFIGURATION_ERROR") from None
    return PREFIX+date.strftime("%Y/%m/%d/")+filename


def validate_key(value):
    if not isinstance(value,str) or len(value)>180 or "\\" in value or value!=object_key(value.rsplit("/",1)[-1]):
        raise OffsiteError("OFFSITE_CONFIGURATION_ERROR")
    return value


def capture_time(filename):
    return datetime.strptime(NAME.fullmatch(filename)["stamp"],"%Y%m%dT%H%M%SZ").replace(tzinfo=UTC).timestamp()


def atomic_json(path,value):
    path=Path(path)
    if path.is_symlink():raise OffsiteError("OFFSITE_CONFIGURATION_ERROR")
    fd,name=tempfile.mkstemp(prefix=path.name+".",suffix=".pending",dir=path.parent)
    try:
        os.chmod(name,0o600)
        with os.fdopen(fd,"w",encoding="utf-8") as stream:
            json.dump(value,stream,allow_nan=False);stream.flush();os.fsync(stream.fileno())
        Path(name).replace(path)
    finally:Path(name).unlink(missing_ok=True)


def read_json(path):
    try:
        if path.is_symlink() or path.stat().st_size>16384:return {}
        value=json.loads(path.read_text())
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):return {}


@contextmanager
def exclusive(directory):
    # The backup volume has one writer; manual uploads and the daemon share this lock.
    import fcntl
    target=Path(directory)/".offsite.lock"
    descriptor=os.open(target,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    with os.fdopen(descriptor,"a+") as stream:
        try:fcntl.flock(stream,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:raise BackupBusy() from None
        try:yield
        finally:fcntl.flock(stream,fcntl.LOCK_UN)


class Offsite:
    def __init__(self,config,client=None):
        if not config.offsite_backup_enabled:raise OffsiteError("OFFSITE_CONFIGURATION_ERROR")
        self.config=config;self.client=client or client_for(config)

    def check(self):
        try:
            self.client.head_bucket(Bucket=self.config.b2_bucket)
            acl=self.client.get_bucket_acl(Bucket=self.config.b2_bucket)
            if any(g.get("Grantee",{}).get("Type")=="Group" for g in acl.get("Grants",[])):
                raise OffsiteError("OFFSITE_CONFIGURATION_ERROR")
            try:lock=self.client.get_object_lock_configuration(Bucket=self.config.b2_bucket).get("ObjectLockConfiguration",{})
            except ClientError as exc:
                if exc.response.get("Error",{}).get("Code") not in {"ObjectLockConfigurationNotFoundError","NoSuchObjectLockConfiguration","404"}:raise
                lock={}
            if self.config.b2_object_lock_enabled:
                default=lock.get("Rule",{}).get("DefaultRetention",{})
                if lock.get("ObjectLockEnabled")!="Enabled" or default.get("Mode")!="COMPLIANCE" or default.get("Days")!=self.config.b2_object_lock_days:
                    raise OffsiteError("OFFSITE_RETENTION_ERROR")
            elif lock.get("ObjectLockEnabled")=="Enabled":raise OffsiteError("OFFSITE_RETENTION_ERROR")
        except Exception as exc:raise classify(exc,"OFFSITE_VERIFY_FAILED") from None

    def head(self,key,version=None):
        if version is not None and (not isinstance(version,str) or not 1<=len(version)<=1024):
            raise OffsiteError("OFFSITE_CONFIGURATION_ERROR")
        try:return self.client.head_object(Bucket=self.config.b2_bucket,Key=validate_key(key),**({"VersionId":version} if version else {}))
        except ClientError as exc:
            if exc.response.get("Error",{}).get("Code") in {"404","NoSuchKey","NotFound","NoSuchVersion"}:return None
            raise classify(exc,"OFFSITE_VERIFY_FAILED") from None
        except Exception as exc:raise classify(exc,"OFFSITE_VERIFY_FAILED") from None

    def verify(self,key,expected_size=None,expected_sha=None,version=None):
        head=self.head(key,version)
        if not head:raise OffsiteError("OFFSITE_VERIFY_FAILED")
        size=head.get("ContentLength",0);digest=head.get("Metadata",{}).get("mascomatch-sha256","")
        if not 0<size<=MAX_ARCHIVE_BYTES or not re.fullmatch("[a-f0-9]{64}",digest) or (expected_size is not None and size!=expected_size) or (expected_sha and digest!=expected_sha):
            raise OffsiteError("OFFSITE_VERIFY_FAILED")
        version=head.get("VersionId")
        uploaded=head.get("LastModified")
        if not version or not isinstance(uploaded,datetime):raise OffsiteError("OFFSITE_VERIFY_FAILED")
        retained=None
        if self.config.b2_object_lock_enabled:
            try:
                retention=self.client.get_object_retention(Bucket=self.config.b2_bucket,Key=validate_key(key),VersionId=version)["Retention"]
                retained=retention.get("RetainUntilDate")
                if retention.get("Mode")!="COMPLIANCE" or not isinstance(retained,datetime) or not isinstance(uploaded,datetime) or retained<uploaded+timedelta(days=self.config.b2_object_lock_days)-timedelta(seconds=60):
                    raise OffsiteError("OFFSITE_RETENTION_ERROR")
            except Exception as exc:raise classify(exc,"OFFSITE_RETENTION_ERROR") from None
        return {"key":key,"size":size,"sha256":digest,"version_id":version,"uploaded_at":uploaded.timestamp(),
                "retained_until":retained.isoformat() if retained else None}

    def upload(self,path):
        from app.ops.backup import file_hash,verified_archive
        path=Path(path)
        if path.is_symlink() or not path.is_file():raise OffsiteError("OFFSITE_CONFIGURATION_ERROR")
        key=object_key(path.name)
        try:
            with tempfile.TemporaryDirectory(prefix="mascomatch-local-verify-") as workspace:verified_archive(path,workspace)
        except Exception:raise OffsiteError("LOCAL_VERIFY_FAILED") from None
        size=path.stat().st_size;digest=file_hash(path)
        if self.head(key):return self.verify(key,size,digest)  # Reconcile a lost receipt; never overwrite.
        try:
            previous=self.client.list_object_versions(Bucket=self.config.b2_bucket,Prefix=key,MaxKeys=1)
            if any(item.get("Key")==key for group in ("Versions","DeleteMarkers") for item in previous.get(group,[])):
                raise OffsiteError("OFFSITE_VERIFY_FAILED")  # A hidden version is still an existing key.
        except Exception as exc:raise classify(exc,"OFFSITE_VERIFY_FAILED") from None
        deadline=time.monotonic()+self.config.b2_operation_timeout_seconds
        def progress(_):
            if time.monotonic()>deadline:raise OffsiteError("OFFSITE_UPLOAD_FAILED")
        extra={"ContentType":"application/octet-stream","Metadata":{"mascomatch-sha256":digest}}
        if self.config.b2_object_lock_enabled:
            # Retention starts before transfer; allow its bounded duration plus network margin.
            extra.update(ObjectLockMode="COMPLIANCE",ObjectLockRetainUntilDate=datetime.now(UTC)+timedelta(
                days=self.config.b2_object_lock_days,seconds=self.config.b2_operation_timeout_seconds+180))
        try:
            self.client.upload_file(str(path),self.config.b2_bucket,key,ExtraArgs=extra,
                Config=TransferConfig(multipart_threshold=32*1024**2,multipart_chunksize=32*1024**2,max_concurrency=2,
                    max_io_queue=4,io_chunksize=1024**2,num_download_attempts=3),Callback=progress)
        except Exception as exc:raise classify(exc,"OFFSITE_UPLOAD_FAILED") from None
        return self.verify(key,size,digest)

    def download(self,key,directory,version=None):
        from app.ops.backup import file_hash,verified_archive
        info=self.verify(validate_key(key),version=version)
        destination=Path(directory)/key.rsplit("/",1)[-1]
        deadline=time.monotonic()+self.config.b2_operation_timeout_seconds
        body=None;created=False
        try:
            body=self.client.get_object(Bucket=self.config.b2_bucket,Key=key,VersionId=info["version_id"])["Body"]
            remaining=info["size"]
            with destination.open("xb") as stream:
                created=True
                destination.chmod(0o600)
                while remaining:
                    if time.monotonic()>deadline:raise OffsiteError("OFFSITE_VERIFY_FAILED")
                    block=body.read(min(1024**2,remaining))
                    if not block:raise OffsiteError("OFFSITE_VERIFY_FAILED")
                    stream.write(block);remaining-=len(block)
                if body.read(1):raise OffsiteError("OFFSITE_VERIFY_FAILED")
            if file_hash(destination)!=info["sha256"]:raise OffsiteError("OFFSITE_VERIFY_FAILED")
            with tempfile.TemporaryDirectory(prefix="mascomatch-offsite-auth-") as workspace:verified_archive(destination,workspace)
            return destination,info
        except Exception as exc:
            if created:destination.unlink(missing_ok=True)
            raise classify(exc,"OFFSITE_VERIFY_FAILED") from None
        finally:
            if body:body.close()

    def objects(self):
        rows=[];markers={}
        try:
            for _ in range(100):
                response=self.client.list_object_versions(Bucket=self.config.b2_bucket,Prefix=PREFIX,MaxKeys=1000,**markers)
                for item in response.get("Versions",[]):
                    try:validate_key(item["Key"])
                    except OffsiteError:continue
                    rows.append(item)
                    if len(rows)>=MAX_OBJECTS:return rows,True
                if not response.get("IsTruncated"):return rows,False
                next_markers={"KeyMarker":response["NextKeyMarker"],"VersionIdMarker":response["NextVersionIdMarker"]}
                if next_markers==markers:raise OffsiteError("OFFSITE_VERIFY_FAILED")
                markers=next_markers
            return rows,True
        except Exception as exc:raise classify(exc,"OFFSITE_VERIFY_FAILED") from None

    def latest(self):
        rows,truncated=self.objects()
        if truncated:raise OffsiteError("OFFSITE_VERIFY_FAILED")
        current=[row for row in rows if row.get("IsLatest")]
        if not current:raise OffsiteError("OFFSITE_VERIFY_FAILED")
        return max(current,key=lambda row:row["Key"])


class State:
    def __init__(self,directory):
        self.directory=Path(directory).resolve();self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/".offsite-state.json";self.value=read_json(self.path)

    def save(self):
        from app.ops.backup_status import publish
        self.value["heartbeat"]=time.time()
        atomic_json(self.path,self.value);publish(self.value)

    def receipt(self,path):return path.with_name(path.name+".offsite.json")

    def success(self,path,info,config,duration):
        now=time.time()
        receipt={**info,"destination":config.destination,"confirmed_at":now}
        atomic_json(self.receipt(path),receipt)
        self.value.update(offsite_last_success=now,latest_capture=max(self.value.get("latest_capture",0),capture_time(path.name)),
            last_size_bytes=info["size"],last_duration_seconds=duration)
        self.save()

    def failed(self,error):
        if error.code.startswith("OFFSITE_"):self.value["offsite_last_attempt"]=time.time()
        self.value.update(error_code=error.code,failures_total=self.value.get("failures_total",0)+1,
                          consecutive_failures=self.value.get("consecutive_failures",0)+1)
        self.save()
        print(error.code,flush=True)


def reconcile(state,remote,limit=16):
    if state.value.get("destination")!=remote.config.destination:
        state.value.update(destination=remote.config.destination,offsite_last_success=0,latest_capture=0,last_deep_verify=0,
                           object_count=0,stored_bytes=0,inventory_at=0,inventory_truncated=False)
    paths=archive_paths(state.directory);pending=[]
    had_error=False
    for path in paths:
        receipt=read_json(state.receipt(path))
        if not valid_receipt(receipt,path,remote.config):pending.append(path)
    state.value.update(enabled=True,pending_count=len(pending));state.save()
    state.value["offsite_last_attempt"]=time.time();state.save()
    try:remote.check()
    except Exception as exc:state.failed(classify(exc,"OFFSITE_CONFIGURATION_ERROR"));return
    # Receipts are hints, not authority: inspect the pinned remote versions again.
    for path in paths:
        if path in pending:continue
        receipt=read_json(state.receipt(path))
        try:
            info=remote.verify(object_key(path.name),receipt.get("size"),receipt.get("sha256"),receipt.get("version_id"))
            state.value.update(latest_capture=max(state.value.get("latest_capture",0),capture_time(path.name)),
                               offsite_last_success=max(state.value.get("offsite_last_success",0),info["uploaded_at"]))
        except OffsiteError as exc:
            if exc.code=="OFFSITE_VERIFY_FAILED":pending.append(path)
            else:state.failed(exc);return
    pending.sort();state.value["pending_count"]=len(pending);state.save()
    # Newest first: catch-up of old archives must not hide the age of the newest recovery point.
    for path in reversed(pending[-limit:]):
        started=time.monotonic();state.value["offsite_last_attempt"]=time.time();state.save()
        try:
            info=remote.upload(path)
            state.success(path,info,remote.config,time.monotonic()-started)
            state.value["pending_count"]=max(0,state.value["pending_count"]-1);state.save()
        except Exception as exc:
            had_error=True;error=classify(exc,"OFFSITE_UPLOAD_FAILED");state.failed(error)
            if error.code in {"OFFSITE_AUTH_FAILED","OFFSITE_CONFIGURATION_ERROR","OFFSITE_RETENTION_ERROR"}:break
    try:
        rows,truncated=remote.objects()
        state.value.update(object_count=len(rows),stored_bytes=sum(r["Size"] for r in rows),inventory_at=time.time(),inventory_truncated=truncated)
        state.save()
    except Exception as exc:
        had_error=True;state.failed(classify(exc,"OFFSITE_VERIFY_FAILED"))
    if not had_error:
        state.value.update(error_code=None,consecutive_failures=0);state.save()


def deep_verify(state,remote,key=None,version=None):
    remote.check()
    if key is None:
        item=remote.latest();key=item["Key"];version=item["VersionId"]
    with tempfile.TemporaryDirectory(prefix=".b2-download-",dir=state.directory) as directory:
        _,info=remote.download(validate_key(key),directory,version)
    state.value["last_deep_verify"]=time.time();state.save()
    return info


def prune_local(state,keep,remote=None):
    for path in archive_paths(state.directory)[:-keep]:
        if remote:
            receipt=read_json(state.receipt(path))
            if not valid_receipt(receipt,path,remote.config):continue
            try:
                from app.ops.backup import file_hash
                remote.verify(object_key(path.name),path.stat().st_size,file_hash(path),receipt.get("version_id"))
            except Exception:continue
        path.unlink();state.receipt(path).unlink(missing_ok=True)


def valid_receipt(receipt,path,config):
    version=receipt.get("version_id");digest=receipt.get("sha256")
    return (receipt.get("destination")==config.destination and receipt.get("size")==path.stat().st_size
        and isinstance(digest,str) and bool(re.fullmatch("[a-f0-9]{64}",digest))
        and isinstance(version,str) and 1<=len(version)<=1024)
