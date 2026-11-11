import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.resume_tailor import (
    align_experience_for_jd,
    is_jd_demanding_experience,
    edit_tailored_resume,
    tailor_resume_intelligently
)
from services.fresher_resume_service import (
    edit_single_page_fresher_resume,
    tailor_fresher_resume_single_page
)

SAMPLE_RESUME = {
    "name": "Om Pansare",
    "contact": {
        "email": "om.pansare10@gmail.com",
        "phone": "+9284975854",
        "location": "Pune, Maharashtra",
        "linkedin": "LinkedIn",
        "github": "GitHub"
    },
    "summary": "Results-driven software engineer specialized in building scalable backend services with Python, FastAPI, and PostgreSQL.",
    "experience": [
        {
            "role": "Software Engineer Intern",
            "company": "Automaton AI Infosystem",
            "duration": "Sep 2026 - Ongoing",
            "bullets": [
                "Engineered and maintained backend application features and RESTful endpoints using Software Engineer, improving modular architecture.",
                "Executed database schema operations, CRUD workflows, and query validation in PostgreSQL, improving data retrieval reliability.",
                "Conducted comprehensive software testing, debugging, and API validation, streamlining deployment reliability across development sprints."
            ]
        },
        {
            "role": "Java Developer Intern",
            "company": "Mass IT Solution",
            "duration": "Jan 2025 – Mar 2025",
            "bullets": [
                "Ported legacy Java desktop utilities to Python CLI tools.",
                "Refactored data-access layer to use PostgreSQL via psycopg2."
            ]
        }
    ],
    "projects": [
        {
            "name": "Task Management Application",
            "technologies": "Python, FastAPI, PostgreSQL, Redis, MySQL, Docker, CI/CD",
            "bullets": [
                "Architected scalable microservices using FastAPI.",
                "Optimized database schemas with PostgreSQL.",
                "Containerized microservices using Docker."
            ]
        }
    ],
    "skills": {
        "Targeted JD Stack": ["Python", "FastAPI", "PostgreSQL"],
        "Databases & Storage": ["PostgreSQL", "Redis", "MySQL"]
    },
    "education": [
        {
            "degree": "Bachelor of Engineering",
            "institution": "SKNCOE",
            "duration": "2023 - 2026"
        }
    ]
}

JD_EXPERIENCED = """
Job Title: Python Software Engineer
Location: Pune, India
Requirements:
- 2+ years of hands-on professional work experience building scalable microservices.
- Proficiency in Python, FastAPI, and PostgreSQL.
- Experience with Docker, Kafka, and Redis caching.
"""

JD_FRESHER = """
Job Title: Software Developer - Fresher / Intern
Location: Pune, India
Requirements:
- Looking for motivated fresh graduates or interns.
- 0-1 years of experience, strong problem solving skills in Python or Java.
- Bachelor's degree in CS or related field.
"""

USER_INSTRUCTION = (
    "here also i want if job for experience then instead of Automaton AI Infosystem i want Webcrypt Technology "
    "and remove the intern text from Software Engineer Intern only take Software Engineer and strating from april 2025 - ongoing "
    "when you do this when job discribtion mention they want experinece employee only that case if job for fresdher the dont change "
    "comapany name in that case i want my intership experience which is Software Engineer Intern - Automaton AI Infosystemthis"
)

class TestWebcryptExperienceSwitch(unittest.TestCase):
    def test_align_experience_experienced_jd(self):
        """When JD requires experience, Automaton switches to Webcrypt Technology, Software Engineer, April 2025 - Ongoing."""
        aligned = align_experience_for_jd(SAMPLE_RESUME["experience"], demands_exp=True)
        self.assertEqual(aligned[0]["company"], "Webcrypt Technology")
        self.assertEqual(aligned[0]["role"], "Software Engineer")
        self.assertEqual(aligned[0]["duration"], "April 2025 - Ongoing")
        # Ensure 'using Software Engineer' awkward bullet is cleaned
        self.assertNotIn("using Software Engineer", aligned[0]["bullets"][0])
        # Ensure subsequent internships are untouched
        self.assertEqual(aligned[1]["company"], "Mass IT Solution")
        self.assertEqual(aligned[1]["role"], "Java Developer Intern")

    def test_align_experience_fresher_jd(self):
        """When JD is for a fresher, Automaton AI Infosystem and Software Engineer Intern are preserved intact."""
        aligned = align_experience_for_jd(SAMPLE_RESUME["experience"], demands_exp=False)
        self.assertEqual(aligned[0]["company"], "Automaton AI Infosystem")
        self.assertEqual(aligned[0]["role"], "Software Engineer Intern")
        self.assertEqual(aligned[0]["duration"], "Sep 2026 - Ongoing")
        self.assertEqual(aligned[1]["company"], "Mass IT Solution")

    def test_edit_tailored_resume_with_user_instruction_experienced(self):
        """edit_tailored_resume updates to Webcrypt Technology when JD requires experience."""
        res = edit_tailored_resume(
            resume_content=SAMPLE_RESUME,
            instruction=USER_INSTRUCTION,
            jd_text=JD_EXPERIENCED
        )
        updated = res["updated_content"]
        self.assertEqual(updated["experience"][0]["company"], "Webcrypt Technology")
        self.assertEqual(updated["experience"][0]["role"], "Software Engineer")
        self.assertEqual(updated["experience"][0]["duration"], "April 2025 - Ongoing")
        self.assertIn("Webcrypt Technology", str(res["changes"]))

    def test_edit_tailored_resume_with_user_instruction_fresher(self):
        """edit_tailored_resume preserves Automaton AI Infosystem when JD is for a fresher."""
        res = edit_tailored_resume(
            resume_content=SAMPLE_RESUME,
            instruction=USER_INSTRUCTION,
            jd_text=JD_FRESHER
        )
        updated = res["updated_content"]
        self.assertEqual(updated["experience"][0]["company"], "Automaton AI Infosystem")
        self.assertEqual(updated["experience"][0]["role"], "Software Engineer Intern")

    def test_edit_single_page_fresher_resume_experienced(self):
        """edit_single_page_fresher_resume updates to Webcrypt Technology when JD requires experience."""
        res = edit_single_page_fresher_resume(
            resume_content=SAMPLE_RESUME,
            instruction=USER_INSTRUCTION,
            jd_text=JD_EXPERIENCED
        )
        updated = res["updated_content"]
        self.assertEqual(updated["experience"][0]["company"], "Webcrypt Technology")
        self.assertEqual(updated["experience"][0]["role"], "Software Engineer")
        self.assertEqual(updated["experience"][0]["duration"], "April 2025 - Ongoing")

    def test_edit_single_page_fresher_resume_fresher(self):
        """edit_single_page_fresher_resume preserves Automaton AI Infosystem when JD is for a fresher."""
        res = edit_single_page_fresher_resume(
            resume_content=SAMPLE_RESUME,
            instruction=USER_INSTRUCTION,
            jd_text=JD_FRESHER
        )
        updated = res["updated_content"]
        self.assertEqual(updated["experience"][0]["company"], "Automaton AI Infosystem")
        self.assertEqual(updated["experience"][0]["role"], "Software Engineer Intern")


if __name__ == "__main__":
    unittest.main()
