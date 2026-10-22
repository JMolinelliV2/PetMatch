"""Export explicit owner labels privately. Predictions never become ground truth."""
import argparse
import json
import os
from pathlib import Path
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import Pet,Photo,LostCase,Match,MatchFeedbackEvent
from app.matching.linked import aware


def collect_labels(db):
    pairs={}
    def add(left,right,label,source):
        if left.id==right.id:
            return
        key=tuple(sorted((str(left.id),str(right.id))))
        previous=pairs.get(key)
        if previous and previous["label"]!=label:
            pairs[key]={"label":"CONFLICT"}
        elif not previous:
            pairs[key]={"photos":list(key),"label":label,"source":source}
    photos=list(db.scalars(select(Photo)))
    pets=[pet for pet in db.scalars(select(Pet)) if pet.evaluation_consent_version is None or pet.evaluation_consent]
    cases={case.id:case for case in db.scalars(select(LostCase))}
    pet_photos={pet.id:[photo for photo in photos if (photo.owner_type=="pet" and photo.owner_id==pet.id)
        or (photo.owner_type=="lost_case" and photo.owner_id in cases and cases[photo.owner_id].pet_id==pet.id)] for pet in pets}
    for group in pet_photos.values():
        for index,left in enumerate(group):
            for right in group[index+1:]:
                add(left,right,"SAME_IDENTITY","owner_assigned_photos")
    latest={}
    for event in db.scalars(select(MatchFeedbackEvent).order_by(MatchFeedbackEvent.created_at,MatchFeedbackEvent.id)):
        latest[event.match_id]=event
    for match_id,event in latest.items():
        if event.legacy or event.status not in {"RESOLVED","FALSE_MATCH"}:
            continue
        match=db.get(Match,match_id)
        case=cases.get(match.lost_case_id) if match else None
        pet=db.get(Pet,case.pet_id) if case else None
        if not pet or pet.id not in pet_photos or event.actor_id!=pet.owner_id:
            continue
        references=[p for p in pet_photos[pet.id] if aware(p.created_at)<=aware(event.created_at)]
        observed=[p for p in photos if p.owner_type=="observation" and p.owner_id==match.observation_id and aware(p.created_at)<=aware(event.created_at)]
        for left in references:
            for right in observed:
                add(left,right,"SAME_IDENTITY" if event.status=="RESOLVED" else "DIFFERENT_IDENTITY","owner_feedback:"+str(event.id))
    return {"labels":[value for value in pairs.values() if value["label"]!="CONFLICT"],
            "excluded_conflicts":sum(value["label"]=="CONFLICT" for value in pairs.values()),"automatic_training":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    args=parser.parse_args()
    with SessionLocal() as db:
        report=collect_labels(db)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with open(args.output,"x",encoding="utf-8",opener=lambda path,flags:os.open(path,flags,0o600)) as stream:
        json.dump(report,stream,indent=2)
    args.output.chmod(0o600)
    print(json.dumps({"labels":len(report["labels"]),"excluded_conflicts":report["excluded_conflicts"]}))


if __name__=="__main__":
    main()
