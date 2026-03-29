from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import socketio
from fastapi import FastAPI, HTTPException, Request
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel
from bson import ObjectId
import bcrypt
import jwt as pyjwt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# MongoDB
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Socket.IO
sio = socketio.AsyncServer(async_mode='asgi', cors_allowed_origins='*')

# FastAPI
fastapi_app = FastAPI()

# JWT config
JWT_SECRET = os.environ.get('JWT_SECRET', 'no2-viewer-secret-key-change-in-production')
JWT_ALGORITHM = 'HS256'


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))


def create_access_token(user_id: str, username: str) -> str:
    payload = {
        'sub': user_id,
        'username': username,
        'exp': datetime.now(timezone.utc) + timedelta(hours=24),
        'type': 'access'
    }
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request):
    token = request.cookies.get('access_token')
    if not token:
        auth = request.headers.get('Authorization', '')
        if auth.startswith('Bearer '):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail='Not authenticated')
    try:
        payload = pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        if payload.get('type') != 'access':
            raise HTTPException(status_code=401, detail='Invalid token type')
        user = await db.users.find_one({'_id': ObjectId(payload['sub'])})
        if not user:
            raise HTTPException(status_code=401, detail='User not found')
        return {
            'id': str(user['_id']),
            'email': user.get('email', ''),
            'name': user.get('name', ''),
            'role': user.get('role', 'user')
        }
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expired')
    except pyjwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail='Invalid token')


# Pydantic models
class LoginRequest(BaseModel):
    email: str
    password: str


class AnalysisRequest(BaseModel):
    polygon: dict
    date: str


# Auth endpoints
@fastapi_app.post('/api/auth/login')
async def login(data: LoginRequest):
    from fastapi.responses import JSONResponse
    user = await db.users.find_one({'email': data.email.strip()})
    if not user or not verify_password(data.password, user['password_hash']):
        raise HTTPException(status_code=401, detail='Invalid credentials')

    user_id = str(user['_id'])
    token = create_access_token(user_id, user.get('name', ''))

    response = JSONResponse(content={
        'id': user_id,
        'email': user.get('email', ''),
        'name': user.get('name', ''),
        'role': user.get('role', 'user'),
        'token': token
    })
    response.set_cookie(
        key='access_token', value=token, httponly=True,
        secure=False, samesite='lax', max_age=86400, path='/'
    )
    return response


@fastapi_app.post('/api/auth/logout')
async def logout():
    from fastapi.responses import JSONResponse
    response = JSONResponse(content={'message': 'Logged out'})
    response.delete_cookie('access_token', path='/')
    return response


@fastapi_app.get('/api/auth/me')
async def get_me(request: Request):
    user = await get_current_user(request)
    return user


# Analysis endpoints
@fastapi_app.post('/api/analysis/start')
async def start_analysis(data: AnalysisRequest, request: Request):
    user = await get_current_user(request)

    # Validate polygon structure
    if not data.polygon or 'coordinates' not in data.polygon:
        raise HTTPException(status_code=422, detail='Invalid polygon: missing coordinates')
    coords = data.polygon.get('coordinates', [])
    if not coords or not coords[0] or len(coords[0]) < 4:
        raise HTTPException(status_code=422, detail='Invalid polygon: need at least 3 vertices')

    analysis_id = str(uuid.uuid4())

    analysis_doc = {
        'analysis_id': analysis_id,
        'user_id': user['id'],
        'polygon': data.polygon,
        'date': data.date,
        'status': 'running',
        'agents': {
            'data_fetcher': 'pending',
            'stats_analyzer': 'pending',
            'trend_analyzer': 'pending',
            'recommendation_generator': 'pending'
        },
        'created_at': datetime.now(timezone.utc).isoformat(),
        'no2_data': None,
        'statistics': None,
        'trend_data': None,
        'recommendations': None
    }
    await db.analyses.insert_one(analysis_doc)

    from agents import run_analysis_pipeline
    asyncio.create_task(run_analysis_pipeline(analysis_id, data.polygon, data.date))

    return {'analysis_id': analysis_id, 'status': 'running'}


@fastapi_app.get('/api/analysis/{analysis_id}')
async def get_analysis(analysis_id: str, request: Request):
    await get_current_user(request)
    doc = await db.analyses.find_one({'analysis_id': analysis_id}, {'_id': 0})
    if not doc:
        raise HTTPException(status_code=404, detail='Analysis not found')
    return doc


@fastapi_app.get('/api/analyses')
async def get_analyses(request: Request):
    user = await get_current_user(request)
    docs = await db.analyses.find(
        {'user_id': user['id']}, {'_id': 0}
    ).sort('created_at', -1).to_list(50)
    return docs


# Socket.IO events
@sio.event
async def connect(sid, environ):
    logger.info(f'Socket.IO client connected: {sid}')


@sio.event
async def disconnect(sid):
    logger.info(f'Socket.IO client disconnected: {sid}')


@sio.event
async def join_analysis(sid, data):
    room = data.get('analysis_id')
    if room:
        await sio.enter_room(sid, room)
        logger.info(f'Client {sid} joined analysis room {room}')


# Admin seeding
async def seed_admin():
    admin_email = os.environ.get('ADMIN_EMAIL', 'sarvesh_pc')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'sarvesh_pc@06')

    existing = await db.users.find_one({'email': admin_email})
    if existing is None:
        hashed = hash_password(admin_password)
        await db.users.insert_one({
            'email': admin_email,
            'password_hash': hashed,
            'name': 'Sarvesh',
            'role': 'admin',
            'created_at': datetime.now(timezone.utc).isoformat()
        })
        logger.info(f'Admin user created: {admin_email}')
    elif not verify_password(admin_password, existing['password_hash']):
        await db.users.update_one(
            {'email': admin_email},
            {'$set': {'password_hash': hash_password(admin_password)}}
        )
        logger.info(f'Admin password updated: {admin_email}')

    await db.users.create_index('email', unique=True)
    await db.analyses.create_index('analysis_id', unique=True)

    os.makedirs('/app/memory', exist_ok=True)
    with open('/app/memory/test_credentials.md', 'w') as f:
        f.write('# Test Credentials\n\n')
        f.write(f'## Admin\n- Email: {admin_email}\n- Password: {admin_password}\n- Role: admin\n\n')
        f.write('## Auth Endpoints\n- POST /api/auth/login\n- POST /api/auth/logout\n- GET /api/auth/me\n\n')
        f.write('## Analysis Endpoints\n- POST /api/analysis/start\n- GET /api/analysis/{analysis_id}\n- GET /api/analyses\n')


@fastapi_app.on_event('startup')
async def startup():
    await seed_admin()
    from agents import set_sio
    set_sio(sio)
    logger.info('Server started successfully')


@fastapi_app.on_event('shutdown')
async def shutdown():
    client.close()


# CORS
fastapi_app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# Wrap FastAPI with Socket.IO
socket_app = socketio.ASGIApp(sio, other_asgi_app=fastapi_app, socketio_path='/api/socket.io')
app = socket_app
