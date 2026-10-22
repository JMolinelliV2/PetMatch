"""Opt-in disposable production BFF, SMTP/TLS and encrypted recovery checks. No public ports."""
import argparse
import os
from pathlib import Path
import subprocess
from production_init import initialize
from production_apply import set_flags

ROOT=Path(__file__).resolve().parents[1]
PROJECT="mascomatch-prod-smoke"


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--keep",action="store_true",help="Keep the disposable stack for inspection")
    args=parser.parse_args()
    directory=ROOT/"real-data"/"production-preview"
    if not (directory/".env.production").exists():initialize(directory)
    set_flags(directory/".env.production",{"AI_ENABLED":"false","EMBEDDINGS_ENABLED":"false"})
    private=directory/".secrets"
    password=private/"smtp_password"
    password.chmod(0o600);password.write_text("disposable-mailpit-only\n");password.chmod(0o444)
    env={**os.environ,"SECRETS_DIR":str(private.resolve())}
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
        print("Production preview passed: verified signup, publication, private photo, CSRF, logout, encrypted recovery.")
    finally:
        if not args.keep:
            # Fixed test-only project; normal development/production volumes are never addressed.
            compose("down","--volumes","--remove-orphans")


if __name__=="__main__":main()
