from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel
from typing import List, Optional
import uuid

from db import init_db, get_session
import os
from models import Post, Draft, License as LicenseModel, Offer as OfferModel, FBBatch, FBPostItem, ScheduledJob, Handler, User, Device, ErrorLog
from sqlmodel import select

from auth import get_current_user, create_access_token, get_password_hash
from security import sign_value, verify_signed, file_sha256
from scheduler import start_scheduler, schedule_job
import logging
from fb_client import publish_to_page, publish_photo
import json
from fb_automator import bulk_create as fb_bulk_create, create_post, login as fb_login
from metrics import metrics_text
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi import Form
import pathlib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('aa.server')

app = FastAPI()
BASE_DIR = pathlib.Path(__file__).resolve().parent

def render_admin_page(filename: str):
    return HTMLResponse(content=(BASE_DIR / 'admin' / filename).read_text())

# NOTE: avoid initializing DB at import time so tests can configure AA_DATABASE_URL

# Add CORS (restrict to configured origins in production)
try:
    from fastapi.middleware.cors import CORSMiddleware
    allow_origins = os.environ.get('AA_CORS_ORIGINS', 'http://localhost:3000,http://localhost:8000').split(',')
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allow_origins,
        allow_credentials=True,
        allow_methods=['GET', 'POST'],
        allow_headers=['*'],
    )
except Exception as e:
    logger.warning('CORS middleware not configured: %s', e)

# Add security headers
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


@app.middleware("http")
async def log_exceptions(request, call_next):
    try:
        response = await call_next(request)
        return response
    except Exception as e:
        logger.exception('Unhandled error: %s', e)
        raise


class UserLogin(BaseModel):
    username: str
    password: str


class PostIn(BaseModel):
    title: str
    body: str
    account_type: Optional[str] = "old"


class BatchCreate(BaseModel):
    posts: List[PostIn]
    hold_publish: Optional[bool] = False


class DraftAction(BaseModel):
    ids: List[int]


@app.on_event("startup")
def on_startup():
    init_db()
    start_scheduler()
    import asyncio
    import os
    from models import User
    from auth import get_password_hash
    from db import get_session
    auto_create = os.environ.get('AA_AUTO_CREATE_ADMIN', '1').lower() not in ('0','false')
    admin_pw = os.environ.get('AA_ADMIN_PASSWORD', 'admin123')
    if auto_create:
        with get_session() as s:
            any_user = s.exec(select(User)).first()
            if not any_user:
                u = User(username='admin', hashed_password=get_password_hash(admin_pw), is_admin=True)
                s.add(u)
                s.commit()
    # start async worker
    try:
        import publish_worker
        asyncio.create_task(publish_worker.start_worker())
    except Exception:
        logger.exception('Failed to start publish worker')


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get('/metrics')
def metrics():
    # return Prometheus metrics
    from fastapi.responses import Response
    return Response(content=metrics_text(), media_type='text/plain; version=0.0.4')


@app.get('/admin/batches')
def admin_batches(user=Depends(get_current_user)):
    from models import FBBatch, FBPostItem
    with get_session() as s:
        stmt = select(FBBatch)
        batches = s.exec(stmt).all()
        out = []
        for b in batches:
            items = s.exec(select(FBPostItem).where(FBPostItem.batch_id == b.id)).all()
            out.append({
                'id': b.id,
                'name': b.name,
                'created_at': b.created_at.isoformat(),
                'fired': bool(b.fired),
                'items': len(items),
                'published': sum(1 for i in items if i.status == 'published')
            })
        return {'batches': out}


@app.get('/admin/dashboard')
def admin_dashboard(user=Depends(get_current_user)):
    # Return comprehensive dashboard stats and monitoring info
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    
    with get_session() as s:
        # Gather stats
        posts_count = len(s.exec(select(Post)).all())
        drafts_count = len(s.exec(select(Draft)).all())
        batches_count = len(s.exec(select(FBBatch)).all())
        users_count = len(s.exec(select(User)).all())
        licenses_count = len(s.exec(select(LicenseModel)).all())
        offers_count = len(s.exec(select(OfferModel)).all())
        devices_count = len(s.exec(select(Device)).all())
        scheduled_jobs_count = len(s.exec(select(ScheduledJob)).all())
        handlers_count = len(s.exec(select(Handler)).all())
        error_logs_count = len(s.exec(select(ErrorLog)).all())
        
        batches_fired = len([b for b in s.exec(select(FBBatch)).all() if b.fired])
        posts_published = len([p for p in s.exec(select(Post)).all() if p.published])
        handlers_failed = len([h for h in s.exec(select(Handler)).all() if h.status == 'needs_repair'])
        
    # Generate HTML dashboard
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Alpha Automation Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .stat {{ display: inline-block; margin: 10px; padding: 15px; background: #f0f0f0; border-radius: 5px; }}
            .stat-value {{ font-size: 24px; font-weight: bold; color: #333; }}
            .stat-label {{ font-size: 12px; color: #666; }}
            .alert {{ color: #d9534f; }}
        </style>
    </head>
    <body>
        <h1>Alpha Automation Dashboard</h1>
        <p>Logged in as: <strong>{user.username}</strong> (Admin: {user.is_admin})</p>
        
        <h2>Statistics</h2>
        <div class="stat"><div class="stat-value">{posts_count}</div><div class="stat-label">Posts</div></div>
        <div class="stat"><div class="stat-value">{posts_published}</div><div class="stat-label">Published</div></div>
        <div class="stat"><div class="stat-value">{drafts_count}</div><div class="stat-label">Drafts</div></div>
        <div class="stat"><div class="stat-value">{batches_count}</div><div class="stat-label">Batches</div></div>
        <div class="stat"><div class="stat-value">{batches_fired}</div><div class="stat-label">Fired</div></div>
        <div class="stat"><div class="stat-value">{users_count}</div><div class="stat-label">Users</div></div>
        <div class="stat"><div class="stat-value">{licenses_count}</div><div class="stat-label">Licenses</div></div>
        <div class="stat"><div class="stat-value">{offers_count}</div><div class="stat-label">Offers</div></div>
        <div class="stat"><div class="stat-value">{devices_count}</div><div class="stat-label">Devices</div></div>
        <div class="stat"><div class="stat-value">{scheduled_jobs_count}</div><div class="stat-label">Scheduled</div></div>
        <div class="stat"><div class="stat-value">{handlers_count}</div><div class="stat-label">Handlers</div></div>
        <div class="stat alert"><div class="stat-value">{handlers_failed}</div><div class="stat-label">Failed Handlers</div></div>
        <div class="stat alert"><div class="stat-value">{error_logs_count}</div><div class="stat-label">Errors</div></div>
        
        <h2>Quick Links</h2>
        <ul>
            <li><a href="/admin/users/ui">Manage Users</a></li>
            <li><a href="/admin/batches">View Batches</a></li>
            <li><a href="/admin/logout">Logout</a></li>
        </ul>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


@app.get('/admin/users/list')
def admin_users_list(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    from models import User
    with get_session() as s:
        stmt = select(User)
        users = s.exec(stmt).all()
        return {'users': [{'id': u.id, 'username': u.username, 'is_admin': bool(u.is_admin)} for u in users]}


@app.get('/admin/users/ui')
def admin_users_ui(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    return render_admin_page('users.html')


@app.get('/admin/licenses/ui')
def admin_licenses_ui(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    return render_admin_page('licenses.html')


@app.get('/admin/batches/ui')
def admin_batches_ui(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    return render_admin_page('batches.html')


@app.get('/admin/posts/ui')
def admin_posts_ui(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    return render_admin_page('posts.html')


@app.get('/admin/devices/ui')
def admin_devices_ui(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    return render_admin_page('devices.html')


@app.get('/admin/offers/ui')
def admin_offers_ui(user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    return render_admin_page('offers.html')


@app.post('/admin/users/{username}/set_password')
def admin_set_password(username: str, new_password: str = Form(...), user=Depends(get_current_user)):
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    from models import User
    from auth import get_password_hash
    with get_session() as s:
        stmt = select(User).where(User.username == username)
        u = s.exec(stmt).first()
        if not u:
            raise HTTPException(status_code=404, detail='user not found')
        u.hashed_password = get_password_hash(new_password)
        s.add(u)
        s.commit()
    return {'updated': username}


@app.get('/admin/login')
def admin_login_get():
    return render_admin_page('login.html')


@app.post('/admin/login')
def admin_login_post(username: str = Form(...), password: str = Form(...)):
    from auth import verify_password
    from models import User
    with get_session() as s:
        stmt = select(User).where(User.username == username)
        user = s.exec(stmt).first()
        if not user or not verify_password(password, user.hashed_password):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='invalid credentials')
    token = create_access_token({"sub": username})
    resp = RedirectResponse(url='/admin/dashboard', status_code=302)
    cookie_secure = os.environ.get('AA_COOKIE_SECURE', '0').lower() in ('1', 'true', 'yes')
    samesite = os.environ.get('AA_COOKIE_SAMESITE', 'Lax')
    resp.set_cookie(
        'aa_token',
        token,
        httponly=True,
        max_age=3600,
        secure=cookie_secure,
        samesite=samesite,
    )
    return resp


@app.post('/admin/logout')
def admin_logout(user=Depends(get_current_user)):
    resp = RedirectResponse(url='/admin/login', status_code=302)
    resp.delete_cookie('aa_token')
    return resp


@app.get('/')
def home():
    return render_admin_page('index.html')


@app.post('/admin/users')
def admin_create_user(username: str = Form(...), password: str = Form(...), is_admin: bool = Form(False), user=Depends(get_current_user)):
    # only admins can create users
    if not user.is_admin:
        raise HTTPException(status_code=403, detail='admin required')
    from auth import get_password_hash
    from models import User
    with get_session() as s:
        stmt = select(User).where(User.username == username)
        exists = s.exec(stmt).first()
        if exists:
            raise HTTPException(status_code=400, detail='user exists')
        u = User(username=username, hashed_password=get_password_hash(password), is_admin=bool(is_admin))
        s.add(u)
        s.commit()
    return {'created': username}


@app.post('/admin/users/bootstrap')
def admin_bootstrap(username: str = Form(...), password: str = Form(...)):
    # create initial admin if no users exist
    from models import User
    with get_session() as s:
        any_user = s.exec(select(User)).first()
        if any_user:
            raise HTTPException(status_code=400, detail='users already exist')
        from auth import get_password_hash
        u = User(username=username, hashed_password=get_password_hash(password), is_admin=True)
        s.add(u)
        s.commit()
    return {'created': username}


@app.post('/admin/users/change_password')
def admin_change_password(old_password: str = Form(...), new_password: str = Form(...), user=Depends(get_current_user)):
    from auth import verify_password, get_password_hash
    from models import User
    with get_session() as s:
        u = s.get(User, user.id)
        if not verify_password(old_password, u.hashed_password):
            raise HTTPException(status_code=400, detail='invalid password')
        u.hashed_password = get_password_hash(new_password)
        s.add(u)
        s.commit()
    return {'changed': user.username}


@app.post("/auth/token")
def token(data: UserLogin):
    # verify username/password against DB
    from models import User
    from sqlalchemy.exc import OperationalError
    try:
        with get_session() as s:
            stmt = select(User).where(User.username == data.username)
            user = s.exec(stmt).first()
    except OperationalError:
        # try to initialize DB and retry once
        try:
            init_db()
            with get_session() as s:
                stmt = select(User).where(User.username == data.username)
                user = s.exec(stmt).first()
        except Exception:
            raise HTTPException(status_code=500, detail='database error')
    if not user:
        raise HTTPException(status_code=401, detail='invalid credentials')
    from auth import verify_password
    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail='invalid credentials')
    token = create_access_token({"sub": data.username})
    return {"access_token": token, "token_type": "bearer"}


@app.post("/posts/create")
def create_post(p: PostIn, user=Depends(get_current_user)):
    post = Post(title=p.title, body=p.body, account_type=p.account_type)
    with get_session() as s:
        s.add(post)
        s.commit()
        s.refresh(post)
    return {"id": post.id}


@app.post("/posts/bulk_create")
def bulk_create(b: BatchCreate, user=Depends(get_current_user)):
    ids = []
    with get_session() as s:
        for p in b.posts:
            post = Post(title=p.title, body=p.body, account_type=p.account_type)
            s.add(post)
            s.commit()
            s.refresh(post)
            ids.append(post.id)
    return {"ids": ids}


@app.post('/facebook/prepare_batch')
def fb_prepare_batch(body: dict, user=Depends(get_current_user)):
    # body: {"name":"batch1","items":[{"message":"...","link":null,"media_urls":[]}]}
    name = body.get('name', 'batch')
    items = body.get('items', [])
    with get_session() as s:
        batch = FBBatch(name=name)
        s.add(batch)
        s.commit()
        s.refresh(batch)
        batch_id = batch.id
        for it in items:
            item = FBPostItem(batch_id=batch_id, message=it.get('message',''), link=it.get('link'), media_urls=json.dumps(it.get('media_urls') or []))
            s.add(item)
        s.commit()
    return {"batch_id": batch_id}


@app.get('/facebook/batches/{batch_id}')
def fb_batch_detail(batch_id: int, user=Depends(get_current_user)):
    with get_session() as s:
        batch = s.get(FBBatch, batch_id)
        if not batch:
            raise HTTPException(status_code=404, detail='batch not found')
        items = s.exec(select(FBPostItem).where(FBPostItem.batch_id == batch_id)).all()
        return {
            'id': batch.id,
            'name': batch.name,
            'fired': bool(batch.fired),
            'items': [
                {
                    'id': it.id,
                    'message': it.message,
                    'link': it.link,
                    'media_urls': json.loads(it.media_urls or '[]'),
                    'status': it.status,
                    'published_id': it.published_id,
                }
                for it in items
            ]
        }


@app.post('/facebook/fire_batch')
def fb_fire_batch(body: dict, user=Depends(get_current_user)):
    # body: {"batch_id":1, "page_id":"...", "page_token":"..."}
    batch_id = body.get('batch_id')
    page_id = body.get('page_id')
    page_token = body.get('page_token')
    if not batch_id or not page_id or not page_token:
        raise HTTPException(status_code=400, detail='batch_id, page_id, page_token required')
    published = []
    with get_session() as s:
        b = s.get(FBBatch, batch_id)
        if not b:
            raise HTTPException(status_code=404, detail='batch not found')
        items = s.exec(select(FBPostItem).where(FBPostItem.batch_id == batch_id)).all()
        for it in items:
            try:
                medias = json.loads(it.media_urls or '[]')
                for m in medias:
                    publish_photo(page_id, page_token, m, caption=it.message)
                res = publish_to_page(page_id, page_token, it.message, link=it.link)
                it.published_id = res.get('id')
                s.add(it)
                s.commit()
                published.append(it.published_id)
            except Exception as e:
                logging.exception('Error publishing item %s: %s', it.id, e)
        b.fired = True
        s.add(b)
        s.commit()
    return {"published": published}


@app.post('/facebook/ui/bulk_create')
def fb_ui_bulk_create(body: dict, user=Depends(get_current_user)):
    # body: {"page_url":"...","listings":[{message,media}], "hold":true}
    page_url = body.get('page_url')
    listings = body.get('listings', [])
    hold = body.get('hold', True)
    if not page_url or not listings:
        raise HTTPException(status_code=400, detail='page_url and listings required')
    res = fb_bulk_create(page_url, listings, hold_publish=hold)
    return res


@app.post('/facebook/ui/login')
def fb_ui_login(body: dict, user=Depends(get_current_user)):
    email = body.get('email')
    password = body.get('password')
    if not email or not password:
        raise HTTPException(status_code=400, detail='email and password required')
    ok = fb_login(email, password)
    return {"ok": bool(ok)}


@app.post('/worker/run_once')
async def worker_run_once(user=Depends(get_current_user)):
    import publish_worker
    await publish_worker.run_once_async()
    return {"status": "ran"}


@app.get('/posts/list')
def list_posts(published: Optional[bool] = None, account_type: Optional[str] = None, user=Depends(get_current_user)):
    with get_session() as s:
        stmt = select(Post)
        if published is not None:
            stmt = stmt.where(Post.published == published)
        if account_type:
            stmt = stmt.where(Post.account_type == account_type)
        posts = s.exec(stmt).all()
        return {'posts': [
            {
                'id': p.id,
                'title': p.title,
                'body': p.body,
                'account_type': p.account_type,
                'created_at': p.created_at.isoformat(),
                'published': bool(p.published),
                'batch_id': p.batch_id,
            }
            for p in posts
        ]}


@app.get('/posts/{post_id}')
def get_post(post_id: int, user=Depends(get_current_user)):
    with get_session() as s:
        post = s.get(Post, post_id)
        if not post:
            raise HTTPException(status_code=404, detail='post not found')
        return {
            'id': post.id,
            'title': post.title,
            'body': post.body,
            'account_type': post.account_type,
            'created_at': post.created_at.isoformat(),
            'published': bool(post.published),
            'batch_id': post.batch_id,
        }


@app.post("/posts/publish_batch/{batch_id}")
def publish_batch(batch_id: int, user=Depends(get_current_user)):
    with get_session() as s:
        stmt = select(Post).where(Post.batch_id == batch_id)
        posts = s.exec(stmt).all()
        if not posts:
            raise HTTPException(status_code=404, detail='batch not found or contains no posts')
        for post in posts:
            post.published = True
            s.add(post)
        s.commit()
    return {"published_batch": batch_id, "count": len(posts)}


@app.get('/drafts/list')
def list_drafts(user=Depends(get_current_user)):
    with get_session() as s:
        stmt = select(Draft)
        drafts = s.exec(stmt).all()
        return {'drafts': [
            {'id': d.id, 'title': d.title, 'body': d.body, 'created_at': d.created_at.isoformat()}
            for d in drafts
        ]}


@app.get('/schedule/jobs')
def list_scheduled_jobs(user=Depends(get_current_user)):
    with get_session() as s:
        stmt = select(ScheduledJob)
        jobs = s.exec(stmt).all()
        return {'jobs': [
            {'id': j.id, 'job_id': j.job_id, 'payload': j.payload, 'run_at': j.run_at.isoformat() if j.run_at else None, 'created_at': j.created_at.isoformat()}
            for j in jobs
        ]}


@app.get('/handlers/status')
def handler_status(user=Depends(get_current_user)):
    with get_session() as s:
        stmt = select(Handler)
        handlers = s.exec(stmt).all()
        return {'handlers': [
            {'id': h.id, 'selector': h.selector, 'field_type': h.field_type, 'status': h.status, 'fail_count': h.fail_count, 'last_error': h.last_error}
            for h in handlers
        ]}


@app.post('/handlers/repair')
def handler_repair(body: dict, user=Depends(get_current_user)):
    selector = body.get('selector')
    if not selector:
        raise HTTPException(status_code=400, detail='selector required')
    from self_healer import attempt_heal
    ok = attempt_heal(selector)
    if not ok:
        raise HTTPException(status_code=404, detail='handler not found or repair failed')
    return {'repaired': selector}


class AIGenerateRequest(BaseModel):
    prompt: str
    style: Optional[str] = 'standard'


@app.post('/ai/generate')
def ai_generate(payload: AIGenerateRequest, user=Depends(get_current_user)):
    from ai.trainer import generate_post
    result = generate_post(payload.prompt, payload.style)
    return result


@app.post("/drafts/save")
def save_draft(p: PostIn, user=Depends(get_current_user)):
    d = Draft(title=p.title, body=p.body)
    with get_session() as s:
        s.add(d)
        s.commit()
        s.refresh(d)
    return {"draft_id": d.id}


@app.post("/drafts/publish")
def publish_drafts(action: DraftAction, user=Depends(get_current_user)):
    published = []
    with get_session() as s:
        for _id in action.ids:
            d = s.get(Draft, _id)
            if d:
                post = Post(title=d.title, body=d.body)
                s.add(post)
                s.delete(d)
                s.commit()
                s.refresh(post)
                published.append(post.id)
    return {"published": published}


@app.post("/posts/delete_duplicates")
def delete_duplicates(user=Depends(get_current_user)):
    removed = []
    with get_session() as s:
        stmt = select(Post)
        rows = s.exec(stmt).all()
        seen = {}
        for post in rows:
            key = (post.title.strip(), post.body.strip())
            if key in seen:
                removed.append(post.id)
                s.delete(post)
            else:
                seen[key] = post.id
        s.commit()
    return {"removed": removed}


@app.post("/handlers/scan")
def scan_handler(html: dict, user=Depends(get_current_user)):
    body = html.get("html", "")
    fields = []
    if "input" in body:
        fields.append("input")
    if "select" in body:
        fields.append("select")
    # store detected handlers
    with get_session() as s:
        for f in fields:
            h = dict(selector=f, field_type=f)
            # simplistic insert
            from models import Handler
            obj = Handler(selector=f, field_type=f)
            s.add(obj)
        s.commit()
    return {"fields": fields}


@app.get("/handlers/list")
def list_handlers(user=Depends(get_current_user)):
    from models import Handler
    with get_session() as s:
        stmt = select(Handler)
        items = s.exec(stmt).all()
        return {"handlers": [dict(id=i.id, selector=i.selector, type=i.field_type) for i in items]}


@app.post('/schedule/publish')
def schedule_publish(body: dict, user=Depends(get_current_user)):
    # body: {"run_at":"2026-01-01T12:00:00","payload":"..."}
    run_at = body.get('run_at')
    payload = body.get('payload','')
    if not run_at:
        raise HTTPException(status_code=400, detail='run_at required')
    from datetime import datetime
    dt = datetime.fromisoformat(run_at)
    job_id = schedule_job(dt, payload)
    return {"job_id": job_id}


@app.post('/errors/report')
def report_error(body: dict, user=Depends(get_current_user)):
    selector = body.get('selector')
    error = body.get('error', '')
    if not selector or not error:
        raise HTTPException(status_code=400, detail='selector and error required')
    from self_healer import report_error as rep
    rep(selector, error)
    return {"status": "reported"}


@app.post("/admin/licenses/generate")
def gen_license(payload: dict, user=Depends(get_current_user)):
    key = str(uuid.uuid4())
    lic = LicenseModel(key=key, package=payload.get('pkg', 'standard'))
    with get_session() as s:
        s.add(lic)
        s.commit()
        s.refresh(lic)
    sig = sign_value(lic.key)
    return {"key": lic.key, "signature": sig}


@app.post("/admin/licenses/delete")
def del_license(payload: dict, user=Depends(get_current_user)):
    key = payload.get("key")
    with get_session() as s:
        stmt = select(LicenseModel).where(LicenseModel.key == key)
        lic = s.exec(stmt).first()
        if lic:
            s.delete(lic)
            s.commit()
            return {"deleted": key}
    raise HTTPException(status_code=404, detail="key not found")


@app.get("/admin/licenses")
def list_licenses(user=Depends(get_current_user)):
    with get_session() as s:
        stmt = select(LicenseModel)
        items = s.exec(stmt).all()
        return {"licenses": [dict(id=i.id, key=i.key, package=i.package) for i in items]}


@app.post('/admin/offers/generate')
def gen_offer(payload: dict, user=Depends(get_current_user)):
    code = str(uuid.uuid4())
    offer = OfferModel(code=code, package=payload.get('pkg', 'standard'))
    with get_session() as s:
        s.add(offer)
        s.commit()
        s.refresh(offer)
    return {"code": offer.code, "package": offer.package}


@app.post('/admin/offers/deactivate')
def deactivate_offer(payload: dict, user=Depends(get_current_user)):
    code = payload.get('code')
    with get_session() as s:
        stmt = select(OfferModel).where(OfferModel.code == code)
        offer = s.exec(stmt).first()
        if offer:
            offer.active = False
            s.add(offer)
            s.commit()
            return {"deactivated": code}
    raise HTTPException(status_code=404, detail="offer not found")


@app.get('/admin/offers')
def list_offers(user=Depends(get_current_user)):
    with get_session() as s:
        stmt = select(OfferModel)
        items = s.exec(stmt).all()
        return {"offers": [dict(id=i.id, code=i.code, package=i.package, active=i.active) for i in items]}


@app.post('/admin/offers/redeem')
def redeem_offer(payload: dict, user=Depends(get_current_user)):
    code = payload.get('code')
    device_id = payload.get('device_id')
    if not code or not device_id:
        raise HTTPException(status_code=400, detail='code and device_id required')
    with get_session() as s:
        stmt = select(OfferModel).where(OfferModel.code == code, OfferModel.active == True)
        offer = s.exec(stmt).first()
        if not offer:
            raise HTTPException(status_code=404, detail='offer not found or inactive')
        lic_key = str(uuid.uuid4())
        lic = LicenseModel(key=lic_key, package=offer.package)
        s.add(lic)
        s.commit()
        s.refresh(lic)
        dev = Device(device_id=device_id, license_key=lic.key)
        s.add(dev)
        s.commit()
        return {"license_key": lic.key, "package": lic.package, "device_id": dev.device_id}


@app.post('/devices/register')
def register_device(body: dict, user=Depends(get_current_user)):
    device_id = body.get('device_id')
    key = body.get('key')
    if not device_id or not key:
        raise HTTPException(status_code=400, detail='device_id and key required')
    from models import Device
    with get_session() as s:
        # validate license
        stmt = select(LicenseModel).where(LicenseModel.key == key)
        lic = s.exec(stmt).first()
        if not lic:
            raise HTTPException(status_code=404, detail='license not found')
        # count existing devices
        dstmt = select(Device).where(Device.license_key == key)
        reg = s.exec(dstmt).all()
        if len(reg) >= (lic.devices_allowed or 1):
            raise HTTPException(status_code=403, detail='device limit reached')
        dev = Device(device_id=device_id, license_key=key)
        s.add(dev)
        s.commit()
        s.refresh(dev)
        return {"device_id": dev.device_id}


@app.post('/licenses/validate')
def validate_license(body: dict):
    key = body.get('key')
    device = body.get('device_id')
    signature = body.get('signature')
    if not key or not device:
        raise HTTPException(status_code=400, detail='key and device_id required')
    # verify provided signature to reduce cloning
    if not signature or not verify_signed(key, signature):
        raise HTTPException(status_code=403, detail='invalid signature')
    from models import Device
    with get_session() as s:
        dstmt = select(Device).where(Device.device_id == device, Device.license_key == key)
        found = s.exec(dstmt).first()
        return {"valid": bool(found)}


@app.post('/devices/heartbeat')
def device_heartbeat(body: dict):
    device = body.get('device_id')
    if not device:
        raise HTTPException(status_code=400, detail='device_id required')
    from models import Device
    from datetime import datetime
    with get_session() as s:
        d = s.exec(select(Device).where(Device.device_id == device)).first()
        if not d:
            raise HTTPException(status_code=404, detail='device not registered')
        d.last_seen = datetime.utcnow()
        s.add(d)
        s.commit()
        return {"device_id": d.device_id, "last_seen": d.last_seen.isoformat()}


@app.get('/integrity/check')
def integrity_check():
    # compute SHA256 of this file and return it; in production this should be compared to a signed value
    import pathlib
    p = pathlib.Path(__file__)
    h = file_sha256(str(p))
    return {"file": str(p), "sha256": h}
