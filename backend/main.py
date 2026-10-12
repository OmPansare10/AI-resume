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
    allow_origins=["*"],
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
    ai_info = get_ollama_client_info()
    return {
        "status": "healthy",
        "ollama": ai_info["running"],
        "provider": ai_info.get("provider", "ollama"),
        "model": ai_info["model_configured"],
        "model_found": ai_info["model_found"],
        "available_models": ai_info["available_models"],
        "error": ai_info.get("error")
    }