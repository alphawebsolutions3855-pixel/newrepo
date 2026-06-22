import os
import requests
import time
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from typing import Optional, List, Dict

GRAPH_API_BASE = os.environ.get('FB_GRAPH_API', 'https://graph.facebook.com/v17.0')
MOCK = os.environ.get('AA_MOCK_FB', '1') == '1'
SIMULATE_FAILURES = os.environ.get('AA_SIMULATE_FAIL', '0') == '1'

class FBClientError(Exception):
    pass


@retry(wait=wait_exponential(multiplier=1, min=1, max=10), stop=stop_after_attempt(5), retry=retry_if_exception_type(FBClientError))
def post_to_graph(path: str, params: Dict[str, str], files: Optional[Dict] = None) -> Dict:
    # simulate failures for testing retry logic
    if SIMULATE_FAILURES:
        # if message contains 'fail' trigger an error
        msg = params.get('message') or params.get('caption') or ''
        if 'fail' in msg:
            raise FBClientError('simulated failure')
    if MOCK:
        # return a fake id
        return {"id": f"mock_{int(time.time()*1000)}"}
    url = f"{GRAPH_API_BASE}/{path}"
    try:
        r = requests.post(url, data=params, files=files, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        raise FBClientError(str(e))


def publish_to_page(page_id: str, page_access_token: str, message: str, link: Optional[str] = None, media_urls: Optional[List[str]] = None) -> Dict:
    # For simple message+link posts using the /{page-id}/feed endpoint
    params = {'message': message, 'access_token': page_access_token}
    if link:
        params['link'] = link
    return post_to_graph(f"{page_id}/feed", params)


def publish_photo(page_id: str, page_access_token: str, photo_url: str, caption: Optional[str] = None) -> Dict:
    params = {'url': photo_url, 'access_token': page_access_token}
    if caption:
        params['caption'] = caption
    return post_to_graph(f"{page_id}/photos", params)
