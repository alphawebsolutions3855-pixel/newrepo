from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, nullable=False)
    hashed_password: str
    is_admin: bool = False

class License(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    key: str = Field(index=True, nullable=False)
    package: Optional[str] = None
    devices_allowed: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Offer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, nullable=False)
    package: Optional[str] = None
    expires_at: Optional[datetime] = None
    active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Post(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    body: str
    account_type: Optional[str] = 'old'
    batch_id: Optional[int] = Field(default=None, foreign_key='batch.id')
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published: bool = False

class Draft(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    body: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Batch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Handler(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    selector: str
    field_type: Optional[str]
    last_seen: datetime = Field(default_factory=datetime.utcnow)
    status: Optional[str] = 'active'
    fail_count: int = 0
    last_error: Optional[str] = None

class Device(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    device_id: str = Field(index=True)
    license_key: Optional[str] = None
    registered_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen: Optional[datetime] = None

class ScheduledJob(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    job_id: str
    payload: Optional[str]
    run_at: Optional[datetime]
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ErrorLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    selector: Optional[str]
    error: str
    occurred_at: datetime = Field(default_factory=datetime.utcnow)


class FBBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: Optional[str]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    fired: bool = False


class FBPostItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: Optional[int] = Field(default=None, foreign_key="fbbatch.id")
    message: str
    link: Optional[str] = None
    media_urls: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    published_id: Optional[str] = None
    retry_count: int = 0
    last_attempt: Optional[datetime] = None
    next_attempt_at: Optional[datetime] = None
    status: str = 'pending'  # pending, published, failed, retrying
