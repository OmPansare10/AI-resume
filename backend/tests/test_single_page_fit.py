import sys
from pathlib import Path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import unittest
import pymupdf as fitz
from services.resume_tailor import (
    parse_master_resume_structure,
    tailor_resume_intelligently,
    edit_tailored_resume
)
from services.resume_generator import generate_pdf, generate_docx

SAMPLE_RESUME = """OM PANSARE
om.pansare10@gmail.com | 91+9284975854 | Pune

EDUCATION
Smt. Kashibai Navale College of Engineering — Pune, Maharashtra 2023–2026
Bachelor of Engineering in ENTC 8.35
Diploma in Computer Engineering 80%

ROLES OF RESPONSIBILITY
Java Developer Intern |Mass IT Solution                  Jan 2025 – Mar 2025
• Developed Java desktop applications using Java, MySQL, and JDBC with OOP principles for reliable and maintainable software.
• Performed software testing, debugging, and SQL query validation to identify and resolve application issues.
• Validated CRUD operations, database functionality, and application performance to improve software quality.

IJava Backend Intern | Infaneat Digital Marketing and Web Media     Jul 2022 – Sep 2022
• Developed authentication and backend features using Java, JSP, Servlets, MySQL, and JDBC.
• Performed functional testing, debugging, and SQL validation to identify and resolve application issues.
• Validated CRUD operations, database accuracy, and application workflows to improve software quality.

PROJECTS
Task Management Application | Java, Spring Boot, PostgreSQL
• Developed task management system with REST APIs.
• Implemented JWT authentication and PostgreSQL database queries.
"""

SAMPLE_JD = """We are looking for a Software Engineer with experience in Python, FastAPI, PostgreSQL, Redis, and Docker.
You will build RESTful microservices, optimize database schemas, and write automated tests."""


class TestSinglePageFit(unittest.TestCase):

    def test_similar_to_1_page_instruction(self):
        tailored = tailor_resume_intelligently(SAMPLE_JD, SAMPLE_RESUME)
        content = tailored["tailored_content"]

        # User instruction matching their exact prompt
        instruction = "i wanyt similar to the 1 page resume"
        edit_result = edit_tailored_resume(
            resume_content=content,
            instruction=instruction,
            original_resume_text=SAMPLE_RESUME,
            jd_text=SAMPLE_JD
        )
        updated = edit_result["updated_resume"]

        # Verify flags
        self.assertTrue(updated.get("single_page"))
        self.assertTrue(updated.get("compact_layout"))

        # Verify internships preserved with clean names
        exp = updated.get("experience", [])
        self.assertGreaterEqual(len(exp), 2)
        self.assertEqual(exp[0]["role"], "Java Developer Intern")
        self.assertEqual(exp[0]["company"], "Mass IT Solution")
        self.assertEqual(exp[1]["role"], "Java Backend Intern")
        self.assertEqual(exp[1]["company"], "Infaneat Digital Marketing and Web Media")

        # Verify bullet points are non-empty and formatted
        for job in exp:
            self.assertGreaterEqual(len(job["bullets"]), 2)

    def test_pdf_generation_is_single_page(self):
        tailored = tailor_resume_intelligently(SAMPLE_JD, SAMPLE_RESUME)
        content = tailored["tailored_content"]
        edit_result = edit_tailored_resume(
            resume_content=content,
            instruction="similar to the 1 page resume",
            original_resume_text=SAMPLE_RESUME,
            jd_text=SAMPLE_JD
        )
        updated = edit_result["updated_resume"]

        pdf_path = generate_pdf(updated)
        self.assertTrue(pdf_path.exists())

        doc = fitz.open(str(pdf_path))
        self.assertEqual(len(doc), 1, f"Expected 1 page but got {len(doc)} pages")
        doc.close()

    def test_docx_generation_is_valid(self):
        tailored = tailor_resume_intelligently(SAMPLE_JD, SAMPLE_RESUME)
        content = tailored["tailored_content"]
        content["single_page"] = True
        docx_path = generate_docx(content)
        self.assertTrue(docx_path.exists())


if __name__ == "__main__":
    unittest.main()

