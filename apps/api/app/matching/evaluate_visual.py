"""Evaluate identity-labelled local photos with installed visual models; never trains."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from time import monotonic
from app.embeddings.provider import get_embedding_provider
from app.embeddings.specs import openclip_spec,pet_reid_spec
from app.matching.scoring import cosine,aggregate_visual_similarity
from app.core.config import settings


def load_dataset(path):
    path=Path(path).resolve()
    document=json.loads(path.read_text(encoding="utf-8"))
    rows=document["images"]
    if not isinstance(rows,list) or not 2<=len(rows)<=10000:
        raise ValueError("Dataset requires 2..10000 labelled images")
    hashes=set()
    identities={}
    names=set()
    for row in rows:
        file=(path.parent/row["file"]).resolve()
        if not file.is_relative_to(path.parent) or not file.is_file() or Path(row["file"]).is_absolute():
            raise ValueError("Image must be an existing file inside the dataset directory")
        if row["file"] in names or row.get("role") not in {"gallery","query"} or not row.get("identity"):
            raise ValueError("Duplicate file, missing identity or invalid gallery/query role")
        names.add(row["file"])
        digest=hashlib.sha256(file.read_bytes()).hexdigest()
        if digest in hashes:
            raise ValueError("Repeated image bytes contaminate evaluation")
        hashes.add(digest)
        split=row.get("split","test")
        if split not in {"train","calibration","test"} or row.get("species","unknown") not in {"dog","cat"}:
            raise ValueError("Invalid split or species")
        if identities.setdefault(row["identity"],split)!=split:
            raise ValueError("An identity occurs in more than one train/calibration/test split")
        row["path"]=file
    hard={frozenset(pair) for pair in document.get("hard_negatives",[])}
    if any(len(pair)!=2 or not pair<=names for pair in hard):
        raise ValueError("Hard negatives must name two different dataset files")
    return rows,hard


def evaluate(rows,hard,provider_name,threshold=.8):
    spec=pet_reid_spec() if provider_name=="pet_reid" else openclip_spec()
    provider=get_embedding_provider(spec)
    vectors={}
    latencies=[]
    for row in rows:
        if provider_name=="pet_reid" and row.get("species") not in {"dog","cat"}:
            raise ValueError("Pet-ReID comparison requires a common dog/cat-only dataset")
        started=monotonic()
        result=provider.encode_result(row["path"].read_bytes(),row.get("species","unknown"))
        latencies.append(monotonic()-started)
        vectors[row["file"]]=result.vector
    positive=negative=false_positive=hard_count=0
    for index,left in enumerate(rows):
        for right in rows[index+1:]:
            same=left["identity"]==right["identity"]
            positive+=int(same)
            negative+=int(not same)
            pair=frozenset([left["file"],right["file"]])
            if pair in hard and same:
                raise ValueError("Hard negative has the same labelled identity")
            hard_count+=int(pair in hard)
            false_positive+=int(not same and cosine(vectors[left["file"]],vectors[right["file"]])>=threshold)
    ranks=[]
    queries=[row for row in rows if row["role"]=="query"]
    gallery=[row for row in rows if row["role"]=="gallery"]
    for query in queries:
        groups={}
        for reference in gallery:
            groups.setdefault(reference["identity"],[]).append(cosine(vectors[query["file"]],vectors[reference["file"]]))
        ordered=sorted(groups,key=lambda identity:aggregate_visual_similarity(groups[identity]),reverse=True)
        ranks.append(ordered.index(query["identity"])+1 if query["identity"] in ordered else math.inf)
    def top(k):
        return sum(rank<=k for rank in ranks)/len(ranks) if ranks else None
    latencies.sort()
    return {"identities":len({r["identity"] for r in rows}),"images":len(rows),"queries":len(queries),
        "positive_pairs":positive,"negative_pairs":negative,"hard_negatives":hard_count,
        "top_1":top(1),"top_3":top(3),"top_5":top(5),"recall_at_1":top(1),"recall_at_5":top(5),
        "false_positive_rate":false_positive/negative if negative else None,"cosine_threshold":threshold,
        "latency_p50_seconds":latencies[math.ceil(len(latencies)*.5)-1],"latency_p95_seconds":latencies[math.ceil(len(latencies)*.95)-1],
        "spec":spec.to_dict(),"space_id":spec.space_id,"aggregation":"best or weighted best+second; one relevant identity/query",
        "warning":"Ranking/false-positive estimates depend on this labelled dataset; scores are not probabilities."}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset",type=Path)
    parser.add_argument("--provider",choices=["open_clip","pet_reid","both"],default="both")
    parser.add_argument("--threshold",type=float,help="Override for a single provider only")
    parser.add_argument("--openclip-threshold",type=float,default=.87)
    parser.add_argument("--pet-reid-threshold",type=float,default=.82)
    parser.add_argument("--split",choices=["calibration","test"],default="test")
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    if any(not -1<=value<=1 for value in (args.openclip_threshold,args.pet_reid_threshold) if value is not None) or (args.threshold is not None and not -1<=args.threshold<=1):
        parser.error("Cosine threshold must be between -1 and 1")
    if args.provider=="both" and args.threshold is not None:
        parser.error("Set separate --openclip-threshold and --pet-reid-threshold for two incompatible spaces")
    rows,hard=load_dataset(args.dataset)
    rows=[row for row in rows if row.get("split","test")==args.split]
    if not rows or not any(r["role"]=="query" for r in rows) or not any(r["role"]=="gallery" for r in rows):
        parser.error("Selected split needs gallery and query photos")
    providers=["open_clip","pet_reid"] if args.provider=="both" else [args.provider]
    report={"split":args.split,"models":[evaluate(rows,hard,p,args.threshold if args.threshold is not None else
        args.openclip_threshold if p=="open_clip" else args.pet_reid_threshold) for p in providers]}
    rendered=json.dumps(report,indent=2)
    if args.output:
        args.output.write_text(rendered,encoding="utf-8")
    print(rendered)


if __name__=="__main__":
    main()
