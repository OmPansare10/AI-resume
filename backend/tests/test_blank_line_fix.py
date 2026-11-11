"""
Regression tests for preventing accidental project/experience deletion when
asking Copilot to remove blank lines / extra whitespace (including with attached screenshots),
while keeping explicit project removal ('Remove project 2') intact.
"""

import copy
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from services.resume_tailor import (
    apply_direct_user_instructions,
    apply_surgical_edit_post_merge,
)
from services.fresher_resume_service import edit_single_page_fresher_resume


def _sample_resume():
    return {
        "name": "Om Pansare",
        "email": "om.pansare10@gmail.com",
        "phone": "+91 92849 75854",
        "location": "Pune, Maharashtra",
        "summary": "Results-driven AI Engineer.\n\nSkilled in Python and GenAI.",
        "skills": {
            "TARGETED JD STACK": "Python, AI / ML, GenAI, Agentic AI, LLMs",
        },
        "experience": [
            {
                "role": "Software Engineer Intern",
                "company": "Automaton AI Infosystem",
                "duration": "Sep 2026 - Ongoing",
                "bullets": [
                    "Applied Python and modern AI frameworks to develop GenAI workflows.",
                    "   ",
                    "Implemented MLOps best practices\n\nwith Docker and CI/CD.",
                ],
            }
        ],
        "projects": [
            {
                "name": "Agentic AI Task Orchestrator",
                "technologies": "Python, Agentic AI, LLMs, LangChain, FastAPI, MLOps, Docker",
                "bullets": [
                    "Built a multi-step Agentic AI task planning engine in Python using LangChain.",
                    "Integrated LLM tool-calling with persistent context state in PostgreSQL (pgvector), reducing manual task triage latency by 42%.",
                    "Established MLOps practices with Docker containerization, automated prompt evaluation benchmarks, and CI/CD deployment via FastAPI\n\n",
                    "",
                ],
            },
            {
                "name": "GenAI & ML Food Waste Redistribution Platform",
                "technologies": "Python, AI / ML, GenAI, Scikit-learn, Hugging Face, FastAPI, MLOps",
                "bullets": [
                    "Developed AI/ML surplus-prediction pipelines in Python using Scikit-learn.",
                    "Engineered a GenAI recommendation assistant powered by LLMs.",
                ],
            },
            {
                "name": "Meet.AI — GenAI & Agentic Meeting Assistant",
                "technologies": "Python, GenAI, LLMs, Agentic AI, LangChain, PostgreSQL (pgvector), MLOps",
                "bullets": [
                    "Engineered a GenAI meeting intelligence pipeline in Python leveraging LLMs and LangChain.",
                    "Designed an Agentic AI action-item extractor paired with semantic RAG indexing.",
                ],
            },
        ],
        "education": [
            {
                "institution": "Smt. Kashibai Navale College of Engineering",
                "degree": "Bachelor of Engineering in ENTC",
                "year": "2023-2026",
            }
        ],
        "certifications": ["Generative AI with Large Language Models", "   "],
    }


OCR_SNIPPET = (
    "42%.\n"
    "Established MLOps practices with Docker containerization, automated prompt evaluation benchmarks, and CI/CD deployment via FastAPI\n\n"
    "Meet.AI — GenAI & Agentic Meeting Assistant (Python, GenAI, LLMs, Agentic AI, LangChain, PostgreSQL (pgvector), MLOps)\n"
    "Engineered a Generative AI (GenAI) meeting intelligence pipeline in Python leveraging LLMs and LangChain."
)


class BlankLineFixTests(unittest.TestCase):
    def test_direct_remove_blank_line_with_project_screenshot_preserves_all_projects(self):
        resume = _sample_resume()
        updated, notes = apply_direct_user_instructions(
            resume_content=copy.deepcopy(resume),
            instruction="remove blank line in this",
            attached_images=["dummy_img"],
            ocr_text=OCR_SNIPPET,
        )

        proj_names = [p["name"] for p in updated.get("projects", [])]
        self.assertEqual(len(proj_names), 3)
        self.assertIn("Agentic AI Task Orchestrator", proj_names)
        self.assertIn("GenAI & ML Food Waste Redistribution Platform", proj_names)
        self.assertIn("Meet.AI — GenAI & Agentic Meeting Assistant", proj_names)

        # Verify empty bullets and embedded blank lines were cleaned across sections
        self.assertEqual(len(updated["projects"][0]["bullets"]), 3)
        for p in updated["projects"]:
            for b in p["bullets"]:
                self.assertNotIn("\n", b)
                self.assertTrue(b.strip())

        self.assertEqual(len(updated["experience"][0]["bullets"]), 2)
        for b in updated["experience"][0]["bullets"]:
            self.assertNotIn("\n", b)
        self.assertNotIn("\n", updated["summary"])
        self.assertEqual(len(updated["certifications"]), 1)
        self.assertTrue(any("blank line" in n.lower() for n in notes))

    def test_chat2_remove_blank_line_with_screenshot_keeps_all_projects_and_cleans_newlines(self):
        resume = _sample_resume()
        fake_b64 = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="

        with patch("services.fresher_resume_service.extract_text_from_image_b64", return_value=OCR_SNIPPET), \
             patch("services.resume_tailor.call_ollama", side_effect=RuntimeError("offline")):
            res = edit_single_page_fresher_resume(
                resume_content=copy.deepcopy(resume),
                instruction="remove blank line in this",
                image_data=fake_b64,
                base_tailored_resume=copy.deepcopy(resume),
            )

        updated = res["updated_content"]
        proj_names = [p["name"] for p in updated.get("projects", [])]
        self.assertEqual(len(proj_names), 3)
        self.assertIn("Meet.AI — GenAI & Agentic Meeting Assistant", proj_names)
        for p in updated["projects"]:
            for b in p["bullets"]:
                self.assertNotIn("\n", b)
                self.assertTrue(b.strip())

    def test_explicit_remove_project_2_still_works(self):
        resume = _sample_resume()
        res = edit_single_page_fresher_resume(
            resume_content=copy.deepcopy(resume),
            instruction="Remove project 2",
            base_tailored_resume=copy.deepcopy(resume),
        )
        proj_names = [p["name"] for p in res["updated_content"].get("projects", [])]
        self.assertEqual(len(proj_names), 2)
        self.assertNotIn("GenAI & ML Food Waste Redistribution Platform", proj_names)
        self.assertIn("Agentic AI Task Orchestrator", proj_names)
        self.assertIn("Meet.AI — GenAI & Agentic Meeting Assistant", proj_names)

    def test_post_merge_restores_projects_dropped_by_llm_on_non_removal_instruction(self):
        pre = _sample_resume()
        post = copy.deepcopy(pre)
        # Simulate LLM accidentally dropping Meet.AI during a spacing cleanup instruction
        post["projects"] = post["projects"][:2]

        merged = apply_surgical_edit_post_merge(
            pre_resume=pre,
            post_resume=post,
            target_info={"section": "projects", "is_bulk": True},
            instruction="clean up spacing",
        )
        proj_names = [p["name"] for p in merged.get("projects", [])]
        self.assertEqual(len(proj_names), 3)
        self.assertIn("Meet.AI — GenAI & Agentic Meeting Assistant", proj_names)


if __name__ == "__main__":
    unittest.main()

