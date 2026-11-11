import asyncio
import base64
import io
import logging
import re
from typing import Optional, Tuple
from PIL import Image, ImageEnhance, ImageFilter, ImageOps

logger = logging.getLogger(__name__)

async def _run_winocr(pil_img: Image.Image) -> str:
    try:
        import winocr
        res = await winocr.recognize_pil(pil_img, "en")
        return (res.text or "").strip()
    except Exception as e:
        logger.warning(f"winocr recognition failed: {e}")
        return ""


def _prepare_ocr_image(pil_img: Image.Image, high_contrast: bool = False) -> Image.Image:
    """
    Normalize alpha transparency onto white, invert dark-mode crops,
    upscale small tightly cropped snippets, and pad borders so Windows OCR
    reliably reads single-line and low-height screenshots.
    """
    if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
        rgba = pil_img.convert("RGBA")
        bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        bg.paste(rgba, mask=rgba.split()[3])
        work = bg.convert("RGB")
    elif pil_img.mode != "RGB":
        work = pil_img.convert("RGB")
    else:
        work = pil_img.copy()

    # Check outer corner/border brightness to handle dark-mode snippets cleanly
    gray = work.convert("L")
    w, h = gray.size
    sample_pts = [
        (0, 0),
        (max(0, w - 1), 0),
        (0, max(0, h - 1)),
        (max(0, w - 1), max(0, h - 1)),
        (w // 2, 0),
        (w // 2, max(0, h - 1)),
    ]
    edge_mean = sum(gray.getpixel(pt) for pt in sample_pts) / len(sample_pts)
    if edge_mean < 110:
        work = ImageOps.invert(work)

    # Upscale small/thin screenshots (e.g., 1-line 18px-60px tall bullet crops)
    scale = 1
    if h < 180 or w < 900:
        scale_h = max(1, (180 + max(1, h) - 1) // max(1, h))
        scale_w = max(1, (900 + max(1, w) - 1) // max(1, w))
        scale = min(4, max(2, scale_h, scale_w))
        max_side = max(w, h)
        while scale > 1 and max_side * scale > 3200:
            scale -= 1
    if scale > 1:
        work = work.resize((w * scale, h * scale), Image.Resampling.LANCZOS)

    if high_contrast:
        g = ImageOps.autocontrast(work.convert("L"))
        g = ImageEnhance.Sharpness(g).enhance(1.6)
        work = g.convert("RGB")

    # Add generous white margin around tightly cropped lines
    work = ImageOps.expand(work, border=48, fill=(255, 255, 255))
    return work


def _execute_ocr_sync(pil_img: Image.Image) -> str:
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(lambda: asyncio.run(_run_winocr(pil_img)))
                return future.result(timeout=10)
        return loop.run_until_complete(_run_winocr(pil_img))
    except RuntimeError:
        return asyncio.run(_run_winocr(pil_img))


def extract_text_from_image_b64(image_data: str) -> str:
    """
    Extracts text from a base64 encoded image string using local Windows OCR.
    Applies upscaling, alpha compositing, and border padding so even small
    single-line cropped screenshots extract accurately.
    """
    if not image_data or not isinstance(image_data, str):
        return ""

    try:
        if "," in image_data:
            image_data = image_data.split(",", 1)[1]

        raw_bytes = base64.b64decode(image_data)
        pil_img = Image.open(io.BytesIO(raw_bytes))

        # Primary pass: upscaled + padded clean image
        prepared = _prepare_ocr_image(pil_img, high_contrast=False)
        text = _execute_ocr_sync(prepared)

        # Fallback passes for noisy/blurry small crops
        if len(re.findall(r'[A-Za-z0-9]{2,}', text or "")) < 2:
            hi = _prepare_ocr_image(pil_img, high_contrast=True)
            hi_text = _execute_ocr_sync(hi)
            if len(hi_text.strip()) > len((text or "").strip()):
                text = hi_text

        if not (text or "").strip():
            rgb_raw = pil_img.convert("RGB") if pil_img.mode != "RGB" else pil_img
            text = _execute_ocr_sync(rgb_raw)

        return (text or "").strip()
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
