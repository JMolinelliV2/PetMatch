"""Opt-in disposable production BFF, SMTP/TLS and encrypted recovery checks. No public ports."""
import argparse
import os
from pathlib import Path
import subprocess
from production_init import initialize,prepare_b2_secrets
from production_apply import set_flags,read_config

ROOT=Path(__file__).resolve().parents[1]
PROJECT="mascomatch-prod-smoke"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep",action="store_true",help="Keep the disposable stack for inspection")
    parser.add_argument("--with-b2",action="store_true",help="Explicit real B2 drill; leaves an Object Locked test archive")
    parser.add_argument("--b2-env-file",type=Path,help="Non-secret B2 test bucket configuration; credentials remain in preview .secrets")
    args=parser.parse_args()
    directory=ROOT/"real-data"/"production-preview"
    if not (directory/".env.production").exists():initialize(directory)
    prepare_b2_secrets(directory)
    set_flags(directory/".env.production",{"AI_ENABLED":"false","EMBEDDINGS_ENABLED":"false"})
    private=directory/".secrets"
    password=private/"smtp_password"
    password.chmod(0o600);password.write_text("disposable-mailpit-only\n");password.chmod(0o444)
    env={**os.environ,"SECRETS_DIR":str(private.resolve()),"OFFSITE_BACKUP_ENABLED":"false"}
    b2={}
    if args.with_b2:
        if not args.b2_env_file or not args.b2_env_file.is_file():parser.error("--with-b2 requires --b2-env-file")
        b2=read_config(args.b2_env_file)
        allowed={"B2_ENDPOINT","B2_REGION","B2_BUCKET","B2_OBJECT_LOCK_ENABLED","B2_OBJECT_LOCK_DAYS"}
        if not set(b2)<=allowed or not b2.get("B2_BUCKET","").startswith("mascomatch-drill-"):
            parser.error("Only dedicated mascomatch-drill-* bucket configuration is accepted; no credentials in the env file")
        if b2.get("B2_OBJECT_LOCK_ENABLED","true")!="true" or b2.get("B2_OBJECT_LOCK_DAYS","30")!="30":
            parser.error("The drill requires COMPLIANCE Object Lock for 30 days")
        for name in ("b2_key_id","b2_application_key"):
            if not (private/name).read_text().strip():parser.error("Place dedicated test bucket credentials in the preview secret files first")
    base=["docker","compose","-p",PROJECT,"--env-file",str(directory/".env.production"),
          "-f",str(ROOT/"compose.production.yml"),"-f",str(ROOT/"compose.smoke.yml")]
    def compose(*args):subprocess.run([*base,*args],env=env,cwd=ROOT,check=True)
    try:
        compose("build","api","web","backup","recovery-check","migrate","photos-init","db")
        subprocess.run(["docker","run","--rm","--network","none","--user","0","-v",str(private)+":/fixture",
                "-v",str(ROOT/"tools/smoke_certificates.py")+":/tmp/cert.py:ro",PROJECT+"-api","python","/tmp/cert.py","/fixture"],check=True)
        compose("up","-d","--force-recreate","--wait","mailpit")
        compose("up","-d","--wait","--wait-timeout","180","db","redis","photos","mailpit")
        compose("run","--rm","--no-deps","photos-init")
        compose("run","--rm","--no-deps","migrate")
        compose("up","-d","--wait","--wait-timeout","180","api","web")
        compose("exec","-T","-e","DISPOSABLE_STACK="+PROJECT,"web","node","/tmp/production_smoke.mjs")
        compose("run","--rm","--no-deps","recovery-check")
        if args.with_b2:
            # Only the backup service receives B2 credentials, including in the disposable drill.
            subprocess.run([*base,"-f",str(ROOT/"compose.b2-smoke.yml"),"run","--rm","--no-deps","backup"],
                           env={**env,**b2,"OFFSITE_BACKUP_ENABLED":"true"},cwd=ROOT,check=True)
        print("Production preview passed: verified signup, publication, private photo, CSRF, logout, encrypted recovery.")
    finally:
        if not args.keep:
            # Fixed test-only project; normal development/production volumes are never addressed.
            compose("down","--volumes","--remove-orphans")


if __name__=="__main__":main()
