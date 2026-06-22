from db import get_session
from models import Handler, ErrorLog
from sqlmodel import select
import logging

log = logging.getLogger('aa.self_healer')

def report_error(selector: str, error: str):
    with get_session() as s:
        # log error
        elog = ErrorLog(selector=selector, error=error)
        s.add(elog)
        # update handler fail stats
        stmt = select(Handler).where(Handler.selector == selector)
        h = s.exec(stmt).first()
        if h:
            h.fail_count = (h.fail_count or 0) + 1
            h.last_error = error[:1024]
            if h.fail_count >= 3:
                h.status = 'needs_repair'
        else:
            # create a handler record for tracking
            h = Handler(selector=selector, field_type=None, status='needs_repair', fail_count=1, last_error=error[:1024])
            s.add(h)
        # capture needed values while still attached to session
        fail_count = h.fail_count if h else 0
        sel = h.selector if h else selector
        s.commit()
    # attempt immediate heal for high-severity
    if fail_count >= 3:
        attempt_heal(sel)


def attempt_heal(selector: str):
    """Attempt a basic repair for a selector. This is a heuristic placeholder.

    Real implementations would rescan the page DOM, use ML to find matching fields,
    or replay UI flows to rediscover selectors. Here we attempt simple alternatives.
    """
    with get_session() as s:
        stmt = select(Handler).where(Handler.selector == selector)
        h = s.exec(stmt).first()
        if not h:
            log.warning('No handler found to heal: %s', selector)
            return False
        # heuristic: try variations
        candidates = [selector + ' input', selector.replace('aria-label', 'placeholder'), selector + ' textarea']
        # pick first candidate and mark as repaired
        new_selector = candidates[0]
        h.selector = new_selector
        h.status = 'active'
        h.fail_count = 0
        h.last_error = None
        s.commit()
        log.info('Healed handler %s -> %s', selector, new_selector)
        return True


def run_healing_cycle():
    with get_session() as s:
        stmt = select(Handler).where(Handler.fail_count >= 3)
        bad = s.exec(stmt).all()
        for h in bad:
            log.info('Auto-healing handler: %s', h.selector)
            attempt_heal(h.selector)
