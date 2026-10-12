import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.resume_parser import extract_resume_text
from services.jd_parser import extract_jd_from_text, extract_jd_from_link
from services.ai_service import analyze_resume_against_jd, analyze_and_tailor_unified, get_ollama_client_info
from services.resume_tailor import (
    generate_tailored_resume,
    edit_tailored_resume,
    extract_contact_info,
    tailor_resume_intelligently
)
from services.resume_generator import generate_docx, generate_pdf

router = APIRouter()

# Directories
BACKEND_DIR = Path(__file__).resolve().parent.parent
UPLOAD_DIR = BACKEND_DIR / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".docx"}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15MB


# Pydantic Request Models
class AnalyzeRequest(BaseModel):
    jd_text: str = Field(..., min_length=10, description="Job description text")
    resume_text: str = Field(..., min_length=10, description="Master resume text")
    resume_filename: Optional[str] = Field("", description="Original resume filename")


class EditResumeRequest(BaseModel):
    resume_content: Dict[str, Any]
    instruction: Optional[str] = Field(default="", description="Instruction for AI modification")
    image_data: Optional[str] = Field(default=None, description="Base64 encoded image or screenshot")
    images_data: Optional[List[str]] = Field(default=None, description="List of multiple base64 encoded images or screenshots")
    original_resume_text: Optional[str] = ""
    jd_text: Optional[str] = ""


class DownloadDocxRequest(BaseModel):
    tailored_content: Optional[Dict[str, Any]] = None
    resume_data: Optional[Dict[str, Any]] = None


class DownloadPdfRequest(BaseModel):
    tailored_content: Optional[Dict[str, Any]] = None
    resume_data: Optional[Dict[str, Any]] = None


@router.post("/upload")
async def upload_resume(
    jd_method: str = Form(...),
    jd_text: str = Form(""),
    jd_link: str = Form(""),
    resume: UploadFile = File(...)
):
    """
    1. Validates JD method & extracts JD text
    2. Validates & safely saves Master Resume to backend/uploads
    3. Extracts resume text
    4. Returns extracted JD text and Master Resume text
    """
    # 1. Validate JD method
    if jd_method not in ["text", "link"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid JD method. Use 'text' or 'link'."
        )

    # 2. Process Job Description
    try:
        if jd_method == "text":
            if not jd_text or not jd_text.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Job Description cannot be empty."
                )
            processed_jd = extract_jd_from_text(jd_text)
        else:
            if not jd_link or not jd_link.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Job Description link cannot be empty."
                )
            if not (jd_link.startswith("http://") or jd_link.startswith("https://")):
                raise HTTPException(
                    status_code=400,
                    detail="Invalid Job Description URL. URL must start with http:// or https://"
                )
            try:
                processed_jd = extract_jd_from_link(jd_link)
            except Exception as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Could not retrieve the Job Description from this URL: {str(e)}"
                )

        if not processed_jd or len(processed_jd.strip()) < 20 or "javascript is disabled" in processed_jd.lower():
            raise HTTPException(
                status_code=400,
                detail=(
                    "Could not extract text from this job link because this website (e.g. Naukri, LinkedIn) "
                    "requires JavaScript or blocks automated scrapers. Please open the job page, copy the job description text, "
                    "and paste it into the 'Paste JD' tab."
                )
            )

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"Could not process Job Description: {error}"
        )

    # 3. Validate Resume file
    if not resume.filename:
        raise HTTPException(
            status_code=400,
            detail="Resume file is required."
        )

    clean_filename = Path(resume.filename).name
    extension = Path(clean_filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Only PDF and DOCX resumes are supported."
        )

    # 4. Save Master Resume securely
    resume_path = UPLOAD_DIR / clean_filename

    try:
        content = await resume.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Resume file exceeds the 15MB size limit."
            )
        if len(content) == 0:
            raise HTTPException(
                status_code=400,
                detail="Uploaded resume file is empty."
            )

        with open(resume_path, "wb") as buffer:
            buffer.write(content)

    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not save master resume: {error}"
        )

    # 5. Extract Resume Text
    try:
        extracted_text = extract_resume_text(str(resume_path))
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not extract text from the uploaded resume: {error}"
        )

    if not extracted_text or not extracted_text.strip():
        raise HTTPException(
            status_code=400,
            detail="Could not extract any text from the uploaded resume. Please verify the document is not an image scan."
        )

    # 6. Return processed data
    return {
        "message": "JD and Resume processed successfully",
        "jd_method": jd_method,
        "jd_text": processed_jd,
        "resume_filename": clean_filename,
        "resume_text": extracted_text
    }


@router.post("/analyze")
async def analyze_and_tailor(payload: AnalyzeRequest):
    """
    Sends JD and Master Resume text to local Ollama AI.
    Runs deep requirement analysis and generates tailored resume sections.
    """
    if not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="Job Description cannot be empty.")
    if not payload.resume_text.strip():
        raise HTTPException(status_code=400, detail="Master Resume text cannot be empty.")

    # 1. Check Ollama readiness
    health = get_ollama_client_info()
    if not health["running"]:
        raise HTTPException(
            status_code=503,
            detail="Ollama is not running. Please start Ollama on your machine and try again."
        )
    if not health["model_found"] and not health["available_models"]:
        raise HTTPException(
            status_code=503,
            detail=f"Configured Ollama model was not found. Please run 'ollama pull {health['model_configured']}'."
        )

    try:
        # High-speed zero-loss tailoring: preserves 100% authentic sections & weaves in target keywords (~10-15s)
        result = tailor_resume_intelligently(
            jd_text=payload.jd_text,
            resume_text=payload.resume_text,
            filename=payload.resume_filename or ""
        )
        return result

    except RuntimeError as re_err:
        raise HTTPException(status_code=502, detail=str(re_err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(err)}")


@router.post("/edit-resume")
async def edit_resume_endpoint(payload: EditResumeRequest):
    """
    Edit with AI: Modify tailored content based on user instructions and/or attached image(s)
    while strictly preserving Master Resume ground truth.
    """
    has_instruction = bool((payload.instruction or "").strip())
    has_images = bool(payload.image_data or (payload.images_data and len(payload.images_data) > 0))
    if not has_instruction and not has_images:
        raise HTTPException(status_code=400, detail="Please provide an instruction or attach an image.")

    try:
        result = edit_tailored_resume(
            resume_content=payload.resume_content,
            instruction=payload.instruction or "",
            original_resume_text=payload.original_resume_text or "",
            jd_text=payload.jd_text or "",
            image_data=payload.image_data,
            images_data=payload.images_data
        )
        return result
    except RuntimeError as re_err:
        raise HTTPException(status_code=502, detail=str(re_err))
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Edit with AI failed: {str(err)}")


@router.post("/download-docx")
async def download_docx_endpoint(payload: DownloadDocxRequest):
    """
    Generates a professional DOCX resume and returns it as a downloadable file.
    """
    content = payload.tailored_content or payload.resume_data
    if not content:
        raise HTTPException(status_code=400, detail="Tailored resume content is required.")

    try:
        file_path = generate_docx(content)
        if not file_path.exists():
            raise HTTPException(status_code=500, detail="Failed to locate generated document.")

        candidate_name = content.get("name", "Tailored_Resume")
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', candidate_name).strip('_')
        download_filename = f"{safe_name}_Tailored_Resume.docx"

        return FileResponse(
            path=str(file_path),
            filename=download_filename,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Could not generate DOCX: {str(err)}")


@router.post("/download-pdf")
async def download_pdf_endpoint(payload: DownloadPdfRequest):
    """
    Generates an executive-level, ATS-friendly PDF resume and returns it as a downloadable file.
    """
    content = payload.tailored_content or payload.resume_data
    if not content:
        raise HTTPException(status_code=400, detail="Tailored resume content is required.")

    try:
        file_path = generate_pdf(content)
        if not file_path.exists():
            raise HTTPException(status_code=500, detail="Failed to locate generated PDF document.")

        candidate_name = content.get("name", "Tailored_Resume")
        safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', candidate_name).strip('_')
        download_filename = f"{safe_name}_Tailored_Resume.pdf"

        return FileResponse(
            path=str(file_path),
            filename=download_filename,
            media_type="application/pdf"
        )
    except Exception as err:
        raise HTTPException(status_code=500, detail=f"Could not generate PDF: {str(err)}")

