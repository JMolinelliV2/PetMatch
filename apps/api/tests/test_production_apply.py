import importlib.util
from pathlib import Path
from types import SimpleNamespace
import pytest


def tooling():
    path=next((p/"tools/production_apply.py" for p in Path(__file__).resolve().parents if (p/"tools/production_apply.py").is_file()),None)
    if path is None:pytest.skip("Run operator tests from the repository root")
    spec=importlib.util.spec_from_file_location("production_apply",path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_flags_are_atomic_and_preserve_unrelated_values(tmp_path):
    tool=tooling();path=tmp_path/"private.env"
    path.write_text("AI_ENABLED=true\nPRIVATE_VALUE=kept\n")
    tool.set_flags(path,{"AI_ENABLED":"false","PET_REID_ENABLED":"false"})
    assert tool.read_config(path)=={"AI_ENABLED":"false","PET_REID_ENABLED":"false","PRIVATE_VALUE":"kept"}
    with pytest.raises(ValueError):tool.set_flags(path,{"SMTP_PASSWORD":"unexpected"})
    with pytest.raises(ValueError):tool.set_flags(path,{"AI_ENABLED":"true\nINJECTION=yes"})


@pytest.mark.parametrize("action,expected",[("fallback",{"PET_REID_ENABLED":"false","AI_ENABLED":"true"}),
    ("pause-ai",{"AI_ENABLED":"false","PET_REID_ENABLED":"true"}),
    ("resume-ai",{"AI_ENABLED":"true","PET_REID_ENABLED":"true"})])
def test_rollout_stops_workers_before_requeue_and_preserves_data(tmp_path,monkeypatch,action,expected):
    tool=tooling();path=tmp_path/"private.env"
    path.write_text("AI_ENABLED=true\nPET_REID_ENABLED=true\nEMBEDDINGS_ENABLED=true\n")
    calls=[]
    monkeypatch.setattr(tool.sys,"argv",["production_apply.py",action,"--env-file",str(path)])
    monkeypatch.setattr(tool.subprocess,"run",lambda cmd,**kwargs:(calls.append(cmd) or SimpleNamespace(stdout="")))
    tool.main()
    cfg=tool.read_config(path)
    assert all(cfg[k]==v for k,v in expected.items())
    stop=next(i for i,c in enumerate(calls) if "stop" in c)
    reclaim=next(i for i,c in enumerate(calls) if "app.analysis.requeue" in c)
    up=next(i for i,c in enumerate(calls) if "up" in c)
    assert stop<reclaim<up
    assert not any("down" in c or "--volumes" in c for c in calls)
    assert "app.ops.release_check" in calls[-1]


def test_deploy_backs_up_existing_schema_before_migration_and_keeps_pause(tmp_path,monkeypatch):
    tool=tooling();path=tmp_path/"private.env"
    path.write_text("AI_ENABLED=false\nPET_REID_ENABLED=false\nEMBEDDINGS_ENABLED=true\n")
    calls=[]
    monkeypatch.setattr(tool.sys,"argv",["production_apply.py","deploy","--env-file",str(path)])
    monkeypatch.setattr(tool.subprocess,"run",lambda cmd,**kwargs:(calls.append(cmd) or SimpleNamespace(stdout="t\n" if "psql" in cmd else "")))
    tool.main()
    backup=next(i for i,c in enumerate(calls) if "app.ops.backup" in c)
    assert "--local-only" in calls[backup]  # A B2 outage cannot block bringing API/web back online.
    migrate=next(i for i,c in enumerate(calls) if c[-1]=="migrate")
    assert backup<migrate
    assert tool.read_config(path)["AI_ENABLED"]=="false"
    assert not any("app.analysis.gemma_setup" in c for c in calls)


def test_fallback_rejects_disabled_openclip_before_stopping_services(tmp_path,monkeypatch):
    tool=tooling();path=tmp_path/"private.env"
    path.write_text("AI_ENABLED=true\nOPENCLIP_ENABLED=false\n")
    calls=[]
    monkeypatch.setattr(tool.sys,"argv",["production_apply.py","fallback","--env-file",str(path)])
    monkeypatch.setattr(tool.subprocess,"run",lambda cmd,**kwargs:calls.append(cmd))
    with pytest.raises(SystemExit):tool.main()
    assert calls==[]
