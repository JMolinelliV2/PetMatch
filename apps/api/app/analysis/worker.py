"""Persistent bounded workers; separate semantic and visual lanes in production."""
import asyncio
import json
import os
import threading
import time
from rq import Queue, SimpleWorker
from rq.serializers import JSONSerializer
from app.analysis.queue import get_queue, QUEUE_NAME
from app.analysis.logging import log_event
from app.core.config import settings


class PersistentWorker(SimpleWorker):
    deadline = 0.0

    def execute_job(self,job,queue):
        self.deadline=time.monotonic()+job.timeout+15
        try:
            return super().execute_job(job,queue)
        finally:
            self.deadline=0.0


def heartbeat(worker,kinds,stop):
    while not stop.wait(5):
        if worker.deadline and time.monotonic()>worker.deadline:
            # Native runtime stuck past timeout: container restart + DB lease recover the job.
            os._exit(70)
        try:
            for kind in kinds:
                from app.ops.resources import container_resources
                worker.connection.set("mascomatch:worker:"+kind,json.dumps({"time":time.time(),"pid":os.getpid(),
                    "busy":bool(worker.deadline),"resources":container_resources()}),ex=30)
        except Exception:
            pass


def main():
    kind=settings.analysis_worker_kind
    kinds=["visual","semantic"] if kind=="all" else [kind]
    connection=get_queue().connection
    # Strict tier order prevents queued backfill delaying a newly submitted sighting.
    names=[f"{QUEUE_NAME}-{lane}-{tier}" for tier in ("urgent","normal","backfill") for lane in kinds]
    queues=[Queue(name,connection=connection,serializer=JSONSerializer) for name in names]
    worker=PersistentWorker(queues,connection=connection,serializer=JSONSerializer,log_job_description=False)
    stop=threading.Event()
    thread=threading.Thread(target=heartbeat,args=(worker,kinds,stop),daemon=True)
    thread.start()
    if "semantic" in kinds:
        from app.analysis.providers import prewarm_models
        for outcome in asyncio.run(prewarm_models()):
            log_event("ollama_prewarm",**outcome)
    try:
        worker.work(logging_level="WARNING")
    finally:
        stop.set()


if __name__=="__main__":
    main()
