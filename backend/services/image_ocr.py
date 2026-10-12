import asyncio
import base64
import io
import logging
import re
from typing import Optional, Tuple
from PIL import Image

logger = logging.getLogger(__name__)

async def _run_winocr(pil_img: Image.Image) -> str:
    try:
        import winocr
        res = await winocr.recognize_pil(pil_img, "en")
        return (res.text or "").strip()
    except Exception as e:
        logger.warning(f"winocr recognition failed: {e}")
        return ""

def extract_text_from_image_b64(image_data: str) -> str:
    """
    Extracts text from a base64 encoded image string using local Windows OCR.
    Handles data URLs (e.g. 'data:image/png;base64,...') or raw base64.
    """
    if not image_data or not isinstance(image_data, str):
        return ""

    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        raw_bytes = base64.b64decode(image_data)
        pil_img = Image.open(io.BytesIO(raw_bytes))

        # Convert palette/RGBA if needed to RGB for OCR consistency
        if pil_img.mode in ("P", "RGBA", "LA"):
            pil_img = pil_img.convert("RGB")

        # Run winocr asynchronously
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In already running event loop
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(lambda: asyncio.run(_run_winocr(pil_img)))
                    text = future.result(timeout=10)
            else:
                text = loop.run_until_complete(_run_winocr(pil_img))
        except RuntimeError:
            text = asyncio.run(_run_winocr(pil_img))

        return text
    except Exception as e:
        logger.error(f"Error in extract_text_from_image_b64: {e}")
        return ""

def is_photo_update_request(instruction: str, ocr_text: str = "") -> bool:
    """
    Detects if the user wants to update their resume profile picture.
    """
    inst = instruction.lower()
    photo_phrases = [
        "profile photo", "profile picture", "resume photo", "my photo",
        "my picture", "use this image as my photo", "set photo", "change photo",
        "update photo", "add photo", "set as photo", "use as photo", "profile pic",
        "headshot", "avatar", "candidate photo"
    ]
    return any(p in inst for p in photo_phrases)


def is_project_photo_request(instruction: str, ocr_text: str = "") -> bool:
    """
    Detects if the user wants to add/update a project from an image or attach the image to a project.
    """
    inst = instruction.lower()
    proj_phrases = [
        "in project", "to project", "for project", "want this in project",
        "put this in project", "add this in project", "add this to project",
        "add project", "my project", "create project", "new project",
        "project screenshot", "project image", "project photo",
        "change project", "update project", "use for project", "use as project",
        "projects", "github", "portfolio project"
    ]
    if any(p in inst for p in proj_phrases):
        return True

    # Also check if ocr text heavily indicates a software project and no profile photo requested
    if ocr_text and not is_photo_update_request(instruction):
        ocr_lower = ocr_text.lower()
        tech_cues = ["github.com", "repository", "technologies:", "tech stack", "flask", "react", "django", "fastapi", "spring boot"]
        if any(c in ocr_lower for c in tech_cues) and ("project" in inst or not inst.strip()):
            return True

    return False


def extract_multiple_images_ocr(images_data: list) -> list:
    """
    Extracts text from multiple base64 image strings.
    Returns list of dicts: [{'index': i, 'image_data': str, 'text': str}]
    """
    results = []
    for i, img_b64 in enumerate(images_data):
        if not img_b64 or not isinstance(img_b64, str):
            continue
        extracted_text = extract_text_from_image_b64(img_b64)
        results.append({
            "index": i,
            "image_data": img_b64,
            "text": extracted_text
        })
    return results
