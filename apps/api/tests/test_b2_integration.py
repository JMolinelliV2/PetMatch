"""Explicit real B2 drill. Remote Object Locked synthetic archive is deliberately retained."""
import json
import os
from hashlib import sha256
from pathlib import Path
import tempfile
from uuid import uuid4
import psycopg
from psycopg import sql
import pytest
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.core.image_storage import _client
from app.ops.backup import connection_url, create_backup, restore_backup
from app.ops.offsite import Offsite, load_config


@pytest.mark.skipif(os.getenv("RUN_B2_INTEGRATION")!="1",reason="Opt-in real B2 drill requires a dedicated test bucket and disposable production preview")
def test_real_b2_encrypted_recovery():
    assert os.getenv("DISPOSABLE_STACK")=="mascomatch-prod-smoke"
    assert make_url(settings.database_url).host=="db" and settings.s3_endpoint=="http://photos:8333"
    config=load_config()
    assert config.b2_bucket.startswith("mascomatch-drill-")
    assert config.b2_object_lock_enabled and config.b2_object_lock_days==30
    remote=Offsite(config);remote.check()
    client=_client(settings.s3_endpoint);original_bucket=settings.s3_bucket
    database="mascomatch_b2_drill_"+uuid4().hex
    bucket="mascomatch-b2-drill-"+uuid4().hex[:18]
    target=make_url(settings.database_url).set(database=database).render_as_string(hide_password=False)
    control=psycopg.connect(connection_url(settings.database_url),autocommit=True)
    database_created=False;bucket_created=False
    try:
        with tempfile.TemporaryDirectory(prefix="b2-drill-",dir="/backups") as directory:
            path=create_backup(directory);info=remote.upload(path)
            # Print immediately: if a later assertion fails the owner can still locate the protected archive.
            print("B2_DRILL_ARCHIVE_RETAINED",json.dumps({k:info[k] for k in ("key","version_id","retained_until","size")}))
            assert info["retained_until"]
            assert remote.upload(path)["version_id"]==info["version_id"]
            download=Path(directory)/"download";download.mkdir()
            recovered,_=remote.download(info["key"],download,info["version_id"])
            assert sha256(recovered.read_bytes()).digest()==sha256(path.read_bytes()).digest()
            control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)));database_created=True
            client.create_bucket(Bucket=bucket);bucket_created=True
            settings.s3_bucket=bucket
            restore_backup(recovered,target)
            with psycopg.connect(connection_url(target)) as db:
                assert db.execute("SELECT count(*) FROM lost_cases").fetchone()[0]>=1
                photos=db.execute("SELECT storage_key FROM photos").fetchall();assert photos
            for (key,) in photos:
                source=client.get_object(Bucket=original_bucket,Key=key)["Body"]
                restored=client.get_object(Bucket=bucket,Key=key)["Body"]
                try:assert sha256(source.read()).digest()==sha256(restored.read()).digest()
                finally:source.close();restored.close()
            with pytest.raises(ValueError,match="no application tables"):restore_backup(recovered,target)
            print("B2_RESTORE_DRILL_PASSED: authenticated archive, database rows, photo hashes, nonempty-target protection")
    finally:
        settings.s3_bucket=original_bucket
        if bucket_created:
            for row in client.list_objects_v2(Bucket=bucket).get("Contents",[]):client.delete_object(Bucket=bucket,Key=row["Key"])
            client.delete_bucket(Bucket=bucket)
        if database_created:
            assert database.startswith("mascomatch_b2_drill_")
            control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database)))
        control.close()
