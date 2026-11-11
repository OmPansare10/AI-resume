import unittest
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from services.resume_tailor import (
    calculate_experience_from_april_2025,
    is_jd_demanding_experience,
    build_tailored_summary,
    apply_direct_user_instructions,
    edit_tailored_resume
)
from services.fresher_resume_service import (
    condense_fresher_resume_to_one_page,
    edit_single_page_fresher_resume
)


class TestSummaryExperienceLogic(unittest.TestCase):

    def test_calculate_experience_from_april_2025(self):
        """Verify dynamic calculation of experience from April 2025 baseline."""
        # 14 months -> June 2026
        d_14m = datetime(2026, 6, 1)
        m14, phrase14 = calculate_experience_from_april_2025(d_14m)
        self.assertEqual(m14, 14)
        self.assertEqual(phrase14, "over 1 year of hands-on engineering experience")

        # 19 months -> November 2026
        d_19m = datetime(2026, 11, 1)
        m19, phrase19 = calculate_experience_from_april_2025(d_19m)
        self.assertEqual(m19, 19)
        self.assertEqual(phrase19, "over 1.5 years of hands-on engineering experience")

        # 24 months -> April 2027
        d_24m = datetime(2027, 4, 1)
        m24, phrase24 = calculate_experience_from_april_2025(d_24m)
        self.assertEqual(m24, 24)
        self.assertEqual(phrase24, "over 2 years of hands-on engineering experience")

        # 30 months -> October 2027
        d_30m = datetime(2027, 10, 1)
        m30, phrase30 = calculate_experience_from_april_2025(d_30m)
        self.assertEqual(m30, 30)
        self.assertEqual(phrase30, "over 2.5 years of hands-on engineering experience")

    def test_is_jd_demanding_experience(self):
        """Verify distinction between experienced JDs and fresher/internship JDs."""
        jd_exp_4yr = "Software Engineer required. Must have 4+ years of experience in Python and FastAPI backend development."
        jd_exp_3yr = "Backend Developer with minimum 3 years of work experience."
        jd_fresher = "Hiring Fresher Software Engineers / Interns. Graduate trainee program. Python and SQL basics."
        jd_campus = "Campus placement for entry-level developers. 0-1 years experience, knowledge of data structures."

        self.assertTrue(is_jd_demanding_experience(jd_exp_4yr))
        self.assertTrue(is_jd_demanding_experience(jd_exp_3yr))
        self.assertFalse(is_jd_demanding_experience(jd_fresher))
        self.assertFalse(is_jd_demanding_experience(jd_campus))

    def test_build_tailored_summary_never_inflates_to_4_years(self):
        """
        Verify that even if JD demands 4+ years of experience, summary NEVER invents 4+ years,
        and strictly uses authentic calculated experience from April 2025.
        """
        jd_exp_4yr = "Software Engineer needed. 4+ years of hands-on experience in Python and PostgreSQL."
        jd_profile = {
            "primary_language": "Python",
            "frameworks": ["FastAPI"],
            "databases": ["PostgreSQL", "Redis"]
        }
        # In Nov 2026 (19 months)
        now_nov_2026 = datetime(2026, 11, 1)
        summary = build_tailored_summary(
            jd_profile=jd_profile,
            jd_text=jd_exp_4yr,
            role_title="Software Engineer",
            now=now_nov_2026
        )

        # Must not claim 4+ years
        self.assertNotIn("4+ years", summary)
        self.assertNotIn("4 years", summary)
        # Must claim authentic calculated experience
        self.assertIn("over 1.5 years of hands-on engineering experience", summary)
        # Must be at least 3 sentences
        sentences = [s.strip() for s in summary.split(". ") if s.strip()]
        self.assertGreaterEqual(len(sentences), 3)

    def test_build_tailored_summary_for_fresher_omits_years(self):
        """
        Verify that for fresher JDs, years of experience are omitted and
        hands-on internship experience is highlighted.
        """
        jd_fresher = "Hiring Fresher / Intern Software Engineer. Entry level trainee. Knowledge of Python."
        jd_profile = {
            "primary_language": "Python",
            "frameworks": ["FastAPI"],
            "databases": ["PostgreSQL", "Redis"]
        }
        summary = build_tailored_summary(
            jd_profile=jd_profile,
            jd_text=jd_fresher,
            role_title="Software Engineer"
        )

        self.assertNotIn("years of", summary)
        self.assertNotIn("1.5 years", summary)
        self.assertIn("extensive hands-on internship experience", summary)
        sentences = [s.strip() for s in summary.split(". ") if s.strip()]
        self.assertGreaterEqual(len(sentences), 3)

    def test_condense_fresher_preserves_three_line_summary_and_calculated_exp(self):
        """
        Verify that 1-page condensing preserves all 3 full sentences and does not strip
        valid calculated experience (e.g. over 1.5 years).
        """
        sample_sum = (
            "Results-driven Software Engineer with over 1.5 years of hands-on engineering experience designing, "
            "developing, and deploying scalable backend microservices and RESTful APIs using Python, FastAPI, and PostgreSQL, Redis. "
            "Proficient in database schema design, indexing, and query optimization across PostgreSQL, Redis, alongside asynchronous "
            "distributed messaging and Redis caching layers. Proven track record of containerizing microservices with Docker, integrating "
            "automated CI/CD pipelines, and delivering resilient, production-grade software solutions with 99.9% uptime."
        )
        sample_data = {
            "name": "Om Pansare",
            "summary": sample_sum,
            "education": [{"degree": "B.E.", "institution": "College", "year": "2026"}],
            "experience": [{"role": "Intern", "company": "Tech Corp", "bullets": ["Bullet 1.", "Bullet 2.", "Bullet 3."]}],
            "projects": [{"name": "P1", "technologies": "Python", "bullets": ["B1.", "B2.", "B3."]}],
            "skills": {"languages": ["Python", "Java"]}
        }
        condensed = condense_fresher_resume_to_one_page(sample_data)
        # Valid experience preserved
        self.assertIn("over 1.5 years of hands-on engineering experience", condensed["summary"])
        # All 3 sentences intact
        sentences = [s.strip() for s in condensed["summary"].split(". ") if s.strip()]
        self.assertGreaterEqual(len(sentences), 3)

    def test_copilot_best_summary_instruction(self):
        """Verify that user copilot chat asking for best summary / 3 lines generates the calculated 3-line summary."""
        content = {
            "name": "Om Pansare",
            "job_title": "Software Engineer",
            "summary": "Short 1 line summary.",
            "skills": {"languages": ["Python", "FastAPI"], "databases": ["PostgreSQL", "Redis"]}
        }
        inst = "in this summary section i want best summary at list 3 line summary and calculate experiece from april 2025"
        updated, changes = apply_direct_user_instructions(
            resume_content=content,
            instruction=inst
        )
        sentences = [s.strip() for s in updated["summary"].split(". ") if s.strip()]
        self.assertGreaterEqual(len(sentences), 3)
        self.assertIn("over 1.5 years of hands-on engineering experience", updated["summary"])
        self.assertTrue(any("summary" in c.lower() for c in changes))


if __name__ == "__main__":
    unittest.main()
