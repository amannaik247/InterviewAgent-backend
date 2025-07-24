from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os
import logging
import uuid
from fastapi import FastAPI, Request
from dependencies import get_user_id

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from routes.resume import router as resume_router
from routes.transcription import transcription_router
from routes.job import job_router
from routes.question import question_router
from routes.evaluate import router as evaluate_router

app = FastAPI()

@app.middleware("http")
async def add_user_id_header(request: Request, call_next):
    user_id_from_header = request.headers.get("X-User-ID")
    if not user_id_from_header:
        user_id = str(uuid.uuid4())
        logger.info(f"Generated new user_id: {user_id}")
    else:
        user_id = user_id_from_header
        logger.info(f"Using user_id from header: {user_id}")

    request.state.user_id = user_id
    response = await call_next(request)
    return response

# Set session creation secret


# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://interview-agent-frontend.vercel.app", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

app.include_router(resume_router)
app.include_router(transcription_router)
app.include_router(job_router)
app.include_router(question_router)
app.include_router(evaluate_router)

@app.get("/")
def read_root():
    return {"message": "Interview API is running"}
