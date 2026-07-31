from __future__ import annotations
import argparse,time
from app.services import research_repository as repo
from app.services.research_v3 import run
RUNNABLE={"searching","retrying","reading","extracting","verifying","proposing"}
def run_once()->int:
    jobs=[job for job in repo.list_jobs() if job.status in RUNNABLE]
    for job in jobs:run(job.job_id)
    return len(jobs)
def main():
    parser=argparse.ArgumentParser(description="LogiSpace checkpointed research worker");parser.add_argument("--once",action="store_true");parser.add_argument("--interval",type=float,default=2);args=parser.parse_args()
    while True:
        run_once()
        if args.once:return
        time.sleep(max(.2,args.interval))
if __name__=="__main__":main()
