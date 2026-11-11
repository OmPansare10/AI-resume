"""Regression tests verifying Single-Page and Multi-Page PDF & DOCX parity."""

import os
import sys
import unittest
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

import docx
import pymupdf as fitz

from services.fresher_resume_service import (
    generate_single_page_docx,
    generate_single_page_pdf,
)
from services.resume_generator import generate_docx, generate_pdf


def _sample_ai_engineer_resume() -> dict:
    return {
        "name": "OM PANSARE",
        "contact": {
            "email": "om.pansare10@gmail.com",
            "phone": "+91 92849 75854",
            "location": "Pune, Maharashtra",
            "linkedin": "https://www.linkedin.com/in/om-pansare-10/",
            "github": "https://github.com/ompansare",
        },
        "summary": (
            "Results-driven AI Engineer with extensive hands-on internship experience building AI/ML, "
            "Generative AI (GenAI), Agentic AI, and LLMs solutions using Python and modern AI frameworks. "
            "Skilled in engineering LLM workflows, prompt engineering, RAG pipelines, and autonomous AI agent "
            "orchestration with LangChain, LangGraph, and Hugging Face backed by PostgreSQL (pgvector) and FAISS."
        ),
        "skills": {
            "Targeted JD Stack": ["Python", "AI / ML", "GenAI", "Agentic AI", "LLMs", "MLOps", "AI Frameworks"],
            "AI Frameworks & Libraries": ["LangChain", "LangGraph", "Hugging Face", "PyTorch", "Scikit-learn"],
            "Databases & Vector Stores": ["PostgreSQL (pgvector)", "FAISS", "Redis", "MySQL", "MongoDB"],
            "MLOps & Cloud": ["Docker", "Git", "CI/CD", "REST APIs"],
            "Languages": ["Java", "Python", "JavaScript", "SQL", "C++"],
            "Backend": ["Spring Boot", "REST APIs", "JDBC", "JSP", "Servlets"],
            "Frontend": ["React.js", "HTML", "CSS"],
            "Testing": ["JUnit", "TestNG", "Selenium WebDriver", "Postman", "REST Assured"],
            "Core Concepts": ["OOP", "DSA", "DBMS", "SDLC", "STLC"],
            "Tools": ["Git", "GitHub", "Eclipse", "VS Code", "Jenkins"],
            "Methodologies": ["Agile/Scrum", "CI/CD", "Debugging"],
        },
        "experience": [
            {
                "role": "Software Engineer Intern",
                "company": "Automaton AI Infosystem",
                "duration": "Sep 2026 - Ongoing",
                "bullets": [
                    "Applied Python and modern AI frameworks (LangChain, LangGraph) to develop GenAI workflows.",
                    "Contributed to AI/ML and Agentic AI initiatives with structured prompt pipelines and evaluation.",
                    "Implemented MLOps best practices including containerized model-serving REST APIs with Docker.",
                ],
            },
            {
                "role": "Java Developer Intern",
                "company": "Mass IT Solution",
                "duration": "Jan 2025 \u2013 Mar 2025",
                "bullets": [
                    "Developed Java desktop applications using Java, MySQL, and JDBC with OOP principles.",
                    "Performed software testing, debugging, and SQL query validation to resolve application issues.",
                    "Validated CRUD operations, database functionality, and application performance.",
                ],
            },
            {
                "role": "Java Backend Intern",
                "company": "Infaneat Digital Marketing and Web Media",
                "duration": "Jul 2022 \u2013 Sep 2022",
                "bullets": [
                    "Developed authentication and backend features using Java, JSP, Servlets, MySQL, and JDBC.",
                    "Performed functional testing, debugging, and SQL validation to improve application quality.",
                    "Validated CRUD operations, database accuracy, and end-to-end backend workflows.",
                ],
            },
        ],
        "projects": [
            {
                "name": "Agentic AI Task Orchestrator",
                "technologies": "Python, Agentic AI, LLMs, LangChain, FastAPI, MLOps, Docker",
                "bullets": [
                    "Built a multi-step Agentic AI task planning engine in Python using LangChain and LangGraph.",
                    "Integrated LLM tool-calling with context retrieval in PostgreSQL (pgvector), cutting latency by 42%.",
                    "Established MLOps practices with Docker containerization and CI/CD evaluation checks.",
                ],
            },
            {
                "name": "GenAI & ML Food Waste Redistribution Platform",
                "technologies": "Python, AI / ML, GenAI, Scikit-learn, Hugging Face, FastAPI, MLOps",
                "bullets": [
                    "Developed AI/ML surplus-prediction pipelines in Python using Scikit-learn and data libraries.",
                    "Engineered a GenAI recommendation assistant powered by LLMs to match local donors.",
                    "Applied MLOps model tracking, validation tests, and containerized Docker REST endpoints.",
                ],
            },
            {
                "name": "Meet.AI \u2014 GenAI & Agentic Meeting Assistant",
                "technologies": "Python, GenAI, LLMs, Agentic AI, LangChain, PostgreSQL (pgvector), MLOps",
                "bullets": [
                    "Engineered a GenAI meeting intelligence pipeline in Python for real-time transcript summarization.",
                    "Designed an Agentic AI action-item extractor paired with semantic RAG indexing in PostgreSQL.",
                    "Implemented MLOps latency telemetry, prompt versioning, and Dockerized FastAPI endpoints.",
                ],
            },
        ],
        "education": [
            {
                "institution": "Smt. Kashibai Navale College of Engineering \u2014 Pune, Maharashtra",
                "degree": "Bachelor of Engineering in ENTC \u2013 8.35",
                "year": "2023\u20132026",
            },
            {
                "institution": "Government Polytechnic Pune \u2014 Pune, Maharashtra",
                "degree": "Diploma in Computer Engineering \u2013 80%",
                "year": "2020\u20132023",
            },
        ],
        "certifications": [
            "Generative AI with Large Language Models (DeepLearning.AI)",
            "AWS Certified AI Practitioner / Machine Learning Foundations",
            "Machine Learning Engineering for Production (MLOps) Specialization",
        ],
    }


def _collect_docx_text(doc: docx.Document) -> str:
    parts = [p.text for p in doc.paragraphs]
    for tbl in doc.tables:
        for row in tbl.rows:
            for cell in row.cells:
                parts.extend(p.text for p in cell.paragraphs)
    return "\n".join(parts)


class TestExportParity(unittest.TestCase):
    def setUp(self) -> None:
        self._created_files = []

    def tearDown(self) -> None:
        for fp in self._created_files:
            try:
                if fp and os.path.exists(fp):
                    os.remove(fp)
            except OSError:
                pass

    def _assert_pdf_matches_preview(self, pdf_path: Path, expect_single_page: bool) -> None:
        self._created_files.append(pdf_path)
        self.assertTrue(pdf_path.exists())

        with fitz.open(str(pdf_path)) as pdf_doc:
            if expect_single_page:
                self.assertEqual(len(pdf_doc), 1, f"Single-page PDF spilled onto {len(pdf_doc)} pages")
            else:
                self.assertGreaterEqual(len(pdf_doc), 1)

            first_rect = pdf_doc[0].rect
            self.assertAlmostEqual(first_rect.width, 595.0, delta=3.0)
            self.assertAlmostEqual(first_rect.height, 842.0, delta=3.0)

            full_text = "\n".join(page.get_text() for page in pdf_doc)
            links = pdf_doc[0].get_links()
            uris = {lnk.get("uri") for lnk in links if lnk.get("uri")}

        self.assertIn("https://www.linkedin.com/in/om-pansare-10/", uris)
        self.assertIn("https://github.com/ompansare", uris)

        # Ensure Summary is never silently dropped
        self.assertIn("Results-driven AI Engineer with extensive hands-on internship experience", full_text)
        # Ensure preview section names, 3 experiences, 3 projects, 2 educations, and certifications exist
        for expected in (
            "SUMMARY",
            "CORE SKILLS & TECHNOLOGIES",
            "EXPERIENCE",
            "KEY PROJECTS",
            "EDUCATION",
            "CERTIFICATIONS",
            "Software Engineer Intern | Automaton AI Infosystem",
            "Mass IT Solution",
            "Infaneat Digital Marketing and Web Media",
            "Jan 2025 \u2013 Mar 2025",
            "Agentic AI Task Orchestrator",
            "GenAI & ML Food Waste Redistribution Platform",
            "Meet.AI \u2014 GenAI & Agentic Meeting Assistant",
            "Smt. Kashibai Navale College of Engineering \u2014 Pune, Maharashtra",
            "Government Polytechnic Pune \u2014 Pune, Maharashtra",
            "Generative AI with Large Language Models (DeepLearning.AI)",
            "AWS Certified AI Practitioner / Machine Learning Foundations",
        ):
            self.assertIn(expected, full_text, f"Missing expected PDF text: {expected!r}")

        # Ensure zero '?' replacement glyphs or extraction artifacts from broken fonts
        self.assertNotIn("? Jan 2025", full_text)
        self.assertNotIn("? Mar 2025", full_text)
        self.assertNotIn("Meet.AI ?", full_text)
        self.assertNotIn("\xa0", full_text)
        self.assertNotIn("\xad", full_text)

    def _assert_docx_matches_preview(self, docx_path: Path) -> None:
        self._created_files.append(docx_path)
        self.assertTrue(docx_path.exists())

        word_doc = docx.Document(str(docx_path))
        section = word_doc.sections[0]
        # Verify explicit A4 dimensions (8.27 x 11.69 inches)
        self.assertAlmostEqual(section.page_width.inches, 8.27, delta=0.05)
        self.assertAlmostEqual(section.page_height.inches, 11.69, delta=0.05)

        full_text = _collect_docx_text(word_doc)
        for expected in (
            "OM PANSARE",
            "Results-driven AI Engineer with extensive hands-on internship experience",
            "CORE SKILLS & TECHNOLOGIES",
            "Software Engineer Intern  |  Automaton AI Infosystem",
            "Java Backend Intern  |  Infaneat Digital Marketing and Web Media",
            "Jan 2025 \u2013 Mar 2025",
            "Agentic AI Task Orchestrator",
            "Meet.AI \u2014 GenAI & Agentic Meeting Assistant",
            "Smt. Kashibai Navale College of Engineering \u2014 Pune, Maharashtra",
            "Bachelor of Engineering in ENTC - 8.35",
            "Government Polytechnic Pune \u2014 Pune, Maharashtra",
            "Generative AI with Large Language Models (DeepLearning.AI)",
        ):
            self.assertIn(expected, full_text, f"Missing expected DOCX text: {expected!r}")

        xml_str = word_doc.element.xml
        self.assertIn("hyperlink", xml_str)

    def test_single_and_multi_page_pdf_parity(self) -> None:
        data = _sample_ai_engineer_resume()
        self._assert_pdf_matches_preview(generate_single_page_pdf(data), expect_single_page=True)
        self._assert_pdf_matches_preview(generate_pdf(data), expect_single_page=False)

    def test_single_and_multi_page_docx_parity(self) -> None:
        data = _sample_ai_engineer_resume()
        self._assert_docx_matches_preview(generate_single_page_docx(data))
        self._assert_docx_matches_preview(generate_docx(data))


if __name__ == "__main__":
    unittest.main()
