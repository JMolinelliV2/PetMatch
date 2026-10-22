"""B2 tests use an in-memory S3 double: no credentials or external requests."""
import base64
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path
import tarfile
from types import SimpleNamespace
from uuid import uuid4

from botocore.exceptions import ClientError
from pydantic import SecretStr, ValidationError
import pytest
from app.core.config import settings
from app.ops import backup, backup_status, offsite

UTC=timezone.utc


@pytest.fixture(autouse=True)
def no_external_telemetry(monkeypatch):
    monkeypatch.setattr(backup_status,"publish",lambda value:None)


@pytest.fixture
def config(tmp_path,monkeypatch):
    monkeypatch.delenv("B2_KEY_ID",raising=False);monkeypatch.delenv("B2_APPLICATION_KEY",raising=False)
    identity=tmp_path/"key-id";identity.write_text("private-test-identity")
    secret=tmp_path/"application-key";secret.write_text("private-test-application-secret")
    return offsite.OffsiteConfig(_env_file=None,offsite_backup_enabled=True,
        b2_endpoint="https://s3.us-west-004.backblazeb2.com",b2_region="us-west-004",b2_bucket="mascomatch-drill-fixture",
        b2_key_id_file=str(identity),b2_application_key_file=str(secret))


@pytest.fixture
def archive(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"backup_key",SecretStr(base64.urlsafe_b64encode(b"x"*32).decode()))
    def create(stamp="20261022T120000Z"):
        path=tmp_path/(stamp+"-"+uuid4().hex+".mbak")
        photo=b"synthetic-private-photo";dump=b"synthetic-pg-dump"
        manifest={"format":1,"database_sha256":sha256(dump).hexdigest(),
                  "photos":[{"key":"fixture.jpg","mime":"image/jpeg","sha256":sha256(photo).hexdigest()}]}
        with path.open("wb") as output:
            writer=backup.EncryptWriter(output,b"x"*32)
            with tarfile.open(fileobj=writer,mode="w|") as tar:
                for name,payload in (("database.dump",dump),("photos/fixture.jpg",photo),("manifest.json",json.dumps(manifest).encode())):
                    info=tarfile.TarInfo(name);info.size=len(payload);tar.addfile(info,BytesIO(payload))
            writer.finish()
        return path
    return create


class S3:
    def __init__(self):
        self.data={};self.uploads=[];self.calls=[];self.failure=None;self.public=False;self.lock=True;self.days=30;self.hidden=False

    def head_bucket(self,**kwargs):
        self.calls.append("head_bucket")
        if self.failure:raise self.failure

    def get_bucket_acl(self,**kwargs):
        return {"Grants":[{"Grantee":{"Type":"Group" if self.public else "CanonicalUser"}}]}

    def get_object_lock_configuration(self,**kwargs):
        return {"ObjectLockConfiguration":{"ObjectLockEnabled":"Enabled" if self.lock else "Disabled",
                "Rule":{"DefaultRetention":{"Mode":"COMPLIANCE","Days":self.days}}}}

    def head_object(self,Key,**kwargs):
        if Key not in self.data or (self.hidden and not kwargs.get("VersionId")):
            raise ClientError({"Error":{"Code":"404"}},"HeadObject")
        return self.data[Key]["head"].copy()

    def get_object_retention(self,Key,**kwargs):return {"Retention":self.data[Key]["retention"]}

    def upload_file(self,filename,bucket,key,ExtraArgs,Config,Callback):
        self.calls.append("upload_file")
        if self.failure:raise self.failure
        assert Config.multipart_threshold==32*1024**2 and Config.max_concurrency==2
        payload=Path(filename).read_bytes();Callback(len(payload))
        self.uploads.append((key,payload,ExtraArgs))
        self.data[key]={"body":payload,"head":{"ContentLength":len(payload),"Metadata":ExtraArgs["Metadata"],
                       "VersionId":"version-fixture","LastModified":datetime.now(UTC)},
                       "retention":{"Mode":ExtraArgs.get("ObjectLockMode"),"RetainUntilDate":ExtraArgs.get("ObjectLockRetainUntilDate")}}

    def get_object(self,Key,**kwargs):return {"Body":BytesIO(self.data[Key]["body"])}

    def list_object_versions(self,Prefix,**kwargs):
        return {"Versions":[{"Key":key,"VersionId":item["head"]["VersionId"],"IsLatest":not self.hidden,
                            "Size":item["head"]["ContentLength"],"LastModified":item["head"]["LastModified"]}
                            for key,item in self.data.items() if key.startswith(Prefix)],"IsTruncated":False}


def test_disabled_requires_no_credentials(monkeypatch):
    monkeypatch.setenv("OFFSITE_BACKUP_ENABLED","false")
    assert not offsite.load_config().offsite_backup_enabled


def test_enabled_requires_config_and_hides_input(monkeypatch,capsys):
    monkeypatch.setenv("OFFSITE_BACKUP_ENABLED","true");monkeypatch.setenv("B2_ENDPOINT","https://private-secret@bad.invalid")
    with pytest.raises(offsite.OffsiteError,match="^OFFSITE_CONFIGURATION_ERROR$"):offsite.load_config()
    assert "private-secret" not in capsys.readouterr().out


@pytest.mark.parametrize("endpoint",["http://s3.us-west-004.backblazeb2.com","https://127.0.0.1", "https://s3.us-west-004.backblazeb2.com.evil.test",
    "https://private:secret@s3.us-west-004.backblazeb2.com", "https://s3.us-west-004.backblazeb2.com/path", "https://s3.us-west-004.backblazeb2.com?x=1",
    "https://s3.us-west-004.backblazeb2.com:8080", "https://s3.eu-central-003.backblazeb2.com"])
def test_endpoint_only_server_configured_b2(config,endpoint):
    values=config.model_dump(exclude={"b2_key_id","b2_application_key"});values["b2_endpoint"]=endpoint
    with pytest.raises(ValidationError):offsite.OffsiteConfig(_env_file=None,**values)


def test_credentials_only_dedicated_files_and_no_repr(config):
    assert "private-test" not in repr(config)
    values=config.model_dump(exclude={"b2_key_id","b2_application_key"})
    for change in ({"b2_application_key":"raw-secret"},{"b2_key_id_file":None},{"b2_bucket":settings.s3_bucket},{"b2_bucket":"../bad"}):
        with pytest.raises(ValidationError):offsite.OffsiteConfig(_env_file=None,**{**values,**change})


def test_client_never_uses_default_credentials(config,monkeypatch):
    calls=[]
    monkeypatch.setattr(offsite.boto3,"client",lambda *args,**kwargs:calls.append(kwargs))
    offsite.client_for(config);request=calls[0]
    assert request["verify"] is True and request["endpoint_url"]==config.b2_endpoint
    assert request["aws_access_key_id"]=="private-test-identity"
    assert request["config"].retries["total_max_attempts"]==3


@pytest.mark.parametrize("key",["../a.mbak","/backups/a.mbak","https://evil.test/a.mbak",r"backups\2026\10\22\a.mbak",
    "backups/2026/10/21/20261022T120000Z-"+"a"*32+".mbak","backups/2026/02/30/20260230T120000Z-"+"a"*32+".mbak",""])
def test_object_and_restore_keys_reject_traversal(key):
    with pytest.raises(offsite.OffsiteError):offsite.validate_key(key)


def test_upload_exact_encrypted_bytes_metadata_retention_and_no_overwrite(config,archive):
    path=archive();s3=S3();remote=offsite.Offsite(config,s3);remote.check()
    info=remote.upload(path);key=offsite.object_key(path.name)
    assert offsite.validate_key(key)==key and key.startswith("backups/2026/10/22/")
    assert s3.uploads[0][1]==path.read_bytes() and b"synthetic-private-photo" not in s3.uploads[0][1]
    assert info["sha256"]==backup.file_hash(path) and info["size"]==path.stat().st_size
    assert info["version_id"]=="version-fixture" and s3.uploads[0][2]["ObjectLockMode"]=="COMPLIANCE"
    assert remote.upload(path)==info and len(s3.uploads)==1
    s3.data[key]["head"]["Metadata"]={"mascomatch-sha256":"0"*64}
    with pytest.raises(offsite.OffsiteError,match="OFFSITE_VERIFY_FAILED"):remote.upload(path)
    assert len(s3.uploads)==1


def test_hidden_version_is_never_overwritten(config,archive):
    path=archive();s3=S3();remote=offsite.Offsite(config,s3);remote.upload(path);s3.hidden=True
    with pytest.raises(offsite.OffsiteError,match="OFFSITE_VERIFY_FAILED"):remote.upload(path)
    assert len(s3.uploads)==1


@pytest.mark.parametrize("problem",["size","metadata","missing","version","retention","retention-short"])
def test_remote_verification_fails_closed(config,archive,problem):
    path=archive();s3=S3();remote=offsite.Offsite(config,s3);info=remote.upload(path);item=s3.data[info["key"]]
    if problem=="size":item["head"]["ContentLength"]+=1
    elif problem=="metadata":item["head"]["Metadata"]={"mascomatch-sha256":"bad"}
    elif problem=="missing":s3.data.clear()
    elif problem=="version":item["head"]["VersionId"]=None
    elif problem=="retention":item["retention"]["Mode"]="GOVERNANCE"
    else:item["retention"]["RetainUntilDate"]=datetime.now(UTC)+timedelta(days=1)
    with pytest.raises(offsite.OffsiteError):remote.verify(info["key"],info["size"],info["sha256"])


@pytest.mark.parametrize("problem",["public","missing_lock","wrong_days","unexpected_lock"])
def test_bucket_must_match_private_compliance_config(config,problem):
    s3=S3();remote=offsite.Offsite(config,s3)
    if problem=="public":s3.public=True
    elif problem=="missing_lock":s3.lock=False
    elif problem=="wrong_days":s3.days=7
    else:config.b2_object_lock_enabled=False
    with pytest.raises(offsite.OffsiteError):remote.check()


def test_download_authenticates_before_restore_and_rejects_tampering(config,archive,tmp_path,monkeypatch):
    path=archive();s3=S3();remote=offsite.Offsite(config,s3);info=remote.upload(path)
    target=tmp_path/"download";target.mkdir()
    result,_=remote.download(info["key"],target,info["version_id"])
    assert result.read_bytes()==path.read_bytes();result.unlink()
    item=s3.data[info["key"]];data=bytearray(item["body"]);data[-17]^=1;item["body"]=bytes(data)
    with pytest.raises(offsite.OffsiteError):remote.download(info["key"],target)
    assert not list(target.iterdir())
    # Even a matching ciphertext SHA does not bypass AES-GCM authentication.
    item["head"]["Metadata"]={"mascomatch-sha256":sha256(item["body"]).hexdigest()}
    with pytest.raises(offsite.OffsiteError):remote.download(info["key"],target)
    assert not list(target.iterdir())


def test_download_does_not_remove_existing_destination(config,archive,tmp_path):
    path=archive();remote=offsite.Offsite(config,S3());info=remote.upload(path)
    with pytest.raises(offsite.OffsiteError):remote.download(info["key"],tmp_path)
    assert path.is_file()


def test_upload_rejects_invalid_local_archive_before_network(config,archive):
    path=archive();path.write_bytes(b"not-encrypted");s3=S3()
    with pytest.raises(offsite.OffsiteError,match="LOCAL_VERIFY_FAILED"):offsite.Offsite(config,s3).upload(path)
    assert not s3.calls and not s3.uploads


def test_retry_survives_restart_and_remote_is_authority(config,archive,tmp_path):
    path=archive();s3=S3();s3.failure=RuntimeError("private-test-application-secret")
    state=offsite.State(tmp_path);remote=offsite.Offsite(config,s3)
    offsite.reconcile(state,remote)
    assert path.is_file() and state.value["pending_count"]==1 and state.value["consecutive_failures"]==1
    s3.failure=None;state=offsite.State(tmp_path);offsite.reconcile(state,remote)
    assert state.value["pending_count"]==0 and state.value["object_count"]==1 and state.value["error_code"] is None
    # Lost receipt is recovered by HEAD; file is not uploaded again.
    state.receipt(path).unlink();offsite.reconcile(offsite.State(tmp_path),remote)
    assert len(s3.uploads)==1
    state.path.unlink();state=offsite.State(tmp_path);offsite.reconcile(state,remote)
    assert state.value["latest_capture"]==offsite.capture_time(path.name) and state.value["offsite_last_success"]>0
    # A receipt cannot conceal a remotely missing archive.
    s3.data.clear();offsite.reconcile(state,remote)
    assert len(s3.uploads)==2


def test_remote_auth_failure_is_sanitized_and_keeps_local(config,archive,tmp_path,capsys):
    path=archive();s3=S3();s3.failure=ClientError({"Error":{"Code":"AccessDenied","Message":"private-test-application-secret"}},"HeadBucket")
    state=offsite.State(tmp_path);offsite.reconcile(state,offsite.Offsite(config,s3))
    output=capsys.readouterr().out
    assert output.strip()=="OFFSITE_AUTH_FAILED" and "private-test" not in json.dumps(state.value)
    assert path.exists() and state.value["pending_count"]==1


def test_damaged_receipt_never_confirms_different_ciphertext(config,archive,tmp_path):
    path=archive();remote=offsite.Offsite(config,S3());state=offsite.State(tmp_path)
    offsite.reconcile(state,remote)
    receipt=offsite.read_json(state.receipt(path));receipt.pop("sha256");offsite.atomic_json(state.receipt(path),receipt)
    remote.client.data[offsite.object_key(path.name)]["head"]["Metadata"]={"mascomatch-sha256":"0"*64}
    offsite.reconcile(state,remote)
    assert state.value["pending_count"]==1 and state.value["error_code"]=="OFFSITE_VERIFY_FAILED" and path.exists()


def test_upload_failure_does_not_clear_failure_on_later_success(config,archive,tmp_path,monkeypatch):
    first=archive("20261021T120000Z");last=archive();s3=S3();remote=offsite.Offsite(config,s3)
    original=remote.upload
    def upload(path):
        if path==last:raise RuntimeError("do not log me")
        return original(path)
    monkeypatch.setattr(remote,"upload",upload)
    state=offsite.State(tmp_path);offsite.reconcile(state,remote)
    assert state.value["error_code"]=="OFFSITE_UPLOAD_FAILED" and state.value["pending_count"]==1
    assert state.value["latest_capture"]==offsite.capture_time(first.name)
    assert first.exists() and last.exists()


def test_newest_first_and_destination_change_cannot_reuse_old_freshness(config,archive,tmp_path):
    older=archive("20261021T120000Z");newer=archive();state=offsite.State(tmp_path);s3=S3();remote=offsite.Offsite(config,s3)
    offsite.reconcile(state,remote,limit=1)
    assert s3.uploads[0][0]==offsite.object_key(newer.name) and state.value["pending_count"]==1
    remote.config.b2_bucket="mascomatch-drill-other";s3.failure=RuntimeError("offline")
    offsite.reconcile(state,remote)
    assert state.value["latest_capture"]==0 and state.value["offsite_last_success"]==0


def test_retention_preserves_unconfirmed_and_failed_remote_versions(config,archive,tmp_path):
    older=archive("20261021T120000Z");newer=archive();state=offsite.State(tmp_path);s3=S3();remote=offsite.Offsite(config,s3)
    offsite.prune_local(state,1,remote);assert older.exists()
    offsite.reconcile(state,remote);key=offsite.object_key(older.name)
    saved=s3.data.pop(key);offsite.prune_local(state,1,remote);assert older.exists()
    s3.data[key]=saved;offsite.prune_local(state,1,remote)
    assert not older.exists() and newer.exists() and key in s3.data


def test_local_retention_without_b2_and_ignores_foreign_paths(archive,tmp_path):
    older=archive("20261021T120000Z");newer=archive();foreign=tmp_path/"do-not-delete.mbak";foreign.write_bytes(b"x")
    offsite.prune_local(offsite.State(tmp_path),1)
    assert not older.exists() and newer.exists() and foreign.exists()


def test_deep_verification_is_single_download_and_cleans_staging(config,archive,tmp_path):
    path=archive();remote=offsite.Offsite(config,S3());remote.upload(path);state=offsite.State(tmp_path)
    info=offsite.deep_verify(state,remote)
    assert info["key"]==offsite.object_key(path.name) and state.value["last_deep_verify"]>0
    assert not list(tmp_path.glob(".b2-download-*"))


def test_single_writer_lock(tmp_path):
    with offsite.exclusive(tmp_path):
        with pytest.raises(offsite.OffsiteError):
            with offsite.exclusive(tmp_path):pass


def test_busy_manual_command_does_not_overwrite_daemon_status(tmp_path,monkeypatch):
    state=offsite.State(tmp_path);state.value.update(enabled=False,local_last_success=123);state.save()
    before=state.path.read_bytes()
    monkeypatch.setenv("OFFSITE_BACKUP_ENABLED","false")
    monkeypatch.setattr("sys.argv",["backup","create",str(tmp_path)])
    with offsite.exclusive(tmp_path),pytest.raises(SystemExit) as result:backup.main()
    assert result.value.code==2 and state.path.read_bytes()==before


def test_status_strips_secrets_and_invalid_numbers():
    value=backup_status.public_status({"enabled":True,"pending_count":float("nan"),"last_size_bytes":-1,
        "b2_key_id":"private-test","application_key":"private-test","error_code":"private-test","local_last_success":123})
    assert "private-test" not in json.dumps(value) and value["pending_count"]==value["last_size_bytes"]==0
    metrics=backup_status.metric_values(value)
    assert metrics["mascomatch_backup_last_success_unixtime"]==123
    assert metrics["mascomatch_offsite_backup_enabled"]==1


def test_backup_cycle_preserves_local_when_b2_is_down(config,archive,tmp_path,monkeypatch):
    path=archive();s3=S3();s3.failure=RuntimeError("offline")
    monkeypatch.setattr(backup,"create_backup",lambda directory:path)
    monkeypatch.setattr(offsite,"client_for",lambda config:s3)
    state=offsite.State(tmp_path);backup.cycle(state,config)
    assert state.value["local_last_success"]>0 and path.exists()
    assert state.value["error_code"]=="OFFSITE_VERIFY_FAILED" and state.value["pending_count"]==1


def test_local_failure_still_retries_previously_created_backup(config,archive,tmp_path,monkeypatch):
    path=archive();s3=S3()
    def failed(directory):raise offsite.OffsiteError("LOCAL_VERIFY_FAILED")
    monkeypatch.setattr(backup,"create_backup",failed);monkeypatch.setattr(offsite,"client_for",lambda config:s3)
    state=offsite.State(tmp_path);backup.cycle(state,config)
    assert state.value["local_error_code"]=="LOCAL_VERIFY_FAILED" and state.value["pending_count"]==0 and path.exists()


def test_deployment_copy_never_waits_for_b2_or_prunes(config,archive,tmp_path,monkeypatch):
    older=archive("20261021T120000Z");path=archive()
    monkeypatch.setattr(backup,"create_backup",lambda directory:path)
    def forbidden(*args):raise AssertionError("Deployment local backup must not initialize B2")
    monkeypatch.setattr(offsite,"client_for",forbidden);monkeypatch.setenv("BACKUP_LOCAL_KEEP","1")
    state=offsite.State(tmp_path);state.value["error_code"]="OFFSITE_AUTH_FAILED"
    backup.cycle(state,config,local_only=True)
    assert state.value["local_last_success"]>0 and state.value["error_code"]=="OFFSITE_AUTH_FAILED" and older.exists()


def test_inventory_pagination_is_bounded(config):
    class Paginated(S3):
        def list_object_versions(self,**kwargs):return {"Versions":[],"IsTruncated":True,"NextKeyMarker":"same","NextVersionIdMarker":"same"}
    with pytest.raises(offsite.OffsiteError):offsite.Offsite(config,Paginated()).objects()


def test_operator_placeholder_upgrade_preserves_keys(tmp_path):
    import importlib.util
    script=next((p/"tools/production_init.py" for p in Path(__file__).resolve().parents if (p/"tools/production_init.py").is_file()),None)
    if script is None:pytest.skip("Operator tooling requires repository root")
    spec=importlib.util.spec_from_file_location("b2_init",script);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.initialize(tmp_path);secret=tmp_path/".secrets/b2_application_key";secret.chmod(0o600);secret.write_text("keep-existing")
    (tmp_path/".secrets/b2_key_id").unlink();module.prepare_b2_secrets(tmp_path)
    assert secret.read_text()=="keep-existing" and (tmp_path/".secrets/b2_key_id").read_text().strip()==""
    assert "keep-existing" not in (tmp_path/".env.production").read_text()


def fake_snapshot(monkeypatch):
    class Result:
        def fetchone(self):return ("fixture-snapshot",)
        def fetchall(self):return []
    class Connection:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def execute(self,*args):return Result()
    monkeypatch.setattr(backup.psycopg,"connect",lambda *args,**kwargs:Connection())
    monkeypatch.setattr(backup,"_client",lambda *args:object())
    def dump(args,env):Path(next(item.split("=",1)[1] for item in args if item.startswith("--file="))).write_bytes(b"fixture-dump")
    monkeypatch.setattr(backup,"run_pg",dump)


def test_local_create_survives_redis_outage_after_verification(archive,tmp_path,monkeypatch):
    archive();fake_snapshot(monkeypatch)
    def offline(*args,**kwargs):raise RuntimeError("redis unavailable")
    monkeypatch.setattr(backup.Redis,"from_url",offline)
    path=backup.create_backup(tmp_path)
    with tempfile_directory() as directory:
        assert backup.verified_archive(path,directory)[1]["photos"]==[]


def tempfile_directory():
    import tempfile
    return tempfile.TemporaryDirectory()


def test_local_verification_failure_never_marks_success(archive,tmp_path,monkeypatch):
    archive();fake_snapshot(monkeypatch);calls=[]
    monkeypatch.setattr(backup.Redis,"from_url",lambda *args,**kwargs:calls.append("redis"))
    def invalid(*args):raise ValueError("invalid ciphertext")
    monkeypatch.setattr(backup,"verified_archive",invalid)
    with pytest.raises(offsite.OffsiteError,match="LOCAL_VERIFY_FAILED"):backup.create_backup(tmp_path)
    assert calls==[] and not list(tmp_path.glob("*.partial"))


def test_compose_credentials_are_only_mounted_to_backup():
    import yaml
    root=next((p for p in Path(__file__).resolve().parents if (p/"compose.production.yml").is_file()),None)
    if root is None:pytest.skip("Compose source requires repository root")
    compose=yaml.safe_load((root/"compose.production.yml").read_text())
    for name,service in compose["services"].items():
        sensitive=[key for key in service.get("environment",{}) if key.startswith("B2_") or key.startswith("OFFSITE_")]
        mounts=[item for item in service.get("secrets",[]) if isinstance(item,str) and item.startswith("b2_")]
        assert (not sensitive and not mounts) or name=="backup"
    env=compose["services"]["backup"]["environment"]
    assert env["B2_KEY_ID_FILE"]=="/run/secrets/b2_key_id" and env["B2_APPLICATION_KEY_FILE"]=="/run/secrets/b2_application_key"


def test_admin_status_private_and_metrics_never_connect_to_b2(client,auth_headers,db_factory,monkeypatch):
    from sqlalchemy import select
    from app.models import AdminAccess,User
    class Redis:
        @classmethod
        def from_url(cls,*args,**kwargs):return cls()
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def hgetall(self,*args):return {}
        def get(self,name):
            if name==backup_status.STATUS_KEY:return json.dumps({"enabled":True,"local_last_success":123,"error_code":"OFFSITE_AUTH_FAILED",
                "b2_key_id":"private-test-identity","application_key":"private-test-application-secret"}).encode()
            return None
    monkeypatch.setattr(backup_status,"Redis",Redis)
    monkeypatch.setattr("app.routers.operations.Redis",Redis)
    monkeypatch.setattr("app.routers.operations.SessionLocal",db_factory)
    monkeypatch.setattr("app.routers.admin_operations.chart_data",lambda *args:{})  # Charts require PostgreSQL; covered by the production drill.
    monkeypatch.setattr("app.routers.operations.readiness",lambda:{"database":True,"queue":True,"photos":True})
    def forbidden(*args,**kwargs):raise AssertionError("API must not initialize any B2 client")
    monkeypatch.setattr(offsite,"client_for",forbidden)
    path="/api/v1/admin/operations"
    assert client.get(path).status_code==401
    assert client.get(path,headers=auth_headers).status_code==403
    with db_factory() as db:
        account=db.scalar(select(User));account.role="ADMIN";db.add(AdminAccess(id=1,owner=account));db.commit()
    response=client.get(path,headers=auth_headers)
    assert response.status_code==200 and response.json()["backups"]["error_code"]=="OFFSITE_AUTH_FAILED"
    assert "private-test" not in response.text and response.headers["cache-control"]=="no-store"
    monkeypatch.setattr(settings,"metrics_token",SecretStr("test-monitoring-token"))
    metrics=client.get("/internal/metrics",headers={"Authorization":"Bearer test-monitoring-token"})
    assert metrics.status_code==200 and "private-test" not in metrics.text
    assert "mascomatch_offsite_backup_enabled 1" in metrics.text and "mascomatch_ready 1" in metrics.text
    assert client.get("/health/ready").status_code==200
