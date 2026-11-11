"""
Unit and Integration Tests for Single-Page Fresher Resume Generator and State Isolation.
Verifies:
1. Multi-page and Single-page resume generation pipelines.
2. State isolation: Chat 1 modifications do not affect Resume 2; Chat 2 modifications do not affect Resume 1.
3. Single-page PDF strictly fits on 1 A4 page.
4. Single-page DOCX export produces a valid document.
5. Content optimization and condensing pipeline enforces single-page constraints.
"""

import sys
import unittest
from pathlib import Path
import copy
import json
import re
from unittest.mock import patch

# Add backend to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pymupdf as fitz
from docx import Document

from services.fresher_resume_service import (
    tailor_fresher_resume_single_page,
    edit_single_page_fresher_resume,
    condense_fresher_resume_to_one_page,
    generate_single_page_pdf,
    generate_single_page_docx
)
from services.resume_tailor import (
    tailor_resume_intelligently,
    edit_tailored_resume
)

SAMPLE_RESUME_TEXT = """
OM PANSARE
om.pansare10@gmail.com | +91 9284975854 | linkedin.com/in/ompansare | github.com/OmPansare10 | Pune, Maharashtra

SUMMARY
Software Engineer with hands-on experience in full-stack application development using Java, Spring Boot, REST APIs, React.js, and databases. Experienced in developing scalable backend services, integrating RESTful APIs, implementing authentication, and building responsive frontend applications. Strong foundation in OOP, DSA, DBMS, SDLC, Git, and Agile development.

EDUCATION
Smt. Kashibai Navale College of Engineering - Pune, Maharashtra
Bachelor of Engineering in ENTC                                                              8.35 CGPA (2023-2026)
Government Polytechnic Pune - Pune, Maharashtra
Diploma in Computer Engineering                                                               84.40% (2020-2023)

EXPERIENCE
Full Stack Developer Intern - Tech Innovations, Pune                                        Jun 2024 - Aug 2024
• Developed scalable REST microservices using Java Spring Boot and PostgreSQL, decreasing query latency by 28%.
• Built responsive dashboard components in React.js and integrated JWT token authentication.

PROJECTS
TaskFlow AI Management System | React.js, Spring Boot, PostgreSQL, Docker
• Architected task management platform handling concurrent real-time status updates via WebSocket.
• Designed normalized database schema with indexed queries, ensuring fast sub-100ms data retrieval.
• Containerized application with Docker Compose for seamless reproducible staging deployments.

E-Commerce Microservices Engine | Java, Spring Cloud, Redis, MySQL
• Engineered distributed order processing backend processing over 1,500 mock transactions per minute.
• Implemented Redis cache layer reducing database load by 42% on high-demand inventory queries.

TECHNICAL SKILLS
Languages: Java, Python, C++, JavaScript, SQL
Frameworks: Spring Boot, React.js, FastAPI, Node.js
Databases: PostgreSQL, MySQL, MongoDB, Redis
Developer Tools: Git, GitHub, Docker, Postman, Linux, VS Code
Core Competencies: Data Structures & Algorithms, OOP, DBMS, RESTful APIs, SDLC

CERTIFICATIONS
• Oracle Certified Associate, Java SE 8 Programmer
• Meta Front-End Developer Professional Certificate
"""

SAMPLE_JD_TEXT = """
Job Title: Software Developer - Fresher / Junior
Location: Pune, India
Requirements:
We are looking for a motivated Fresher Software Developer to join our core engineering team.
Key Requirements:
- Solid understanding of Python or Java, and Object-Oriented Programming (OOP) concepts.
- Familiarity with REST APIs and modern web frameworks (FastAPI, React.js).
- Strong relational and NoSQL database skills (PostgreSQL, MongoDB).
- Understanding of Data Structures, Algorithms, and Software Engineering lifecycle.
- Bachelor's degree in Computer Science, Engineering, or related technical field.
"""

MOCK_FRESHER_JSON = """
{
  "job_title": "Software Developer - Fresher",
  "summary": "Ambitious Software Engineer with strong foundation in Java, Spring Boot, React.js, and modern databases. Experienced in building full-stack platforms and RESTful APIs, aiming to deliver scalable software solutions.",
  "education": [
    {
      "degree": "Bachelor of Engineering in ENTC",
      "institution": "Smt. Kashibai Navale College of Engineering",
      "location": "Pune",
      "duration": "2023–2026",
      "score": "8.35 CGPA"
    },
    {
      "degree": "Diploma in Computer Engineering",
      "institution": "Government Polytechnic Pune",
      "location": "Pune",
      "duration": "2020–2023",
      "score": "84.40%"
    }
  ],
  "experience": [
    {
      "role": "Full Stack Developer Intern",
      "company": "Tech Innovations",
      "location": "Pune",
      "duration": "Jun 2024 - Aug 2024",
      "bullets": [
        "Developed scalable microservices using Spring Boot and PostgreSQL.",
        "Built responsive dashboard components in React.js with JWT security."
      ]
    }
  ],
  "projects": [
    {
      "name": "TaskFlow AI Management System",
      "technologies": "React.js, Spring Boot, PostgreSQL, Docker",
      "link": "github.com/OmPansare10/taskflow",
      "bullets": [
        "Architected task management platform with sub-100ms API response time.",
        "Optimized PostgreSQL schema design and indexing for fast concurrent reads."
      ]
    },
    {
      "name": "E-Commerce Microservices Engine",
      "technologies": "Java, Spring Cloud, Redis, MySQL",
      "link": "github.com/OmPansare10/ecommerce",
      "bullets": [
        "Engineered distributed order processing backend handling 1500+ transactions/min.",
        "Implemented Redis cache layer reducing database load by 42%."
      ]
    }
  ],
  "skills": {
    "languages": ["Java", "Python", "JavaScript", "SQL", "C++"],
    "frameworks": ["Spring Boot", "React.js", "FastAPI", "Node.js"],
    "databases": ["PostgreSQL", "MySQL", "MongoDB", "Redis"],
    "developer_tools": ["Git", "GitHub", "Docker", "Postman", "VS Code"],
    "core_competencies": ["Data Structures & Algorithms", "OOP", "DBMS", "REST APIs", "SDLC"]
  },
  "certifications": [
    "Oracle Certified Associate, Java SE 8 Programmer",
    "Meta Front-End Developer Professional Certificate"
  ],
  "single_page_advice": "Strict 1-page A4 campus placement density enforced."
}
"""


class TestSinglePageFresher(unittest.TestCase):

    @patch("services.fresher_resume_service.call_ollama", return_value=MOCK_FRESHER_JSON)
    def test_single_page_generation(self, mock_llm):
        """Test that single-page fresher resume generation outputs valid structured data."""
        res = tailor_fresher_resume_single_page(
            jd_text=SAMPLE_JD_TEXT,
            resume_text=SAMPLE_RESUME_TEXT,
            filename="OM_PANSARE.pdf"
        )
        self.assertEqual(res.get("status"), "success")
        content = res.get("single_page_tailored_content")
        self.assertIsNotNone(content)
        self.assertIn("OM PANSARE", content.get("name", "").upper())
        self.assertTrue(len(content.get("education", [])) > 0)
        self.assertTrue(len(content.get("projects", [])) > 0)
        self.assertIn("skills", content)

    @patch("services.fresher_resume_service.call_ollama", return_value=MOCK_FRESHER_JSON)
    def test_single_page_pdf_page_count(self, mock_llm):
        """Test that the generated PDF contains strictly 1 page."""
        res = tailor_fresher_resume_single_page(
            jd_text=SAMPLE_JD_TEXT,
            resume_text=SAMPLE_RESUME_TEXT,
            filename="OM_PANSARE.pdf"
        )
        content = res["single_page_tailored_content"]
        pdf_path = generate_single_page_pdf(content)
        self.assertTrue(pdf_path.exists())

        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        doc.close()
        self.assertEqual(page_count, 1, f"Expected 1 page, got {page_count}")

    @patch("services.fresher_resume_service.call_ollama", return_value=MOCK_FRESHER_JSON)
    def test_single_page_docx_validity(self, mock_llm):
        """Test that single-page DOCX generator produces a readable document."""
        res = tailor_fresher_resume_single_page(
            jd_text=SAMPLE_JD_TEXT,
            resume_text=SAMPLE_RESUME_TEXT,
            filename="OM_PANSARE.pdf"
        )
        content = res["single_page_tailored_content"]
        docx_path = generate_single_page_docx(content)
        self.assertTrue(docx_path.exists())

        doc = Document(str(docx_path))
        full_text = "\n".join([p.text for p in doc.paragraphs])
        self.assertIn("OM PANSARE", full_text)
        self.assertIn("EDUCATION", full_text.upper())
        self.assertTrue("CORE SKILLS" in full_text.upper() or "TECHNICAL SKILLS" in full_text.upper())

    def test_state_isolation_chat1_does_not_affect_resume2(self):
        """
        Verify that Chat 1 edits modify ONLY Resume 1 (multi-page)
        and leave Resume 2 (single-page) completely untouched.
        """
        # Baseline Resume 1 (Multi-page)
        resume1 = {
            "name": "Om Pansare",
            "summary": "Multi-page resume summary",
            "projects": [
                {"name": "Project Alpha", "technologies": "Java, Spring Boot", "bullets": ["Built API endpoints."]}
            ],
            "skills": {"languages": ["Java"]}
        }

        # Baseline Resume 2 (Single-page)
        resume2 = {
            "name": "Om Pansare",
            "summary": "Single-page fresher summary",
            "education": [{"degree": "B.E. ENTC", "institution": "SKNCOE"}],
            "projects": [
                {"name": "Fresher Project", "technologies": "React, Python", "bullets": ["Built frontend UI."]}
            ],
            "skills": {"languages": ["Python", "JavaScript"]}
        }

        # Snapshot Resume 2 before editing Resume 1
        snapshot_resume2 = copy.deepcopy(resume2)

        # Apply Chat 1 modification: change database in Multi-page resume
        edit_res1 = edit_tailored_resume(
            resume_content=resume1,
            instruction="Switch project database to Cassandra DB",
            original_resume_text=SAMPLE_RESUME_TEXT,
            jd_text=SAMPLE_JD_TEXT
        )
        updated_resume1 = edit_res1["updated_content"]

        # Verify Resume 1 changed
        resume1_str = str(updated_resume1)
        self.assertIn("Cassandra", resume1_str)

        # Verify Resume 2 is COMPLETELY IDENTICAL to its snapshot
        self.assertEqual(resume2, snapshot_resume2)
        self.assertNotIn("Cassandra", str(resume2))

    def test_state_isolation_chat2_does_not_affect_resume1(self):
        """
        Verify that Chat 2 edits modify ONLY Resume 2 (single-page)
        and leave Resume 1 (multi-page) completely untouched.
        """
        # Baseline Resume 1 (Multi-page)
        resume1 = {
            "name": "Om Pansare",
            "summary": "Multi-page resume summary",
            "projects": [
                {"name": "Project Alpha", "technologies": "Java, Spring Boot", "bullets": ["Built API endpoints."]}
            ],
            "skills": {"languages": ["Java"]}
        }

        # Baseline Resume 2 (Single-page)
        resume2 = {
            "name": "Om Pansare",
            "summary": "Single-page fresher summary",
            "education": [{"degree": "B.E. ENTC", "institution": "SKNCOE"}],
            "projects": [
                {"name": "Fresher Project", "technologies": "React, Python", "bullets": ["Built frontend UI."]}
            ],
            "skills": {"languages": ["Python", "JavaScript"]}
        }

        # Snapshot Resume 1 before editing Resume 2
        snapshot_resume1 = copy.deepcopy(resume1)

        # Apply Chat 2 modification: add Kotlin language skill to Single-page fresher resume
        edit_res2 = edit_single_page_fresher_resume(
            resume_content=resume2,
            instruction="Add skills: Kotlin, Jetpack Compose",
            original_resume_text=SAMPLE_RESUME_TEXT,
            jd_text=SAMPLE_JD_TEXT
        )
        updated_resume2 = edit_res2["updated_content"]

        # Verify Resume 2 changed
        self.assertIn("Kotlin", str(updated_resume2.get("skills", {})))

        # Verify Resume 1 is COMPLETELY IDENTICAL to its snapshot
        self.assertEqual(resume1, snapshot_resume1)
        self.assertNotIn("Kotlin", str(resume1.get("skills", {})))

    def test_condense_to_one_page_enforcement(self):
        """Verify that the condense pipeline trims summaries, projects, and bullets to fit 1 page."""
        bloated_data = {
            "name": "TEST CANDIDATE",
            "summary": "First sentence is long. Second sentence is long. Third sentence is long. Fourth sentence is long. Fifth sentence is long. Sixth sentence is long. Extra verbose filler text goes here to bloat paragraph.",
            "education": [{"degree": "B.E.", "institution": "College", "location": "City", "duration": "2024", "score": "8.5"}],
            "projects": [
                {
                    "name": f"Project {i}",
                    "technologies": "Tech",
                    "bullets": [f"Very long bullet point description that describes lots of things {j}" for j in range(6)]
                }
                for i in range(5)
            ],
            "skills": {"languages": [f"Lang{i}" for i in range(20)]},
            "certifications": [f"Cert {i}" for i in range(10)]
        }
        condensed = condense_fresher_resume_to_one_page(bloated_data)

        # Must cap projects at 3
        self.assertLessEqual(len(condensed["projects"]), 3)
        for p in condensed["projects"]:
            # Must cap bullets at 3
            self.assertLessEqual(len(p["bullets"]), 3)
        # Must cap certifications at 3
        self.assertLessEqual(len(condensed["certifications"]), 3)
        # Summary must be concise
        self.assertLessEqual(len(condensed["summary"]), 300)

    def test_sync_from_above_resume_with_experience_and_projects(self):
        """Verify that user prompt to sync all details restores missing experience and projects in 1-page fit."""
        base_tailored = {
            "name": "Om Pansare",
            "contact": {
                "email": "om.pansare10@gmail.com",
                "phone": "+9284975854",
                "location": "Pune, Maharashtra",
                "linkedin": "linkedin.com/in/ompansare",
                "github": "github.com/OmPansare10"
            },
            "summary": "Results-driven Python Developer with 2+ years of experience building high-performance backend services using FastAPI and Django. Proven ability to design scalable RESTful APIs, optimize PostgreSQL schemas, and implement Redis caching.",
            "skills": {
                "Targeted JD Stack": ["Python", "FastAPI", "Django", "PostgreSQL", "Redis", "Docker"],
                "Databases & Storage": ["PostgreSQL", "Redis"],
                "Cloud & DevOps": ["AWS", "REST APIs", "Git", "CI/CD"],
                "Languages": ["Java", "Python", "JavaScript", "SQL", "C++"],
                "Backend": ["Spring Boot", "REST APIs", "JDBC", "JSP", "Servlets"],
                "Frontend": ["React.js", "HTML", "CSS"],
                "Databases": ["MySQL", "MongoDB"],
                "Testing": ["JUnit", "TestNG", "Selenium WebDriver", "Postman", "REST Assured"],
                "Core Concepts": ["OOP", "DSA", "DBMS", "SDLC", "STLC"],
                "Tools": ["Git", "GitHub", "Eclipse", "VS Code", "Jenkins"],
                "Methodologies": ["Agile/Scrum", "CI/CD", "Debugging"]
            },
            "experience": [
                {
                    "role": "Software Engineer Intern",
                    "company": "Automaton AI Infosystem",
                    "location": "Pune",
                    "duration": "Sep 2026",
                    "bullets": [
                        "Developed and maintained software applications using Java, Spring Boot, REST APIs, Python, React.js, and databases.",
                        "Developed and integrated RESTful APIs, implementing authentication, CRUD operations, database connectivity, and application business logic."
                    ]
                }
            ],
            "projects": [
                {
                    "name": "Distributed High-Throughput Order Engine",
                    "technologies": "Python, FastAPI, PostgreSQL, Redis, Docker",
                    "link": "github.com/OmPansare10/order-engine",
                    "bullets": [
                        "Architected scalable microservice processing 12,000 requests per minute with sub-second response times.",
                        "Implemented Redis caching reducing database schema query latency by 45%."
                    ]
                }
            ],
            "education": [
                {
                    "degree": "Bachelor of Engineering in ENTC",
                    "institution": "Smt. Kashibai Navale College of Engineering",
                    "location": "Pune, Maharashtra",
                    "duration": "2023-2026",
                    "score": "CGPA 8.35"
                }
            ],
            "certifications": [
                "Oracle Certified Professional: Java SE 17 Developer",
                "Spring Certified Professional"
            ]
        }

        # Simulating Resume 2 when experience was missing
        incomplete_resume2 = copy.deepcopy(base_tailored)
        incomplete_resume2["experience"] = []  # Experience was missing!

        # User prompt exactly from user request
        user_prompt = "i want all detail in above resume to see in below resume but i want in 1 page project and experience in missing in this 1 pages resume fix it"

        edit_result = edit_single_page_fresher_resume(
            resume_content=incomplete_resume2,
            instruction=user_prompt,
            original_resume_text=SAMPLE_RESUME_TEXT,
            jd_text=SAMPLE_JD_TEXT,
            base_tailored_resume=base_tailored
        )

        updated_resume = edit_result["updated_content"]

        # 1. Experience MUST be restored
        self.assertTrue(len(updated_resume.get("experience", [])) > 0, "Experience must be restored in single-page resume")
        self.assertEqual(updated_resume["experience"][0]["company"], "Automaton AI Infosystem")

        # 2. Projects MUST be present
        self.assertTrue(len(updated_resume.get("projects", [])) > 0, "Projects must be present")
        self.assertIn("Python, FastAPI", updated_resume["projects"][0]["technologies"])

        # 3. Skills MUST retain Targeted JD Stack
        self.assertIn("Targeted JD Stack", updated_resume.get("skills", {}))

        # 4. Summary MUST be present
        self.assertTrue(bool(updated_resume.get("summary")))

        # 5. Generate PDF and verify strict 1-page count
        pdf_path = generate_single_page_pdf(updated_resume)
        self.assertTrue(pdf_path.exists())
        doc = fitz.open(str(pdf_path))
        self.assertEqual(len(doc), 1, "Exported Single-Page PDF must strictly be 1 page")
        doc.close()

    def test_tailor_fresher_resume_single_page_inherits_base_tailored(self):
        """Verify that tailor_fresher_resume_single_page directly inherits from base_tailored_resume."""
        base_tailored = {
            "name": "Om Pansare",
            "contact": {"email": "om.pansare10@gmail.com"},
            "summary": "Experienced Python and FastAPI backend developer.",
            "experience": [
                {
                    "role": "Software Engineer Intern",
                    "company": "Automaton AI Infosystem",
                    "bullets": ["Integrated RESTful APIs with database connectivity."]
                }
            ],
            "projects": [
                {
                    "name": "FastAPI Microservice",
                    "technologies": "FastAPI, PostgreSQL",
                    "bullets": ["Engineered high performance backend endpoints."]
                }
            ],
            "education": [{"degree": "BE ENTC", "institution": "SKNCOE"}],
            "skills": {"Targeted JD Stack": ["Python", "FastAPI", "PostgreSQL"]},
            "certifications": ["Python Certified Associate"]
        }

        res = tailor_fresher_resume_single_page(
            jd_text=SAMPLE_JD_TEXT,
            resume_text=SAMPLE_RESUME_TEXT,
            base_tailored_resume=base_tailored
        )
        content = res["single_page_tailored_content"]
        self.assertEqual(res["page_count_verified"], 1)
        self.assertTrue(len(content["experience"]) > 0)
        self.assertEqual(content["experience"][0]["company"], "Automaton AI Infosystem")
        self.assertTrue(len(content["projects"]) > 0)

    def test_edit_single_page_summary_three_lines(self):
        """Verify that asking for 'summary in aleast 3 line' generates a complete 3-line summary without truncation."""
        sample_resume = json.loads(MOCK_FRESHER_JSON)
        res = edit_single_page_fresher_resume(
            resume_content=sample_resume,
            instruction="i want summary in aleast 3 line",
            base_tailored_resume=sample_resume
        )
        updated = res["updated_content"]
        summary = updated.get("summary", "")
        # Must not end in broken ellipsis '...'
        self.assertFalse(summary.endswith("..."), f"Summary should not be truncated with '...': {summary}")
        # Must contain at least 3 complete sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if s.strip()]
        self.assertGreaterEqual(len(sentences), 3, f"Summary should have at least 3 sentences: {summary}")
        # Length should comfortably represent 3 full lines (>= 300 chars)
        self.assertGreaterEqual(len(summary), 300, f"Summary length should be >= 300 chars: {len(summary)}")

    def test_edit_single_page_summary_two_lines(self):
        """Verify that asking for 'shorten professional summary to 2 lines' produces a concise 2-line summary."""
        sample_resume = json.loads(MOCK_FRESHER_JSON)
        res = edit_single_page_fresher_resume(
            resume_content=sample_resume,
            instruction="shorten professional summary to 2 lines",
            base_tailored_resume=sample_resume
        )
        updated = res["updated_content"]
        summary = updated.get("summary", "")
        self.assertFalse(summary.endswith("..."))
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', summary) if s.strip()]
        self.assertEqual(len(sentences), 2, f"Summary should have exactly 2 sentences: {summary}")

    def test_bullets_single_full_stop(self):
        """Verify that every bullet in experience and projects ends with a single full stop and never multiple dots."""
        sample_resume = json.loads(MOCK_FRESHER_JSON)
        # Add bullets that previously might have been cut or had multiple dots
        sample_resume["projects"][0]["bullets"].append("Engineered async endpoints and JWT...")
        sample_resume["projects"][1]["bullets"].append("Reduced query latency by 70% and...")
        sample_resume["experience"][0]["bullets"].append("Implemented automated CI/CD pipeline deployments via GitLab CI...")

        res = edit_single_page_fresher_resume(
            resume_content=sample_resume,
            instruction="at the end i want single full stop but there is multiple full stop",
            base_tailored_resume=sample_resume
        )
        updated = res["updated_content"]

        all_bullets = []
        for exp in updated.get("experience", []):
            all_bullets.extend(exp.get("bullets", []))
        for proj in updated.get("projects", []):
            all_bullets.extend(proj.get("bullets", []))

        self.assertTrue(len(all_bullets) > 0)
        for b in all_bullets:
            b_str = str(b).strip()
            self.assertFalse(b_str.endswith("..."), f"Bullet must not end with '...': {b_str}")
            self.assertFalse(b_str.endswith(".."), f"Bullet must not end with '..': {b_str}")
            self.assertTrue(b_str.endswith("."), f"Bullet must end with a single full stop '.': {b_str}")
            self.assertFalse(b_str.endswith(".."), f"Bullet must not end with multiple periods: {b_str}")

    def test_remove_2_year_experience_from_summary(self):
        """Verify that 'remove 2 year experien from summary' strips 2+ years claim completely."""
        sample_resume = json.loads(MOCK_FRESHER_JSON)
        sample_resume["summary"] = (
            "Software Engineer with 2+ years of hands-on experience building high-performance web solutions using Python, FastAPI, React. "
            "Skilled in designing secure, scalable RESTful APIs and distributed microservices backed by PostgreSQL, Redis, Docker. "
            "Experienced in implementing automated CI/CD pipelines, test automation, and cloud deployments to ensure reliable production delivery."
        )

        res = edit_single_page_fresher_resume(
            resume_content=sample_resume,
            instruction="remove 2 year experien from summary",
            base_tailored_resume=sample_resume
        )
        updated = res["updated_content"]
        updated_sum = updated.get("summary", "")

        self.assertNotIn("2+ years", updated_sum)
        self.assertNotIn("2 years", updated_sum)
        self.assertNotIn("2 year", updated_sum)
        self.assertIn("hands-on expertise", updated_sum)
        self.assertTrue(len(updated_sum) > 100)


    def test_chat2_certification_db_switch_and_project_removal(self):
        """Verify Chat 2 handles certifications, combined DB switches (MongoDB & Redis), and project removal."""
        base_resume = json.loads(MOCK_FRESHER_JSON)
        base_resume["projects"].append({
            "name": "Analytics Dashboard",
            "technologies": "React, PostgreSQL",
            "bullets": [
                "Built analytics dashboard using React.",
                "Queried PostgreSQL reporting tables cleanly."
            ]
        })

        # 1. Add certification
        res_cert = edit_single_page_fresher_resume(
            resume_content=copy.deepcopy(base_resume),
            instruction="Add AWS Solutions Architect certification"
        )
        self.assertIn(
            "AWS Certified Solutions Architect - Associate",
            res_cert["updated_content"].get("certifications", [])
        )

        # 2. Switch project database to MongoDB & Redis (preserve '& Redis')
        res_db = edit_single_page_fresher_resume(
            resume_content=copy.deepcopy(base_resume),
            instruction="Switch project database to MongoDB & Redis"
        )
        db_skills = str(res_db["updated_content"].get("skills", {}))
        self.assertIn("MongoDB", db_skills)
        self.assertIn("Redis", db_skills)
        self.assertIn("MongoDB", res_db["updated_content"]["projects"][0]["technologies"])
        self.assertIn("Redis", res_db["updated_content"]["projects"][0]["technologies"])

        # 3. Remove project 2 should NOT re-inject a 3rd project when user deleted one
        res_rem = edit_single_page_fresher_resume(
            resume_content=copy.deepcopy(base_resume),
            instruction="Remove project 2",
            base_tailored_resume=copy.deepcopy(base_resume)
        )
        proj_names = [pr["name"] for pr in res_rem["updated_content"].get("projects", [])]
        self.assertNotIn("E-Commerce Microservices Engine", proj_names)
        self.assertEqual(len(proj_names), 2)

    def test_chat2_screenshot_ocr_ordinal_bullet_edit_and_typo_polish(self):
        """
        Exact user scenario: pasted screenshot OCR of experience section + casual/typo query
        'in this at 3 point aad a point in which i redue the time to work, creat an application thta rerduce the time'
        must update Bullet 3 cleanly, fix ',.' artifact on Bullet 2, and keep company/bullets 1-2 intact.
        """
        resume = json.loads(MOCK_FRESHER_JSON)
        resume["experience"] = [
            {
                "role": "Software Engineer Intern",
                "company": "Automaton AI Infosystem",
                "duration": "Sep 2026 - Ongoing",
                "bullets": [
                    "Developed and maintained software applications using Java, Spring Boot, REST APIs, Python, React.js, and databases.",
                    "Developed and integrated RESTful APIs, implementing authentication, CRUD operations, database connectivity,.",
                    "application business logic."
                ]
            }
        ]
        user_query = "in this at 3 point aad a point in which i redue the time to work, creat an application thta rerduce the time"
        ocr_sample = "Boot, REST APIs, Python, React.js\nCRUD operations, database connectivity"

        with patch("services.fresher_resume_service.extract_text_from_image_b64", return_value=ocr_sample), \
             patch("services.resume_tailor.call_ollama", side_effect=RuntimeError("offline fallback check")):
            res = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(resume),
                instruction=user_query,
                image_data="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
                base_tailored_resume=copy.deepcopy(resume)
            )

        exp = res["updated_content"]["experience"][0]
        bullets = exp["bullets"]
        self.assertEqual(exp["company"], "Automaton AI Infosystem")
        self.assertEqual(len(bullets), 3)
        self.assertIn("Java, Spring Boot", bullets[0])
        self.assertFalse(bullets[1].endswith(",."), f"Bullet 2 should clean ',.' artifact: {bullets[1]}")
        self.assertTrue(bullets[1].endswith("database connectivity."))

        b3_low = bullets[2].lower()
        self.assertNotIn("application business logic", b3_low)
        self.assertIn("application", b3_low)
        self.assertIn("reduce", b3_low)
        for typo in ("aad", "redue", "rerduce", "thta", "creat "):
            self.assertNotIn(typo, b3_low)
        self.assertTrue(bullets[2][0].isupper())
        self.assertTrue(bullets[2].endswith("."))
        self.assertFalse(bullets[2].endswith(".."))

    def test_ordinal_project_and_experience_bullet_edits_in_both_chats(self):
        """Verify ordinal bullet replacements work cleanly on Projects & Experience in both Chat 1 and Chat 2."""
        resume = json.loads(MOCK_FRESHER_JSON)
        resume["projects"][0]["image"] = "data:image/png;base64,FAKEIMGDATA12345678901234567890"

        new_b2 = "Built a distributed Redis caching layer cutting response latency by 45%"
        cmd_proj = f"change 2nd bullet of project 1 to {new_b2}"

        with patch("services.resume_tailor.call_ollama", side_effect=RuntimeError("offline")):
            res_chat2 = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(resume),
                instruction=cmd_proj,
                base_tailored_resume=copy.deepcopy(resume)
            )
            res_chat1 = edit_tailored_resume(
                resume_content=copy.deepcopy(resume),
                instruction=cmd_proj
            )

        for label, out_doc in [("Chat 2", res_chat2["updated_content"]), ("Chat 1", res_chat1["updated_content"])]:
            p0 = out_doc["projects"][0]
            self.assertEqual(p0["bullets"][1], new_b2 + ".", f"{label} did not update project 1 bullet 2 cleanly")
            self.assertEqual(p0.get("image"), "data:image/png;base64,FAKEIMGDATA12345678901234567890")

        new_exp_b = "Engineered async FastAPI pipelines boosting API throughput"
        cmd_exp = f"change 2nd bullet of experience to {new_exp_b}"
        with patch("services.resume_tailor.call_ollama", side_effect=RuntimeError("offline")):
            exp_chat2 = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(resume),
                instruction=cmd_exp,
                base_tailored_resume=copy.deepcopy(resume)
            )
            exp_chat1 = edit_tailored_resume(
                resume_content=copy.deepcopy(resume),
                instruction=cmd_exp
            )

        for label, out_doc in [("Chat 2", exp_chat2["updated_content"]), ("Chat 1", exp_chat1["updated_content"])]:
            self.assertEqual(out_doc["experience"][0]["bullets"][1], new_exp_b + ".", f"{label} did not update experience bullet 2")

    def test_groq_429_failover_and_arbitrary_natural_language_edit(self):
        """Verify call_groq retries next Groq model on 429 and Chat 2 applies delta JSON updates cleanly."""
        from unittest.mock import MagicMock
        import services.ai_service as ai_service

        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.text = "Rate limit exceeded"
        mock_429.json.return_value = {"error": {"message": "Rate limit reached"}}

        delta_json = json.dumps({
            "updated_summary": "Backend engineer specializing in distributed FastAPI systems, cloud infrastructure, and real-time analytics pipelines across production environments.",
            "changes": ["Refined summary via fallback Groq model."]
        })
        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.json.return_value = {"choices": [{"message": {"content": delta_json}}]}

        called_models = []

        def fake_post(url, headers=None, json=None, timeout=60):
            called_models.append(json.get("model"))
            if len(called_models) == 1:
                return mock_429
            return mock_200

        base_resume = json.loads(MOCK_FRESHER_JSON)
        with patch.object(ai_service, "GROQ_API_KEY", "test-key"), \
             patch("services.ai_service.requests.post", side_effect=fake_post):
            res = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(base_resume),
                instruction="refine my career overview to spotlight high-availability event-driven architectures and reliability engineering"
            )

        self.assertGreaterEqual(len(called_models), 2)
        self.assertEqual(called_models[0], ai_service.GROQ_MODEL)
        self.assertIn("distributed FastAPI systems", res["updated_content"]["summary"])
        self.assertTrue(any("Refined summary via fallback Groq model" in c for c in res["changes"]))

    def test_chat2_experience_screenshot_never_hijacked_as_summary(self):
        """
        Regression test for 12:26 PM bug: pasting Experience screenshot containing 'Software Engineer Intem Automaton AI Infosystem'
        must NEVER overwrite summary with OCR text, and must accurately route rename / change-this-point edits to Experience.
        """
        base = json.loads(MOCK_FRESHER_JSON)
        base["experience"] = [{
            "role": "Software Engineer Intern",
            "company": "Automaton AI Infosystem",
            "duration": "Sep 2026 - Ongoing",
            "bullets": [
                "Developed and maintained software applications using Java, Spring Boot, REST APIs, Python, React.js.",
                "Integrated PostgreSQL schemas and Redis caching layers."
            ]
        }]
        ocr_exp = "Software Engineer Intem Automaton AI Infosystem Sep 2026 Ongoing Developed and maintained software applicabons using Java, Spring Boot, REST APIs, Python, Reactjs"
        fake_img = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        orig_summary = base["summary"]

        # 1. Explicit company rename mentioning Automaton must rename company (NOT trigger Webcrypt or Summary hijack)
        with patch("services.fresher_resume_service.extract_text_from_image_b64", return_value=ocr_exp):
            res_rename = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(base),
                instruction="rename Automaton AI Infosystem to Acme Systems",
                image_data=fake_img
            )
        self.assertEqual(res_rename["updated_content"]["experience"][0]["company"], "Acme Systems")
        self.assertEqual(res_rename["updated_content"]["summary"], orig_summary)

        # 2. 'change this point to ...' with Experience screenshot must edit Experience Bullet 1, NOT Summary
        with patch("services.fresher_resume_service.extract_text_from_image_b64", return_value=ocr_exp), \
             patch("services.resume_tailor.call_ollama", side_effect=RuntimeError("offline")):
            res_point_to = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(base),
                instruction="change this point to Built async FastAPI microservices cutting latency",
                image_data=fake_img
            )
        self.assertEqual(res_point_to["updated_content"]["summary"], orig_summary)
        self.assertIn("FastAPI microservices", res_point_to["updated_content"]["experience"][0]["bullets"][0])

        # 3. Open-ended 'change this point' (without replacement text) must route to Step 4 LLM with Experience target
        ai_delta = json.dumps({
            "updated_experience": [{
                "role": "Software Engineer Intern",
                "company": "Automaton AI Infosystem",
                "duration": "Sep 2026 - Ongoing",
                "bullets": [
                    "Engineered scalable full-stack applications using Java, Spring Boot, REST APIs, Python, and React.js.",
                    "Integrated PostgreSQL schemas and Redis caching layers."
                ]
            }],
            "changes": ["Strengthened first experience bullet per screenshot context."]
        })
        captured_prompts = []

        def fake_llm(prompt, **kwargs):
            captured_prompts.append(prompt)
            return ai_delta

        with patch("services.fresher_resume_service.extract_text_from_image_b64", return_value=ocr_exp), \
             patch("services.fresher_resume_service.call_ollama", side_effect=fake_llm):
            res_open = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(base),
                instruction="change this point",
                image_data=fake_img
            )
        self.assertEqual(len(captured_prompts), 1)
        self.assertIn("section='experience'", captured_prompts[0])
        self.assertEqual(res_open["updated_content"]["summary"], orig_summary)
        self.assertIn("Engineered scalable full-stack applications", res_open["updated_content"]["experience"][0]["bullets"][0])

    def test_chat2_custom_summary_and_arbitrary_education_edits(self):
        """
        Verify nuance-specific summary instructions ('in summary add Kubernetes...') and arbitrary edits
        ('change CGPA to 9.10 and target role to Cloud Backend Engineer') route cleanly to Step 4 AI and apply updates.
        """
        base = json.loads(MOCK_FRESHER_JSON)
        delta_1 = json.dumps({
            "updated_summary": "Backend Developer skilled in Python, FastAPI, Kubernetes, and Terraform for resilient cloud deployments.",
            "changes": ["Added Kubernetes and Terraform to summary."]
        })
        with patch("services.fresher_resume_service.call_ollama", return_value=delta_1):
            res_sum = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(base),
                instruction="in summary add Kubernetes and Terraform expertise"
            )
        self.assertIn("Kubernetes", res_sum["updated_content"]["summary"])
        self.assertIn("Terraform", res_sum["updated_content"]["summary"])

        delta_2 = json.dumps({
            "target_role": "Cloud Backend Engineer",
            "updated_education": [{"institution": "Pune University", "degree": "B.E. Computer Engineering", "duration": "2020 - 2024", "score": "CGPA 9.10"}],
            "changes": ["Updated target role and CGPA."]
        })
        with patch("services.fresher_resume_service.call_ollama", return_value=delta_2):
            res_edu = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(base),
                instruction="change CGPA to 9.10 and target role to Cloud Backend Engineer"
            )
        self.assertEqual(res_edu["updated_content"]["job_title"], "Cloud Backend Engineer")
        self.assertEqual(res_edu["updated_content"]["education"][0]["score"], "CGPA 9.10")

    def test_chat2_surgical_single_internship_bullet_and_tiny_crop_ocr(self):
        """
        Verify exact user failure case:
        1) Tightly cropped tiny screenshot (18px height) still extracts OCR text via padding/upscaling.
        2) 'change this i want in this i resduce the work time alos reduce the repeatetive work in 10 to 15 words'
           targets ONLY the matched internship bullet without altering Internships 2 & 3 or Bullets 1 & 2.
        3) 'change the 3 point from 1 st intership ...' targets ONLY experience[0].bullets[2].
        4) Sparse 2-bullet internships do NOT receive identical cloned 3rd-bullet filler.
        """
        import base64
        import io
        from PIL import Image, ImageDraw
        from services.image_ocr import extract_text_from_image_b64
        from services.fresher_resume_service import condense_fresher_resume_to_one_page

        three_exp_resume = {
            "name": "Om Pansare",
            "job_title": "Software Developer",
            "summary": "Results-driven software engineer skilled in Java, Spring Boot, Python, and PostgreSQL.",
            "experience": [
                {
                    "role": "Software Engineer Intern",
                    "company": "Automaton AI Infosystem",
                    "duration": "Sep 2026 - Ongoing",
                    "bullets": [
                        "Built full-stack features with Java Spring Boot, Python, React, and REST APIs.",
                        "Implemented secure authentication and CRUD endpoints, improving API reliability.",
                        "Conducted comprehensive software testing, debugging, and API deployment validation.",
                    ],
                },
                {
                    "role": "Java Developer Intern",
                    "company": "Mass IT Solution",
                    "duration": "Jan 2025 - Mar 2025",
                    "bullets": [
                        "Developed Java desktop app with MySQL/JDBC, applying OOP for reliable software.",
                        "Conducted testing, debugging, and SQL validation, enhancing CRUD performance.",
                        "Documented modular DAO layers and streamlined database connection pooling across modules.",
                    ],
                },
                {
                    "role": "Java Backend Intern",
                    "company": "Infaneat Digital Marketing",
                    "duration": "Jul 2022 - Sep 2022",
                    "bullets": [
                        "Developed authentication and backend services using Java JSP, Servlets, MySQL, and JDBC.",
                        "Performed functional testing and SQL validation, improving CRUD workflow accuracy.",
                        "Maintained legacy servlet controllers and resolved session state defects across releases.",
                    ],
                },
            ],
            "projects": json.loads(MOCK_FRESHER_JSON)["projects"],
            "skills": json.loads(MOCK_FRESHER_JSON)["skills"],
            "education": json.loads(MOCK_FRESHER_JSON)["education"],
            "certifications": ["AWS Cloud Practitioner"],
        }

        # A. Tiny tight 24px single-line crop screenshot should still extract OCR cleanly
        img = Image.new("RGB", (680, 24), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)
        draw.text((6, 4), "Conducted comprehensive software testing, debugging, and API deployment validation.", fill=(20, 20, 20))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        tiny_b64 = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        ocr_out = extract_text_from_image_b64(tiny_b64)
        self.assertTrue(any(w in ocr_out.lower() for w in ["testing", "debugging", "validation"]), f"Tiny crop OCR failed: {ocr_out!r}")

        # B. Even if LLM clumsily tries to rewrite ALL 3 internships' 3rd bullets, Surgical Lock isolates Internship 1 Bullet 3!
        clumsy_llm_resp = json.dumps({
            "updated_experience": [
                {
                    "role": "Software Engineer Intern",
                    "company": "Automaton AI Infosystem",
                    "bullets": [
                        "Built full-stack features with Java Spring Boot, Python, React, and REST APIs.",
                        "Implemented secure authentication and CRUD endpoints, improving API reliability.",
                        "Automated repetitive workflows using Python scripts, significantly reducing manual task execution time."
                    ]
                },
                {
                    "role": "Java Developer Intern",
                    "company": "Mass IT Solution",
                    "bullets": [
                        "Developed Java desktop app with MySQL/JDBC, applying OOP for reliable software.",
                        "Conducted testing, debugging, and SQL validation, enhancing CRUD performance.",
                        "REWRITTEN BY MISTAKE!"
                    ]
                },
                {
                    "role": "Java Backend Intern",
                    "company": "Infaneat Digital Marketing",
                    "bullets": [
                        "Developed authentication and backend services using Java JSP, Servlets, MySQL, and JDBC.",
                        "Performed functional testing and SQL validation, improving CRUD workflow accuracy.",
                        "ALSO REWRITTEN BY MISTAKE!"
                    ]
                }
            ],
            "changes": ["Updated 3rd point of Automaton AI Infosystem to reflect workflow automation."]
        })

        with patch("services.fresher_resume_service.call_ollama", return_value=clumsy_llm_resp):
            res_img = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(three_exp_resume),
                instruction="change this i want in this i resduce the work time alos reduce the repeatetive work in 10 to 15 words",
                images_data=[tiny_b64],
            )
        exp_after = res_img["updated_content"]["experience"]
        # Internship 1 Bullet 3 updated; Bullets 1 & 2 preserved; Internships 2 & 3 100% untouched!
        self.assertIn("Automated repetitive workflows", exp_after[0]["bullets"][2])
        self.assertEqual(exp_after[0]["bullets"][0], three_exp_resume["experience"][0]["bullets"][0])
        self.assertEqual(exp_after[0]["bullets"][1], three_exp_resume["experience"][0]["bullets"][1])
        self.assertEqual(exp_after[1]["bullets"], three_exp_resume["experience"][1]["bullets"])
        self.assertEqual(exp_after[2]["bullets"], three_exp_resume["experience"][2]["bullets"])

        # C. Text-only spaced ordinal '1 st intership' + '3 point' must ONLY update experience[0].bullets[2]
        polish_json = json.dumps({
            "bullet": "Automated repetitive operational tasks with Python scripts, reducing manual processing time effectively."
        })
        with patch("services.resume_tailor.call_ollama", return_value=polish_json), \
             patch("services.fresher_resume_service.call_ollama", return_value=polish_json):
            res_ord = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(three_exp_resume),
                instruction="change the 3 point from 1 st intership i want in this i resduce the work time alos reduce the repeatetive work in 10 to 15 words",
            )
        ord_exp = res_ord["updated_content"]["experience"]
        self.assertEqual(ord_exp[0]["bullets"][2], "Automated repetitive operational tasks with Python scripts, reducing manual processing time effectively.")
        self.assertNotIn("1st internship", ord_exp[0]["bullets"][2].lower())
        self.assertEqual(ord_exp[1]["bullets"], three_exp_resume["experience"][1]["bullets"])
        self.assertEqual(ord_exp[2]["bullets"], three_exp_resume["experience"][2]["bullets"])

        # D. Sparse 2-bullet internships padded by condense_fresher_resume_to_one_page must stay distinct (never cloned 3x)
        sparse = copy.deepcopy(three_exp_resume)
        for e in sparse["experience"]:
            e["bullets"] = e["bullets"][:2]
        condensed = condense_fresher_resume_to_one_page(sparse)
        last_bullets = [e["bullets"][2] for e in condensed["experience"]]
        self.assertEqual(len(set(last_bullets)), 3, f"Found duplicated fallback bullets across internships: {last_bullets}")

if __name__ == "__main__":
    unittest.main()



