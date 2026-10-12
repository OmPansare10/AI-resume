import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

from routes.upload import router as upload_router
from services.ai_service import get_ollama_client_info, OLLAMA_MODEL


app = FastAPI(
    title="AI Resume Tailor API",
    description="Backend API for local Ollama-powered resume tailoring",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(
    upload_router,
    prefix="/api"
)


@app.get("/")
def home():
    return {
        "message": "AI Resume Tailor API is running",
        "version": "1.0.0"
    }


@app.get("/api/health")
def health_check():
    ollama_info = get_ollama_client_info()
    return {
        "status": "healthy",
        "ollama": ollama_info["running"],
        "model": ollama_info["model_configured"],
        "model_found": ollama_info["model_found"],
        "available_models": ollama_info["available_models"],
        "error": ollama_info.get("error")
    }