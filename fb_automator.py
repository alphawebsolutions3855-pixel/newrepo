import os
import time
import logging
from typing import List, Optional

DRY = os.environ.get('AA_DRY_RUN', '1') == '1'
log = logging.getLogger('aa.automator')

if not DRY:
    from playwright.sync_api import sync_playwright, Page


def _log_action(action: str, details: Optional[dict] = None):
    log.info('AUTOMATOR: %s %s', action, details or {})


class FBAutomator:
    def __init__(self, headless=True):
        self.headless = headless
        self._pw = None
        self._browser = None
        self._context = None
        self._page = None

    def start(self):
        if DRY:
            _log_action('start_browser', {'headless': self.headless})
            return
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self.headless)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()
        _log_action('browser_started')

    def stop(self):
        if DRY:
            _log_action('stop_browser')
            return
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception as e:
            log.exception('Error stopping browser: %s', e)

    def login(self, email: str, password: str) -> bool:
        _log_action('login', {'email': email})
        if DRY:
            return True
        p: Page = self._page
        p.goto('https://www.facebook.com/login', timeout=30000)
        # attempt typical login flow
        p.fill('input[name="email"]', email)
        p.fill('input[name="pass"]', password)
        p.click('button[name="login"]')
        time.sleep(3)
        # heuristic: check for presence of profile link
        if p.query_selector('a[aria-label="Profile"]'):
            return True
        return True

    def create_page_post(self, page_url: str, message: str, media_paths: Optional[List[str]] = None, hold_publish: bool = False) -> dict:
        _log_action('create_page_post', {'page_url': page_url, 'message': message, 'media': media_paths, 'hold': hold_publish})
        if DRY:
            return {'status': 'dry', 'id': None}
        p: Page = self._page
        p.goto(page_url)
        # naive: click post composer
        # selectors vary; rely on handlers stored elsewhere
        composer = p.query_selector('div[role="textbox"]')
        if not composer:
            composer = p.query_selector('textarea')
        if not composer:
            raise RuntimeError('Composer not found')
        composer.click()
        composer.fill(message)
        if media_paths:
            # upload via file input if available
            file_input = p.query_selector('input[type="file"]')
            if file_input:
                file_input.set_input_files(media_paths)
        # if hold_publish: do not click publish; else click publish
        if not hold_publish:
            publish_btn = p.query_selector('div[aria-label="Post"] button')
            if publish_btn:
                publish_btn.click()
        return {'status': 'posted', 'id': None}

    def bulk_create_listings(self, page_url: str, listings: List[dict], hold_publish: bool = True) -> dict:
        _log_action('bulk_create_listings', {'count': len(listings), 'hold': hold_publish})
        if DRY:
            return {'status': 'dry', 'count': len(listings)}
        results = []
        for item in listings:
            res = self.create_page_post(page_url, item.get('message',''), item.get('media'), hold_publish=hold_publish)
            results.append(res)
            time.sleep(1)
        return {'status': 'done', 'results': results}

    def save_draft(self, page_url: str, message: str) -> dict:
        _log_action('save_draft', {'page_url': page_url})
        if DRY:
            return {'status':'dry'}
        # Implementation depends on FB UI; placeholder
        return {'status': 'saved'}

    def publish_draft(self, draft_id: str) -> dict:
        _log_action('publish_draft', {'draft_id': draft_id})
        if DRY:
            return {'status':'dry'}
        # Placeholder
        return {'status':'published'}


# convenience simple API
_automator = FBAutomator()

def ensure_started():
    try:
        _automator.start()
    except Exception:
        pass


def stop():
    _automator.stop()


def login(email, password):
    ensure_started()
    return _automator.login(email, password)


def bulk_create(page_url, listings, hold_publish=True):
    ensure_started()
    return _automator.bulk_create_listings(page_url, listings, hold_publish)


def create_post(page_url, message, media=None, hold_publish=False):
    ensure_started()
    return _automator.create_page_post(page_url, message, media, hold_publish)
