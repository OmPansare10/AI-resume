import copy
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.fresher_resume_service import (  # noqa: E402
    edit_single_page_fresher_resume,
    tailor_fresher_resume_single_page,
)
from services.resume_tailor import (  # noqa: E402
    edit_tailored_resume,
    extract_target_jd_profile,
    tailor_resume_intelligently,
)


AI_ENGINEER_FRESHER_JD = """Role: AI Engineer – Fresher

Location: Viman Nagar, Pune | Work From Office

Experience:
0–1 year
Fresh graduates
Key Skills:
Python
AI / ML
GenAI
Agentic AI
MLOps
LLMs
AI Frameworks
Qualification:
Recent graduates in CS
Recent graduates in AI/ML
Recent graduates in Data Science
Recent graduates in related fields
Responsibilities:
Work on AI and Generative AI
Contribute to AI/ML initiatives
Apply Python in AI engineering tasks
Additional responsibilities:
Support GenAI and Agentic AI use cases
Work with MLOps practices
Use LLMs and AI frameworks
"""

NON_AI_BACKEND_JD = """Role: Software Engineer - Backend

Experience: 0-1 year (Freshers / New Graduates)
Key Skills: Python, FastAPI, PostgreSQL, Redis, Docker, REST APIs, CI/CD
Responsibilities:
- Design and build scalable backend microservices and RESTful APIs
- Optimize SQL queries and caching layers
"""

MASTER_RESUME_TEXT = """Om Pansare
om.pansare10@gmail.com | +91 92849 75854 | Pune, Maharashtra | LinkedIn | GitHub

SUMMARY
Software Engineer Intern with hands-on experience in Java, Python, Spring Boot, and REST APIs.

SKILLS
Languages: Java, Python, JavaScript, SQL, C++
Backend: Spring Boot, REST APIs, JDBC, JSP, Servlets
Frontend: React.js, HTML, CSS
Databases: MySQL, MongoDB
Testing: JUnit, TestNG, Selenium WebDriver, Postman, REST Assured

EXPERIENCE
Software Engineer Intern | Automaton AI Infosystem | Sep 2026 - Ongoing
- Developed and maintained software applications using Java, Spring Boot, REST APIs, Python, React.js, and databases.
- Developed and integrated RESTful APIs, implementing authentication, CRUD operations, database connectivity.
- Engineered core application business logic, integrating Java services with Spring Boot and RESTful APIs.

Java Developer Intern | Mass IT Solution | Jan 2025 - Mar 2025
- Developed Java desktop applications using Java, MySQL, and JDBC with OOP principles for reliable software.
- Performed software testing, debugging, and SQL query validation to identify and resolve application issues.
- Validated CRUD operations and application performance to improve software quality.

Java Backend Intern | Infaneat Digital Marketing and Web Media | Jul 2022 - Sep 2022
- Developed authentication and backend features using Java, JSP, Servlets, MySQL, and JDBC.
- Performed functional testing, debugging, and SQL validation to identify and resolve application issues.
- Validated CRUD operations, database accuracy, and application workflows to improve software quality.

PROJECTS
Task Management Application
- Built backend task management REST services with Java, Spring Boot, and MySQL.

Food Waste Management System
- Built food donation and inventory tracking web portal using Java and MySQL.

Meet.AI
- Built an AI meeting assistant prototype in Python.

EDUCATION
Smt. Kashibai Navale College of Engineering — Pune, Maharashtra | Bachelor of Engineering in ENTC - 8.35 | 2023-2026
Government Polytechnic Pune — Pune, Maharashtra | Diploma in Computer Engineering - 80% | 2020-2023

CERTIFICATIONS
- PCAP – Certified Associate in Python Programming (Python Institute)
"""


def _stale_backend_resume_dict():
    return {
        "name": "Om Pansare",
        "email": "om.pansare10@gmail.com",
        "phone": "+91 92849 75854",
        "location": "Pune, Maharashtra",
        "linkedin": "LinkedIn",
        "github": "GitHub",
        "job_title": "Software Engineer",
        "summary": (
            "Software Engineer with extensive hands-on internship experience architecting, building, "
            "and deploying scalable backend microservices and RESTful APIs using Python, FastAPI, "
            "and PostgreSQL. Proficient in Docker and CI/CD pipelines."
        ),
        "skills": {
            "Targeted JD Stack": ["Python", "FastAPI", "Docker", "REST APIs"],
            "Databases & Storage": ["PostgreSQL", "Redis"],
            "Languages": ["Java", "Python", "SQL"],
        },
        "experience": [
            {
                "role": "Software Engineer Intern",
                "company": "Automaton AI Infosystem",
                "duration": "Sep 2026 - Ongoing",
                "bullets": [
                    "Engineered and maintained backend application features and RESTful endpoints.",
                    "Executed database schema operations and CRUD workflows in PostgreSQL.",
                    "Conducted comprehensive software testing and API validation.",
                ],
            },
            {
                "role": "Java Developer Intern",
                "company": "Mass IT Solution",
                "duration": "Jan 2025 - Mar 2025",
                "bullets": ["Developed Java desktop applications using Java and MySQL."],
            },
        ],
        "projects": [
            {
                "name": "Task Management Application",
                "technologies": "Python, FastAPI, PostgreSQL",
                "bullets": [
                    "Architected high-performance RESTful microservices using Python and FastAPI.",
                    "Engineered optimized schemas in PostgreSQL supporting 15k+ daily queries.",
                    "Containerized application components with Docker and CI/CD.",
                ],
            },
            {
                "name": "Food Waste Management System",
                "technologies": "Python, FastAPI, PostgreSQL",
                "bullets": [
                    "Architected high-performance RESTful microservices using Python and FastAPI.",
                    "Engineered optimized schemas in PostgreSQL supporting 15k+ daily queries.",
                    "Containerized application components with Docker and CI/CD.",
                ],
            },
            {
                "name": "Meet.AI",
                "technologies": "Python, FastAPI, PostgreSQL",
                "bullets": [
                    "Architected high-performance RESTful microservices using Python and FastAPI.",
                    "Engineered optimized schemas in PostgreSQL supporting 15k+ daily queries.",
                    "Containerized application components with Docker and CI/CD.",
                ],
            },
        ],
        "education": [
            {
                "institution": "Smt. Kashibai Navale College of Engineering",
                "degree": "Bachelor of Engineering in ENTC - 8.35",
                "duration": "2023-2026",
            }
        ],
        "certifications": ["PCAP – Certified Associate in Python Programming (Python Institute)"],
    }


class TestAIJDTailoring(unittest.TestCase):
    def test_extract_profile_detects_ai_engineer_jd_and_non_ai_jd(self):
        ai_prof = extract_target_jd_profile(AI_ENGINEER_FRESHER_JD)
        self.assertTrue(ai_prof["is_ai_role"])
        self.assertEqual(ai_prof["target_role"], "AI Engineer")
        self.assertEqual(ai_prof["primary_language"], "Python")
        stack_joined = " ".join(ai_prof["ai_skills_ordered"]).lower()
        for expected_kw in ("python", "ai / ml", "genai", "agentic ai", "llms", "mlops", "ai frameworks"):
            self.assertIn(expected_kw, stack_joined)
        self.assertGreaterEqual(len(ai_prof["recommended_certifications"]), 2)

        non_ai_prof = extract_target_jd_profile(NON_AI_BACKEND_JD)
        self.assertFalse(non_ai_prof["is_ai_role"])

    def test_tailor_resume_intelligently_ai_jd_fallback_is_complete_and_unique(self):
        with patch("services.resume_tailor.call_ollama", side_effect=RuntimeError("rate limit")):
            out = tailor_resume_intelligently(AI_ENGINEER_FRESHER_JD, MASTER_RESUME_TEXT)

        tc = out["tailored_content"]
        self.assertEqual(tc["job_title"], "AI Engineer")

        summary_low = tc["summary"].lower()
        self.assertIn("ai engineer", summary_low)
        self.assertIn("extensive hands-on internship experience", summary_low)
        self.assertNotIn("years of", summary_low)
        for token in ("genai", "agentic ai", "llm", "mlops", "python"):
            self.assertIn(token, summary_low)

        skills = tc["skills"]
        self.assertIn("Targeted JD Stack", skills)
        self.assertIn("AI Frameworks & Libraries", skills)
        self.assertIn("Databases & Vector Stores", skills)
        self.assertIn("MLOps & Cloud", skills)
        self.assertNotIn("Databases", skills)
        targeted_joined = " | ".join(skills["Targeted JD Stack"]).lower()
        for kw in ("python", "ai / ml", "genai", "agentic ai", "llms", "mlops", "ai frameworks"):
            self.assertIn(kw, targeted_joined)

        exp = tc["experience"]
        self.assertEqual(exp[0]["company"], "Automaton AI Infosystem")
        self.assertEqual(exp[0]["role"], "Software Engineer Intern")
        self.assertEqual(exp[1]["company"], "Mass IT Solution")
        self.assertEqual(exp[2]["company"], "Infaneat Digital Marketing and Web Media")
        exp0_text = " ".join(exp[0]["bullets"]).lower()
        for kw in ("python", "genai", "agentic ai", "llm", "mlops"):
            self.assertIn(kw, exp0_text)

        projects = tc["projects"]
        self.assertEqual(len(projects), 3)
        all_bullets = [b for p in projects for b in p.get("bullets", [])]
        self.assertEqual(len(all_bullets), len(set(all_bullets)), "Project bullets must be unique per project")
        full_dump = json.dumps(tc).lower()
        self.assertNotIn("automated automated", full_dump)
        self.assertTrue(any("ai" in c.lower() or "llm" in c.lower() or "mlops" in c.lower() for c in tc["certifications"]))

    def test_tailor_resume_intelligently_enriches_partial_llm_output(self):
        partial_llm_json = json.dumps({
            "job_title": "Software Engineer",
            "target_tech_stack": ["Python", "FastAPI"],
            "target_database": ["PostgreSQL"],
            "important_keywords": ["Python", "REST APIs"],
            "tailored_summary": "Backend Software Engineer using Python and FastAPI.",
            "tailored_projects": [
                {
                    "name": "Task Management Application",
                    "technologies": "Python, FastAPI, PostgreSQL",
                    "bullets": [
                        "Built backend APIs in Python.",
                        "Managed database schemas.",
                        "Added Docker builds."
                    ],
                },
                {
                    "name": "Food Waste Management System",
                    "technologies": "Python, FastAPI, PostgreSQL",
                    "bullets": [
                        "Built backend APIs in Python.",
                        "Managed database schemas.",
                        "Added Docker builds."
                    ],
                },
                {
                    "name": "Meet.AI",
                    "technologies": "Python, FastAPI, PostgreSQL",
                    "bullets": [
                        "Built backend APIs in Python.",
                        "Managed database schemas.",
                        "Added Docker builds."
                    ],
                },
            ],
            "tailored_certifications": ["PCAP – Certified Associate in Python Programming"],
            "matching_skills": ["Python"],
            "missing_skills": ["LLMs", "MLOps"],
            "changes_applied": ["Updated summary"],
        })
        with patch("services.resume_tailor.call_ollama", return_value=partial_llm_json):
            out = tailor_resume_intelligently(AI_ENGINEER_FRESHER_JD, MASTER_RESUME_TEXT)

        tc = out["tailored_content"]
        self.assertEqual(tc["job_title"], "AI Engineer")
        targeted_joined = " | ".join(tc["skills"]["Targeted JD Stack"]).lower()
        self.assertIn("genai", targeted_joined)
        self.assertIn("agentic ai", targeted_joined)
        all_bullets = [b for p in tc["projects"] for b in p.get("bullets", [])]
        self.assertEqual(len(all_bullets), len(set(all_bullets)))
        self.assertIn("genai", " ".join(all_bullets).lower())

    def test_single_page_fresher_standalone_fallback_for_ai_jd(self):
        with patch("services.fresher_resume_service.call_ollama", side_effect=RuntimeError("rate limit")):
            out = tailor_fresher_resume_single_page(AI_ENGINEER_FRESHER_JD, MASTER_RESUME_TEXT)

        sp = out["single_page_tailored_content"]
        self.assertEqual(sp["job_title"], "AI Engineer")
        self.assertIn("ai", sp["summary"].lower())
        self.assertIn("genai", " ".join(sp["skills"].get("Targeted JD Stack", [])).lower())
        self.assertEqual(sp["experience"][0]["company"], "Automaton AI Infosystem")
        self.assertIn("agentic ai", " ".join(sp["experience"][0]["bullets"]).lower())
        sp_bullets = [b for p in sp["projects"] for b in p.get("bullets", [])]
        self.assertEqual(len(sp_bullets), len(set(sp_bullets)))

    def test_copilot_chats_fallback_align_resume_to_ai_jd(self):
        instruction = "add keypoint according to the job description change the resume according to the job description"
        stale_multi = _stale_backend_resume_dict()
        stale_single = copy.deepcopy(stale_multi)

        with patch("services.resume_tailor.call_ollama", side_effect=RuntimeError("rate limit")):
            multi_edit = edit_tailored_resume(
                stale_multi,
                instruction=instruction,
                original_resume_text=MASTER_RESUME_TEXT,
                jd_text=AI_ENGINEER_FRESHER_JD,
            )

        updated_m = multi_edit["updated_content"]
        self.assertIn("genai", updated_m["summary"].lower())
        self.assertIn("agentic ai", " ".join(updated_m["skills"]["Targeted JD Stack"]).lower())
        self.assertIn("mlops", " ".join(updated_m["experience"][0]["bullets"]).lower())
        m_bullets = [b for p in updated_m["projects"] for b in p.get("bullets", [])]
        self.assertEqual(len(m_bullets), len(set(m_bullets)))

        with patch("services.fresher_resume_service.call_ollama", side_effect=RuntimeError("rate limit")):
            single_edit = edit_single_page_fresher_resume(
                stale_single,
                instruction=instruction,
                original_resume_text=MASTER_RESUME_TEXT,
                jd_text=AI_ENGINEER_FRESHER_JD,
            )

        updated_s = single_edit["updated_content"]
        self.assertIn("genai", updated_s["summary"].lower())
        self.assertIn("agentic ai", " ".join(updated_s["skills"]["Targeted JD Stack"]).lower())
        self.assertIn("mlops", " ".join(updated_s["experience"][0]["bullets"]).lower())


if __name__ == "__main__":
    unittest.main()

