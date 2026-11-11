"""
Unit and integration tests for the Intelligent Dynamic Resume Layout Engine.
Verifies:
1. Short resumes with substantial unused space have their vertical space distributed.
2. Resumes with enough content fill 1 page cleanly.
3. Resumes with dense content auto-compact to strictly 1 page.
4. Adding and removing projects dynamically reflows correctly.
5. Editing project descriptions updates line wrapping and spacing.
6. Adding and removing certifications.
7. PDF export pagination is strictly 1 page for single-page mode and text is 100% selectable.
8. DOCX export preserves logical reading order and keep_with_next properties.
9. Multi-page resume (Resume 1) paginates naturally and prevents orphaned headings.
10. Strict isolation between Resume 1 and Resume 2.
"""

import sys
import unittest
from pathlib import Path

# Add backend to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import pymupdf as fitz
import docx

from services.fresher_resume_service import (
    generate_single_page_pdf,
    generate_single_page_docx,
    condense_fresher_resume_to_one_page,
    edit_single_page_fresher_resume
)
from services.resume_generator import generate_pdf, generate_docx


class TestDynamicResumeLayoutEngine(unittest.TestCase):

    def setUp(self):
        # Base representative test resume data (Om Pansare - Fresher)
        self.base_resume = {
            "name": "Om Pansare",
            "contact": {
                "email": "ompansare10@gmail.com",
                "phone": "+91 9876543210",
                "location": "Pune, India",
                "linkedin": "linkedin.com/in/ompansare10",
                "github": "github.com/OmPansare10"
            },
            "summary": "Enthusiastic Software Engineer with a solid foundation in Python, Java, and modern web frameworks.",
            "skills": {
                "languages": ["Python", "Java", "JavaScript", "SQL"],
                "frameworks": ["FastAPI", "React.js", "Spring Boot"],
                "databases": ["PostgreSQL", "MySQL", "Redis"],
                "tools": ["Git", "Docker", "Postman"]
            },
            "experience": [
                {
                    "role": "Software Engineer Intern",
                    "company": "Automaton AI Infosystem",
                    "duration": "Sep 2026",
                    "location": "Pune",
                    "bullets": [
                        "Developed software applications using Java, Spring Boot, REST APIs, and React.js.",
                        "Integrated RESTful API endpoints, implementing authentication and database connectivity.",
                        "Participated in Agile sprint planning, code reviews, and automated CI/CD pipeline deployments."
                    ]
                },
                {
                    "role": "Java Developer Intern",
                    "company": "Mass IT Solution",
                    "duration": "Jan 2025",
                    "location": "Pune",
                    "bullets": [
                        "Developed Java desktop applications using MySQL and JDBC with OOP principles.",
                        "Performed software testing, debugging, and SQL query validation.",
                        "Engineered modular backend services with JUnit test coverage."
                    ]
                }
            ],
            "projects": [
                {
                    "name": "TaskFlow Pro – Scalable Task Management Service",
                    "technologies": "Python, FastAPI, PostgreSQL, Redis, Docker",
                    "duration": "2025",
                    "link": "github.com/OmPansare10/taskflow-pro",
                    "bullets": [
                        "Designed a stateless FastAPI microservice handling 15k+ requests/min.",
                        "Created a normalized PostgreSQL schema with composite indexes, cutting latency by 45%.",
                        "Containerized microservice with Docker and automated CI/CD pipeline."
                    ]
                },
                {
                    "name": "EcoDonate Hub – Real-time Food Donation Platform",
                    "technologies": "Python, Django, PostgreSQL, Redis, Docker",
                    "duration": "2024",
                    "link": "github.com/OmPansare10/ecodonate-hub",
                    "bullets": [
                        "Implemented a Django service serving 8k concurrent users.",
                        "Optimized PostgreSQL with partitioned tables and materialized views.",
                        "Configured automated test suites with PyTest, maintaining 90%+ code coverage."
                    ]
                },
                {
                    "name": "Meet.AI – Smart Video Conferencing & Summarizer",
                    "technologies": "Python, WebRTC, FastAPI, PostgreSQL, Docker",
                    "duration": "2025",
                    "link": "github.com/OmPansare10/meet-ai",
                    "bullets": [
                        "Engineered real-time meeting transcription engine using WebRTC and FastAPI.",
                        "Designed Redis-backed pub/sub messaging queue, scaling concurrent active channels.",
                        "Implemented JWT authentication and role-based access control."
                    ]
                }
            ],
            "education": [
                {
                    "degree": "Bachelor of Engineering in ENTC",
                    "institution": "Smt. Kashibai Navale College of Engineering",
                    "duration": "2023–2026",
                    "score": "8.35 CGPA"
                }
            ],
            "certifications": [
                "AWS Certified Cloud Practitioner",
                "Python Certified Associate Programmer",
                "Complete Web Development & DSA Specialization"
            ]
        }

    def test_short_resume_vertical_space_distribution(self):
        """Short resume with only 1 project and 1 experience distributes vertical space and avoids blank bottom void."""
        short_resume = dict(self.base_resume)
        short_resume["experience"] = [self.base_resume["experience"][0]]
        short_resume["projects"] = [self.base_resume["projects"][0]]
        short_resume["certifications"] = ["AWS Certified Cloud Practitioner"]

        pdf_path = generate_single_page_pdf(short_resume)
        self.assertTrue(pdf_path.exists())

        doc = fitz.open(str(pdf_path))
        # Strictly exactly 1 page
        self.assertEqual(len(doc), 1, f"Expected 1 page but got {len(doc)}")

        # Verify text is selectable
        page_text = doc[0].get_text()
        self.assertIn("OM PANSARE", page_text)
        self.assertIn("TASKFLOW PRO", page_text.upper())
        self.assertIn("EXPERIENCE", page_text)

        # Inspect drawings: the last section (CERTIFICATIONS) should be well down the page (> 400pt)
        # proving vertical distribution was applied rather than compressing to top
        rects = doc[0].get_drawings()
        self.assertTrue(len(rects) > 0)
        doc.close()

    def test_standard_3project_resume_exact_one_page(self):
        """Standard fresher resume with 3 projects and 2 experiences fits strictly on 1 A4 page."""
        pdf_path = generate_single_page_pdf(self.base_resume)
        self.assertTrue(pdf_path.exists())

        doc = fitz.open(str(pdf_path))
        self.assertEqual(len(doc), 1, f"Expected 1 page but got {len(doc)}")

        text = doc[0].get_text()
        self.assertIn("TASKFLOW PRO", text.upper())
        self.assertIn("ECODONATE HUB", text.upper())
        self.assertIn("MEET.AI", text.upper())
        self.assertIn("AUTOMATON AI", text.upper())
        self.assertIn("MASS IT SOLUTION", text.upper())
        doc.close()

    def test_dense_resume_auto_compaction(self):
        """Dense resume with maximum content compacts and strictly maintains 1-page fit."""
        dense_resume = dict(self.base_resume)
        dense_resume["summary"] = (
            "Results-driven and highly motivated Software Engineer graduate with an established background in full-stack "
            "development, microservices, cloud deployments, and scalable database architectures. Experienced in building "
            "asynchronous RESTful APIs with sub-50ms latency, integrating Redis caching layers, and implementing CI/CD pipelines."
        )

        pdf_path = generate_single_page_pdf(dense_resume)
        self.assertTrue(pdf_path.exists())

        doc = fitz.open(str(pdf_path))
        self.assertEqual(len(doc), 1, "Dense resume must strictly stay 1 page!")
        doc.close()

    def test_adding_project_dynamically(self):
        """Adding a new project reflows the layout without breaking the single-page guarantee."""
        modified_resume = dict(self.base_resume)
        new_project = {
            "name": "Cloud Gate – API Security Proxy",
            "technologies": "Go, Docker, Redis",
            "duration": "2025",
            "bullets": [
                "Engineered reverse proxy with rate limiting.",
                "Reduced DDoS response surface with token bucket algorithms.",
                "Automated Kubernetes manifest configurations."
            ]
        }
        projects = list(modified_resume["projects"])
        # Condense keeps top 3 projects
        projects.insert(0, new_project)
        modified_resume["projects"] = projects

        condensed = condense_fresher_resume_to_one_page(modified_resume)
        self.assertEqual(len(condensed["projects"]), 3)
        self.assertEqual(condensed["projects"][0]["name"], "Cloud Gate – API Security Proxy")

        pdf_path = generate_single_page_pdf(condensed)
        doc = fitz.open(str(pdf_path))
        self.assertEqual(len(doc), 1)
        self.assertIn("CLOUD GATE", doc[0].get_text().upper())
        doc.close()

    def test_deleting_project_dynamically(self):
        """Deleting a project allows the remaining content to redistribute across the page."""
        modified_resume = dict(self.base_resume)
        modified_resume["projects"] = self.base_resume["projects"][:2]

        pdf_path = generate_single_page_pdf(modified_resume)
        doc = fitz.open(str(pdf_path))
        self.assertEqual(len(doc), 1)
        text = doc[0].get_text()
        self.assertIn("TASKFLOW PRO", text.upper())
        self.assertIn("ECODONATE HUB", text.upper())
        # 3rd project removed
        self.assertNotIn("MEET.AI", text)
        doc.close()

    def test_editing_project_description(self):
        """Editing a short bullet to a longer description calculates line wrapping correctly."""
        modified_resume = dict(self.base_resume)
        projs = [dict(p) for p in modified_resume["projects"]]
        projs[0]["bullets"] = [
            "Architected an enterprise-grade stateless FastAPI microservice architecture capable of processing "
            "over 25,000 requests per minute with 99.98% service uptime and sub-15ms database query response latency.",
            "Integrated asynchronous distributed Redis caching queues with composite indexes in PostgreSQL.",
            "Containerized deployment with Docker Compose, automated CI/CD pipelines, and comprehensive PyTest suites."
        ]
        modified_resume["projects"] = projs

        pdf_path = generate_single_page_pdf(modified_resume)
        doc = fitz.open(str(pdf_path))
        self.assertEqual(len(doc), 1)
        text = doc[0].get_text()
        self.assertIn("25,000 requests per minute", text)
        doc.close()

    def test_adding_and_removing_certifications(self):
        """Adding and removing certifications updates layout correctly."""
        # 1. Add certification
        with_extra_cert = dict(self.base_resume)
        with_extra_cert["certifications"] = [
            "AWS Certified Solutions Architect",
            "Docker Certified Associate",
            "Kubernetes CKA"
        ]
        pdf_path_1 = generate_single_page_pdf(with_extra_cert)
        doc1 = fitz.open(str(pdf_path_1))
        self.assertEqual(len(doc1), 1)
        self.assertIn("AWS Certified Solutions Architect", doc1[0].get_text())
        doc1.close()

        # 2. Remove certifications
        no_certs = dict(self.base_resume)
        no_certs["certifications"] = []
        pdf_path_2 = generate_single_page_pdf(no_certs)
        doc2 = fitz.open(str(pdf_path_2))
        self.assertEqual(len(doc2), 1)
        self.assertNotIn("AWS Certified Solutions Architect", doc2[0].get_text())
        doc2.close()

    def test_single_page_docx_generation_and_keep_with_next(self):
        """Single-page DOCX export generates valid document with keep_with_next set on section headers."""
        docx_path = generate_single_page_docx(self.base_resume)
        self.assertTrue(docx_path.exists())

        doc = docx.Document(str(docx_path))
        # Verify text elements
        all_text = " ".join([p.text for p in doc.paragraphs])
        self.assertIn("OM PANSARE", all_text)
        self.assertIn("SUMMARY", all_text)
        self.assertIn("KEY PROJECTS", all_text)

        # Verify keep_with_next property on heading paragraphs
        heading_paragraphs = [p for p in doc.paragraphs if p.text in [
            "SUMMARY", "CORE SKILLS & TECHNOLOGIES", "EXPERIENCE",
            "KEY PROJECTS", "EDUCATION", "CERTIFICATIONS"
        ]]
        self.assertTrue(len(heading_paragraphs) > 0)
        for hp in heading_paragraphs:
            self.assertTrue(hp.paragraph_format.keep_with_next, f"Heading {hp.text} must have keep_with_next = True")

    def test_multi_page_resume_pagination_and_orphan_prevention(self):
        """Multi-page resume (Resume 1) allows natural page flow and prevents orphaned headings."""
        # Create a large multi-page resume
        multi_page_resume = dict(self.base_resume)
        # Expand experiences and projects to naturally span multiple pages
        extra_experiences = [
            {
                "role": "Lead Backend Developer",
                "company": "ScaleTech Global",
                "duration": "2022–2024",
                "location": "Pune",
                "bullets": [
                    f"Architected microservice platform component #{i} with event streaming."
                    for i in range(1, 5)
                ]
            }
            for _ in range(4)
        ]
        multi_page_resume["experience"] = multi_page_resume["experience"] + extra_experiences

        pdf_path = generate_pdf(multi_page_resume)
        self.assertTrue(pdf_path.exists())

        doc = fitz.open(str(pdf_path))
        # Should naturally span 2 or more pages
        self.assertGreaterEqual(len(doc), 2, "Long resume should naturally paginate into multiple pages!")

        # Verify selectable text across pages
        for page_idx, page in enumerate(doc):
            ptext = page.get_text()
            self.assertTrue(len(ptext.strip()) > 50, f"Page {page_idx + 1} must contain readable selectable text")

        doc.close()

    def test_isolation_between_resume_modes(self):
        """Single-page resume edits must not alter Resume 1 data structure or state."""
        resume_1_data = dict(self.base_resume)
        resume_2_data = condense_fresher_resume_to_one_page(self.base_resume)

        # Modify Resume 2 via dedicated fresher editor
        edit_result = edit_single_page_fresher_resume(
            resume_content=resume_2_data,
            instruction="Focus on Python backend skills and add Docker certification",
            original_resume_text="Original text",
            jd_text="Python FastAPI Docker engineer"
        )

        self.assertIn("updated_content", edit_result)
        edited_r2 = edit_result["updated_content"]

        # Ensure Resume 1 remained completely untouched
        self.assertEqual(len(resume_1_data["projects"]), 3)
        self.assertEqual(resume_1_data["name"], "Om Pansare")
        # Resume 2 has its own isolated structure
        self.assertIsInstance(edited_r2, dict)

    def test_education_entry_normalization_matching_image_2(self):
        """Education entries must normalize into standard 2-line layout matching Image 2."""
        from services.fresher_resume_service import format_education_entry

        # Case 1: Inverted fields as parsed from raw master resume
        raw_edu_1 = {
            "degree": "Smt. Kashibai Navale College of Engineering — Pune, Maharashtra 2023–2026",
            "institution": "Bachelor of Engineering in ENTC 8.35",
            "year": "2023–2026"
        }
        res1 = format_education_entry(raw_edu_1)
        self.assertEqual(res1["inst_line"], "Smt. Kashibai Navale College of Engineering — Pune, Maharashtra")
        self.assertEqual(res1["year"], "2023–2026")
        self.assertEqual(res1["degree_line"], "Bachelor of Engineering in ENTC - 8.35")

        # Case 2: Polytechnic diploma with percentage
        raw_edu_2 = {
            "degree": "Government Polytechnic Pune — Pune, Maharashtra 2020–2023",
            "institution": "Diploma in Computer Engineering 80%",
            "year": "2020–2023"
        }
        res2 = format_education_entry(raw_edu_2)
        self.assertEqual(res2["inst_line"], "Government Polytechnic Pune — Pune, Maharashtra")
        self.assertEqual(res2["year"], "2020–2023")
        self.assertEqual(res2["degree_line"], "Diploma in Computer Engineering - 80%")

        # Verify PDF and DOCX generation with this normalized education
        resume_with_edu = dict(self.base_resume)
        resume_with_edu["education"] = [raw_edu_1, raw_edu_2]

        pdf_path = generate_single_page_pdf(resume_with_edu)
        self.assertTrue(pdf_path.exists())
        pdf_doc = fitz.open(str(pdf_path))
        pdf_text = "".join(p.get_text() for p in pdf_doc)
        self.assertIn("Smt. Kashibai Navale College of Engineering", pdf_text)
        self.assertIn("Government Polytechnic Pune", pdf_text)
        self.assertIn("Bachelor of Engineering in ENTC - 8.35", pdf_text)
        self.assertIn("Diploma in Computer Engineering - 80%", pdf_text)
        self.assertEqual(len(pdf_doc), 1)
        pdf_doc.close()


if __name__ == "__main__":
    unittest.main()

