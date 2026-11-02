"""Opt-in encrypted recovery against an explicitly disposable production stack."""
import os
from pathlib import Path
from uuid import uuid4
from hashlib import sha256
import pytest
import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url
from app.core.config import settings
from app.core.image_storage import _client
from app.ops.backup import create_backup, restore_backup, connection_url


@pytest.mark.skipif(os.getenv("RUN_PRODUCTION_INTEGRATION")!="1",reason="Requires the disposable production preview and its operator credentials")
@pytest.mark.parametrize("offsite_copy",[False,True],ids=["local","simulated-offsite"])
def test_encrypted_database_and_photo_recovery(offsite_copy,tmp_path):
    assert os.getenv("DISPOSABLE_STACK") == "mascomatch-prod-smoke"
    original_bucket=settings.s3_bucket
    name="mascomatch_restore_check_"+uuid4().hex
    bucket="mascomatch-restore-check-"+uuid4().hex[:18]
    target_url=make_url(settings.database_url).set(database=name).render_as_string(hide_password=False)
    client=_client(settings.s3_endpoint)
    control=psycopg.connect(connection_url(settings.database_url),autocommit=True)
    created=False
    try:
        control.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        created=True
        client.create_bucket(Bucket=bucket)
        with psycopg.connect(connection_url(settings.database_url)) as source:
            assert source.execute("SELECT version_num FROM alembic_version").fetchone()[0]=="0031_donations"
            assert source.execute("SELECT count(*) FROM product_events WHERE name='account_created' AND visitor_id IS NOT NULL").fetchone()[0]>=1
            assert source.execute("SELECT count(*) FROM recovery_outcomes WHERE reason='OTHER'").fetchone()[0]>=1
            assert source.execute("SELECT count(*) FROM product_events WHERE NOT aggregated").fetchone()[0]==0
        backup=create_backup("/backups")
        if offsite_copy:
            # Real PostgreSQL/SeaweedFS recovery through a simulated B2 copy; no network/cloud credentials.
            from app.ops.offsite import Offsite,OffsiteConfig
            from test_offsite_backup import S3
            identity=tmp_path/"b2-id";identity.write_text("synthetic-key-id")
            secret=tmp_path/"b2-key";secret.write_text("synthetic-application-key")
            config=OffsiteConfig(_env_file=None,offsite_backup_enabled=True,
                b2_endpoint="https://s3.us-west-004.backblazeb2.com",b2_region="us-west-004",b2_bucket="mascomatch-drill-simulated",
                b2_key_id_file=str(identity),b2_application_key_file=str(secret))
            remote=Offsite(config,S3());remote.check();info=remote.upload(backup)
            backup,_=remote.download(info["key"],tmp_path,info["version_id"])
        settings.s3_bucket=bucket
        restore_backup(backup,target_url)
        with psycopg.connect(connection_url(target_url)) as restored:
            cases=restored.execute("SELECT count(*) FROM lost_cases").fetchone()[0]
            photos=restored.execute("SELECT storage_key FROM photos").fetchall()
            assert cases>=1 and photos
            assert restored.execute("SELECT count(*) FROM analytics_tracking").fetchone()[0]==1
            assert restored.execute("SELECT count(*) FROM product_daily").fetchone()[0]>=1
            for (key,) in photos:
                source=client.get_object(Bucket=original_bucket,Key=key)["Body"]
                recovery=client.get_object(Bucket=bucket,Key=key)["Body"]
                try:
                    assert sha256(source.read()).digest()==sha256(recovery.read()).digest()
                finally:
                    source.close();recovery.close()
        with pytest.raises(ValueError,match="no application tables"):
            restore_backup(backup,target_url)
        print("Simulated off-site copy" if offsite_copy else "Local copy",
              "restored: PostgreSQL records and photo hashes verified; populated target rejected")
    finally:
        settings.s3_bucket=original_bucket
        for item in client.list_objects_v2(Bucket=bucket).get("Contents",[]):
            client.delete_object(Bucket=bucket,Key=item["Key"])
        client.delete_bucket(Bucket=bucket)
        if created:
            assert name.startswith("mascomatch_restore_check_")
            control.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
        control.close()
