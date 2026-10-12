from pathlib import Path

import pymupdf as fitz
from docx import Document


def extract_pdf_text(file_path: str) -> str:
    """
    Extract text from a PDF file.
    """

    text = ""

    document = fitz.open(file_path)

    for page in document:
        text += page.get_text("text", sort=True) + "\n"

    document.close()

    return text.strip()


def extract_docx_text(file_path: str) -> str:
    """
    Extract text from a DOCX file.
    """

    document = Document(file_path)

    paragraphs = []

    for paragraph in document.paragraphs:
        if paragraph.text.strip():
            paragraphs.append(paragraph.text.strip())

    return "\n".join(paragraphs)


def extract_resume_text(file_path: str) -> str:
    """
    Detect resume file type and extract text.
    """

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(file_path)

    elif extension == ".docx":
        return extract_docx_text(file_path)

    else:
        raise ValueError(
            f"Unsupported resume format: {extension}"
        )
