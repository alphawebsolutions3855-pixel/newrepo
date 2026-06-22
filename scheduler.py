from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger
from datetime import datetime
from db import get_session
from models import ScheduledJob
import logging

log = logging.getLogger('aa.scheduler')

scheduler = BackgroundScheduler()

def start_scheduler():
    try:
        scheduler.start()
        log.info('Scheduler started')
    except Exception as e:
        # APScheduler raises SchedulerAlreadyRunningError if start() is called twice
        try:
            from apscheduler.schedulers.base import SchedulerAlreadyRunningError
            if isinstance(e, SchedulerAlreadyRunningError):
                log.info('Scheduler already running; skipping start')
            else:
                raise
        except Exception:
            # fallback: if we couldn't import the specific error, re-raise
            raise
    # schedule periodic self-healing job every 5 minutes
    try:
        from self_healer import run_healing_cycle
        # avoid adding the same job multiple times
        if not scheduler.get_job('self_heal_cycle'):
            scheduler.add_job(run_healing_cycle, 'interval', minutes=5, id='self_heal_cycle')
        log.info('Scheduled self-healing job')
    except Exception as e:
        log.exception('Failed to schedule self-healing job: %s', e)

def schedule_job(run_at: datetime, payload: str):
    job = scheduler.add_job(func=run_publish_job, trigger=DateTrigger(run_date=run_at), args=[payload])
    with get_session() as s:
        sj = ScheduledJob(job_id=job.id, payload=payload, run_at=run_at)
        s.add(sj)
        s.commit()
    return job.id

def run_publish_job(payload: str):
    log.info('Running publish job with payload: %s', payload)
    # placeholder: implement publishing logic here
