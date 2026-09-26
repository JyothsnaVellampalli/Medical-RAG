from uuid import UUID

from Evaluation.evaluation_engine import evaluation_engine

job_id = UUID("173372c5-5686-4113-b1ab-47e2ce2190f3")
evaluation_engine.resume_job(job_id)

# Keep the process alive; resume_job starts a daemon thread.
import time
while True:
    time.sleep(3600)
