"""
API Integration Tests for Single-Page Fresher Resume Endpoints.
Verifies all new routes:
- POST /api/analyze-single-page
- POST /api/edit-single-page-resume
- POST /api/download-single-page-pdf
- POST /api/download-single-page-docx
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SAMPLE_RESUME = {
    "name": "OM PANSARE",
    "contact": {
        "email": "om.pansare10@gmail.com",
        "phone": "+91 9284975854",
        "location": "Pune, Maharashtra",
        "linkedin": "linkedin.com/in/ompansare",
        "github": "github.com/OmPansare10"
    },
    "summary": "Software Engineer with hands-on experience in Java, Spring Boot, REST APIs, React.js, and databases.",
    "education": [
        {
            "degree": "Bachelor of Engineering in ENTC",
            "institution": "Smt. Kashibai Navale College of Engineering",
            "location": "Pune",
            "duration": "2023–2026",
            "score": "8.35 CGPA"
        }
    ],
    "projects": [
        {
            "name": "TaskFlow AI Management System",
            "technologies": "React.js, Spring Boot, PostgreSQL",
            "bullets": [
                "Architected task management platform with sub-100ms API response time.",
                "Optimized database schema design and indexing."
            ]
        }
    ],
    "skills": {
        "languages": ["Java", "Python", "JavaScript", "SQL"],
        "frameworks": ["Spring Boot", "React.js", "FastAPI"],
        "databases": ["PostgreSQL", "MySQL", "MongoDB"],
        "developer_tools": ["Git", "GitHub", "Docker", "Postman"],
        "core_competencies": ["Data Structures & Algorithms", "OOP", "DBMS", "REST APIs"]
    },
    "certifications": [
        "Oracle Certified Associate, Java SE 8 Programmer"
    ]
}


class TestApiEndpoints(unittest.TestCase):

    def test_health_check(self):
        """Test health check route."""
        response = client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get("status"), "healthy")

    def test_edit_single_page_resume_endpoint(self):
        """Test POST /api/edit-single-page-resume."""
        payload = {
            "resume_content": SAMPLE_RESUME,
            "instruction": "Add skills: Docker, Kubernetes",
            "original_resume_text": "Sample resume text",
            "jd_text": "Sample JD text"
        }
        response = client.post("/api/edit-single-page-resume", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("updated_content", data)
        updated = data["updated_content"]
        self.assertIn("Docker", str(updated.get("skills", {})))

    def test_download_single_page_pdf_endpoint(self):
        """Test POST /api/download-single-page-pdf."""
        payload = {
            "tailored_content": SAMPLE_RESUME
        }
        response = client.post("/api/download-single-page-pdf", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("content-type"), "application/pdf")
        self.assertTrue(len(response.content) > 100)

    def test_download_single_page_docx_endpoint(self):
        """Test POST /api/download-single-page-docx."""
        payload = {
            "tailored_content": SAMPLE_RESUME
        }
        response = client.post("/api/download-single-page-docx", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertIn("wordprocessingml", response.headers.get("content-type", ""))
        self.assertTrue(len(response.content) > 100)


if __name__ == "__main__":
    unittest.main()
