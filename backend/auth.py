import asyncio
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from pymongo.errors import DuplicateKeyError
from database import db
from realtime import registry, rate_limit as request_limit

router = APIRouter(prefix='/auth')
hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
dummy = hasher.hash(secrets.token_urlsafe(20))


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(default='Commander', min_length=2, max_length=24)


class User(BaseModel):
    id: str
    name: str
    email: str


class Session(BaseModel):
    token: str
    user: User


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


async def authenticate(token):
    session = await db.sessions.find_one({'token_hash': digest(token), 'expires_at': {'$gt': datetime.now(timezone.utc)}}, {'_id': 0})
    if not session:
        raise HTTPException(401, 'Your session has expired. Please sign in again.')
    user = await db.users.find_one({'id': session['user_id'], 'deleting': {'$ne': True}}, {'_id': 0, 'password_hash': 0})
    if not user:
        raise HTTPException(401, 'Account not found.')
    return user


async def current_user(authorization: str = Header(default='')):
    if not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Please sign in to enter the war room.')
    return await authenticate(authorization[7:])


async def rate_limit(request, email):
    await request_limit(f'auth-ip:{request.client.host}', 100)
    now = datetime.now(timezone.utc)
    bucket = f'{request.client.host}:{email}:{int(now.timestamp()) // 60}'
    result = await db.auth_limits.find_one_and_update({'key': bucket}, {'$inc': {'count': 1}, '$set': {'expires_at': now + timedelta(minutes=2)}}, upsert=True, return_document=True, projection={'_id': 0})
    if result['count'] > 12:
        raise HTTPException(429, 'Too many attempts. Try again in one minute.')


async def issue(user):
    token = secrets.token_urlsafe(48)
    await db.sessions.insert_one({'token_hash': digest(token), 'user_id': user['id'], 'expires_at': datetime.now(timezone.utc) + timedelta(days=30)})
    return Session(token=token, user=User(**user))


@router.post('/register', response_model=Session)
async def register(body: Credentials, request: Request):
    email = str(body.email).lower().strip()
    await rate_limit(request, email)
    name = body.name.strip()
    if len(name) < 2:
        raise HTTPException(400, 'Choose a commander name with at least two characters.')
    user = {'id': str(uuid.uuid4()), 'email': email, 'name': name, 'password_hash': await asyncio.to_thread(hasher.hash, body.password)}
    try:
        await db.users.insert_one(user.copy())
    except DuplicateKeyError:
        raise HTTPException(409, 'An account with this email already exists.')
    return await issue(user)


@router.post('/login', response_model=Session)
async def login(body: Credentials, request: Request):
    email = str(body.email).lower().strip()
    await rate_limit(request, email)
    user = await db.users.find_one({'email': email, 'deleting': {'$ne': True}}, {'_id': 0})
    try:
        valid = await asyncio.to_thread(hasher.verify, user['password_hash'] if user else dummy, body.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not user or not valid:
        raise HTTPException(401, 'Email or password is incorrect.')
    return await issue(user)


@router.get('/me', response_model=User)
async def me(user=Depends(current_user)):
    return User(**user)


@router.post('/logout')
async def logout(authorization: str = Header(default='')):
    token_hash = digest(authorization.removeprefix('Bearer '))
    await db.sessions.delete_one({'token_hash': token_hash})
    await db.voice_tickets.delete_many({'session_hash': token_hash})
    await registry.revoke(session_hash=token_hash)
    return {'ok': True}


class DeleteAccount(BaseModel):
    password: str = Field(min_length=8, max_length=128)
    confirmation: str


@router.post('/delete-account')
async def delete_account(body: DeleteAccount, user=Depends(current_user)):
    await request_limit(f'delete-account:{user["id"]}', 5)
    if body.confirmation != 'DELETE':
        raise HTTPException(400, 'Type DELETE to confirm permanent account removal.')
    record = await db.users.find_one({'id': user['id']}, {'_id': 0})
    try:
        valid = bool(record) and await asyncio.to_thread(hasher.verify, record['password_hash'], body.password)
    except (VerificationError, InvalidHashError):
        valid = False
    if not valid:
        raise HTTPException(403, 'Password confirmation is incorrect.')
    await db.users.update_one({'id': user['id']}, {'$set': {'deleting': True}})
    from account_cleanup import cleanup_account
    try:
        await cleanup_account(user['id'])
    except Exception:
        return {'deleted': False, 'deletion_requested': True}
    return {'deleted': True}