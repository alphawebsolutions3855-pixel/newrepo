import asyncio
import logging
from db import get_session
from models import FBBatch, FBPostItem
from sqlmodel import select
from fb_client import publish_to_page, publish_photo
import json
from datetime import datetime, timedelta
from metrics import items_published, items_failed, items_pending, worker_active

log = logging.getLogger('aa.worker')


class AsyncPublishWorker:
    def __init__(self, interval=5, concurrency=2):
        self.interval = interval
        self.concurrency = concurrency
        self._task = None
        self._stop = False
        self._semaphore = asyncio.Semaphore(concurrency)

    async def start(self):
        if self._task is None:
            self._task = asyncio.create_task(self._run())
            worker_active.set(1)

    async def stop(self):
        self._stop = True
        if self._task:
            await self._task
        worker_active.set(0)

    async def _run(self):
        log.info('AsyncPublishWorker started')
        while not self._stop:
            try:
                await self.process_once()
            except Exception as e:
                log.exception('Worker error: %s', e)
            await asyncio.sleep(self.interval)

    async def process_once(self):
        # process batches that are not fired and items due for attempt
        with get_session() as s:
            batches = s.exec(select(FBBatch).where(FBBatch.fired == False)).all()
            for b in batches:
                log.info('Processing batch %s', b.id)
                rows = s.exec(select(FBPostItem).where(FBPostItem.batch_id == b.id)).all()
                item_ids = []
                now = datetime.utcnow()
                for it in rows:
                    if it.next_attempt_at and it.next_attempt_at > now:
                        continue
                    if it.status == 'published':
                        continue
                    item_ids.append(it.id)
                if item_ids:
                    items_pending.set(len(item_ids))
                    tasks = [self._process_item(iid) for iid in item_ids]
                    await asyncio.gather(*tasks)
                    items_pending.set(0)
                # ensure session sees updates made in other transactions
                try:
                    s.expire_all()
                except Exception:
                    pass
                # if all items published, mark batch fired
                s.refresh(b)
                items2 = s.exec(select(FBPostItem).where(FBPostItem.batch_id == b.id)).all()
                if items2 and all(i.status == 'published' for i in items2):
                    b.fired = True
                    s.add(b)
                    s.commit()

    async def _process_item(self, item_id: int):
        async with self._semaphore:
            # run publish in thread executor because fb_client is sync
            try:
                loop = asyncio.get_running_loop()
                with get_session() as s:
                    it = s.get(FBPostItem, item_id)
                    if not it:
                        return
                    medias = json.loads(it.media_urls or '[]')
                for m in medias:
                    await loop.run_in_executor(None, publish_photo, '', '', m, it.message)
                res = await loop.run_in_executor(None, publish_to_page, '', '', it.message, it.link)
                with get_session() as s:
                    it = s.get(FBPostItem, item_id)
                    it.published_id = res.get('id')
                    it.status = 'published'
                    it.last_attempt = datetime.utcnow()
                    s.add(it)
                    s.commit()
                items_published.inc()
                log.info('Published item %s', item_id)
            except Exception as e:
                # update retry state
                with get_session() as s:
                    it = s.get(FBPostItem, item_id)
                    if not it:
                        return
                    it.retry_count = (it.retry_count or 0) + 1
                    it.last_attempt = datetime.utcnow()
                    # exponential backoff: 2^retry seconds
                    delay = min(3600, 2 ** it.retry_count)
                    it.next_attempt_at = datetime.utcnow() + timedelta(seconds=delay)
                    it.status = 'retrying' if it.retry_count < 5 else 'failed'
                    s.add(it)
                    s.commit()
                items_failed.inc()
                log.exception('Failed to publish item %s: %s', item_id, e)


worker = AsyncPublishWorker()

async def start_worker():
    await worker.start()

async def stop_worker():
    await worker.stop()

async def run_once_async():
    await worker.process_once()
