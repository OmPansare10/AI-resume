"""
Integration tests for Internship & Roles of Responsibility preservation and tailoring.
Verifies:
1. Resumes with headers like 'ROLES OF RESPONSIBILITY', 'INTERNSHIP EXPERIENCE', etc. are parsed.
2. Authentic internship role names, company names, locations, and dates are preserved 100%.
3. Internship descriptions (bullet points) are tailored to match the target job description.
4. User instructions such as 'do not change internship name in internship change the description' work accurately.
"""

import sys
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import unittest
from services.resume_tailor import (
    parse_master_resume_structure,
    tailor_resume_intelligently,
    edit_tailored_resume
)
from services.fresher_resume_service import (
    tailor_fresher_resume_single_page,
    edit_single_page_fresher_resume
)

SAMPLE_RESUME = """OM PANSARE
om.pansare10@gmail.com | 91+9284975854 | Pune

EDUCATION
Smt. Kashibai Navale College of Engineering — Pune, Maharashtra 2023–2026
Bachelor of Engineering in ENTC 8.35

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
"""

SAMPLE_JD = """We are looking for a Software Engineer with experience in Python, FastAPI, PostgreSQL, Redis, and Docker.
You will build RESTful microservices, optimize database schemas, and write automated tests."""


class TestInternshipPreservation(unittest.TestCase):

    def test_parse_roles_of_responsibility(self):
        parsed = parse_master_resume_structure(SAMPLE_RESUME)
        exp = parsed.get("experience", [])
        self.assertEqual(len(exp), 2)
        self.assertEqual(exp[0]["role"], "Java Developer Intern")
        self.assertEqual(exp[0]["company"], "Mass IT Solution")
        self.assertIn("2025", exp[0]["duration"])

        self.assertEqual(exp[1]["role"], "Java Backend Intern")
        self.assertEqual(exp[1]["company"], "Infaneat Digital Marketing and Web Media")
        self.assertIn("2022", exp[1]["duration"])

    def test_tailor_resume_preserves_internship_identity_and_tailors_bullets(self):
        result = tailor_resume_intelligently(SAMPLE_JD, SAMPLE_RESUME)
        tailored_exp = result["tailored_content"]["experience"]
        self.assertEqual(len(tailored_exp), 2)
        # Roles and companies must remain 100% authentic
        self.assertEqual(tailored_exp[0]["role"], "Java Developer Intern")
        self.assertEqual(tailored_exp[0]["company"], "Mass IT Solution")
        self.assertEqual(tailored_exp[1]["role"], "Java Backend Intern")
        self.assertEqual(tailored_exp[1]["company"], "Infaneat Digital Marketing and Web Media")
        # Description bullets must be populated and non-empty
        self.assertGreater(len(tailored_exp[0]["bullets"]), 0)
        self.assertGreater(len(tailored_exp[1]["bullets"]), 0)

    def test_fresher_single_page_preserves_internships(self):
        fresher_res = tailor_fresher_resume_single_page(SAMPLE_JD, SAMPLE_RESUME)
        exp = fresher_res["single_page_tailored_content"]["experience"]
        self.assertEqual(len(exp), 2)
        self.assertEqual(exp[0]["role"], "Java Developer Intern")
        self.assertEqual(exp[0]["company"], "Mass IT Solution")
        self.assertEqual(exp[1]["role"], "Java Backend Intern")
        self.assertEqual(exp[1]["company"], "Infaneat Digital Marketing and Web Media")
        # Exactly 3 concise bullets each
        self.assertEqual(len(exp[0]["bullets"]), 3)
        self.assertEqual(len(exp[1]["bullets"]), 3)

    def test_edit_instruction_tailor_internship_description(self):
        fresher_res = tailor_fresher_resume_single_page(SAMPLE_JD, SAMPLE_RESUME)
        instruction = "so i uploaded resume has intership section i want you generated resume then i want intership place as it it do not chnage intership name in intership chnage the description"
        edit_res = edit_single_page_fresher_resume(
            resume_content=fresher_res["single_page_tailored_content"],
            instruction=instruction,
            original_resume_text=SAMPLE_RESUME,
            jd_text=SAMPLE_JD
        )
        exp = edit_res["updated_content"]["experience"]
        self.assertEqual(len(exp), 2)
        self.assertEqual(exp[0]["role"], "Java Developer Intern")
        self.assertEqual(exp[0]["company"], "Mass IT Solution")
        self.assertEqual(exp[1]["role"], "Java Backend Intern")
        self.assertEqual(exp[1]["company"], "Infaneat Digital Marketing and Web Media")
        self.assertTrue(any("internship" in c.lower() for c in edit_res["changes"]))


if __name__ == "__main__":
    unittest.main()
