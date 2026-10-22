"""Controlled, repeatable production rollout and feature-flag rollback. No secrets in output."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]


def read_config(path):
    return dict(line.split("=",1) for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("#") and "=" in line)


def set_flags(path,values):
    allowed={"AI_ENABLED","EMBEDDINGS_ENABLED","PET_REID_ENABLED"}
    if not set(values)<=allowed or any(value not in {"true","false"} for value in values.values()):
        raise ValueError("Only known boolean rollout flags may be changed")
    lines=path.read_text(encoding="utf-8").splitlines()
    seen=set()
    for index,line in enumerate(lines):
        key=line.split("=",1)[0]
        if key in values:
            lines[index]=key+"="+values[key];seen.add(key)
    lines.extend(key+"="+value for key,value in values.items() if key not in seen)
    descriptor,name=tempfile.mkstemp(prefix=path.name+".",suffix=".pending",dir=path.parent)
    temporary=Path(name)
    try:
        with os.fdopen(descriptor,"w",encoding="utf-8") as stream:
            stream.write("\n".join(lines)+"\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=["deploy","fallback","pause-ai","resume-ai","check","smoke"])
    parser.add_argument("--env-file",type=Path,default=ROOT/".env.production")
    parser.add_argument("--project",default="mascomatch")
    parser.add_argument("--with-ai",action="store_true")
    parser.add_argument("--accept-gemma-terms",action="store_true")
    args=parser.parse_args()
    path=args.env_file.resolve()
    if not path.is_file():
        parser.error("Initialize private configuration with tools/production_init.py first")
    if args.action=="fallback" and read_config(path).get("OPENCLIP_ENABLED","true")!="true":
        parser.error("OpenCLIP must be enabled before selecting its fallback; no service was stopped")
    base=["docker","compose","-p",args.project,"--env-file",str(path),"-f",str(ROOT/"compose.production.yml"),
          "--profile","ai-local","--profile","monitoring"]
    def compose(*arguments,capture=False):
        result=subprocess.run([*base,*arguments],cwd=ROOT,check=True,text=True,
                              stdout=subprocess.PIPE if capture else None)
        return result.stdout.strip() if capture else None
    compose("config","--quiet")
    if args.action=="check":
        compose("exec","-T","api","python","-m","app.ops.release_check")
        return
    if args.action=="smoke":
        compose("run","--rm","--no-deps","ai-smoke")
        return
    if args.action=="deploy":
        configuration=read_config(path)
        semantic=args.with_ai or configuration.get("AI_ENABLED")=="true"
        visual=args.with_ai or configuration.get("EMBEDDINGS_ENABLED")=="true"
        compose("build")
        compose("stop","api","worker","worker-ai","backup")
        compose("up","-d","--wait","db","redis","photos")
        compose("run","--rm","--no-deps","photos-init")
        has_schema=compose("exec","-T","db","psql","-U","mascomatch_owner","-d","mascomatch","-Atc",
                           "SELECT to_regclass('public.users') IS NOT NULL",capture=True)=="t"
        if has_schema:
            compose("run","--rm","--no-deps","backup","python","-m","app.ops.backup","create","/backups")
        compose("run","--rm","--no-deps","migrate")
        if not has_schema:
            compose("run","--rm","--no-deps","backup","python","-m","app.ops.backup","create","/backups")
        if semantic or visual:
            compose("build","model-setup","ai-smoke")
            compose("run","--rm","--no-deps","model-setup")
        if semantic:
            gemma=["run","--rm","--no-deps","model-setup","python","-m","app.analysis.gemma_setup"]
            compose(*gemma, "--accept-gemma-terms" if args.accept_gemma_terms else "--check")
        if args.with_ai:
            set_flags(path,{"AI_ENABLED":"true","EMBEDDINGS_ENABLED":"true"})
        compose("run","--rm","--no-deps","api","python","-m","app.analysis.requeue","--workers-stopped")
    else:
        compose("stop","api","worker","worker-ai")
        if args.action=="fallback":
            set_flags(path,{"PET_REID_ENABLED":"false","EMBEDDINGS_ENABLED":"true"})
        elif args.action=="pause-ai":
            set_flags(path,{"AI_ENABLED":"false"})
        elif args.action=="resume-ai":
            set_flags(path,{"AI_ENABLED":"true","EMBEDDINGS_ENABLED":"true","PET_REID_ENABLED":"true"})
        compose("run","--rm","--no-deps","api","python","-m","app.analysis.requeue","--workers-stopped")
    configuration=read_config(path)
    if configuration.get("EMBEDDINGS_ENABLED")=="true":
        compose("run","--rm","--no-deps","worker","python","-m","app.embeddings.backfill","--retry-failed")
    if configuration.get("AI_ENABLED")=="true":
        compose("run","--rm","--no-deps","worker-ai","python","-m","app.analysis.backfill")
    services=["api","web","caddy","backup","prometheus"]
    if configuration.get("AI_ENABLED")=="true":
        services.extend(["ollama","worker-ai"])
    if configuration.get("EMBEDDINGS_ENABLED")=="true":
        services.append("worker")
    compose("up","-d","--wait","--wait-timeout","360",*services)
    compose("exec","-T","api","python","-m","app.ops.release_check")


if __name__=="__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        print("Deployment stopped at a failed step. Fix its reported error and repeat the command; data and model volumes are preserved.",file=sys.stderr)
        raise SystemExit(exc.returncode)
