"""Idempotent low-priority extraction for the current prompts/preprocessing."""
import json
from sqlalchemy import select,func
from app.analysis.service import _schedule,schedule_text,image_snapshot
from app.core.config import settings
from app.db.session import SessionLocal
from app.models import AnalysisJob,LostCase,Observation,Photo
from app.species import owner_is_supported


def backfill(factory=SessionLocal):
    if not settings.ai_enabled:
        return {"enabled":False,"created":0}
    created=0
    for model,kind in ((LostCase,"lost_case"),(Observation,"observation"),(Photo,"photo")):
        last=None
        while True:
            with factory() as db:
                query=select(model).order_by(model.id).limit(100)
                if last:
                    query=query.where(model.id>last)
                rows=list(db.scalars(query))
                if not rows:
                    break
                before=db.scalar(select(func.count()).select_from(AnalysisJob))
                for row in rows:
                    if kind=="photo":
                        if not owner_is_supported(db,row.owner_type,row.owner_id):
                            continue
                        snapshot=image_snapshot(db,row)
                        if snapshot["species"] is not None:
                            _schedule(db,row.owner_type,row.owner_id,"image",snapshot,row.id,priority=10)
                    else:
                        schedule_text(db,kind,row.id,priority=10)
                db.flush()
                created+=db.scalar(select(func.count()).select_from(AnalysisJob))-before
                last=rows[-1].id
                db.commit()
    return {"enabled":True,"created":created}


if __name__=="__main__":
    print(json.dumps(backfill()))
