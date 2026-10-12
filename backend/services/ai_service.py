import json
import logging
import os
import re
from typing import Any, Dict, List, Optional
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b").strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()


def get_ollama_client_info() -> Dict[str, Any]:
    """
    Check AI connectivity:
    1. If GROQ_API_KEY is configured, uses ultra-fast zero-storage Cloud LLM.
    2. If OPENAI_API_KEY is configured, uses OpenAI Cloud.
    3. Otherwise, checks local Ollama server connectivity.
    """
    # 1. Groq Cloud Check
    if GROQ_API_KEY:
        return {
            "running": True,
            "provider": "groq",
            "model_configured": f"Groq Cloud ({GROQ_MODEL})",
            "model_found": True,
            "available_models": [GROQ_MODEL, "llama-3.1-8b-instant"],
            "error": None
        }

    # 2. OpenAI Cloud Check
    if OPENAI_API_KEY:
        return {
            "running": True,
            "provider": "openai",
            "model_configured": f"OpenAI Cloud ({OPENAI_MODEL})",
            "model_found": True,
            "available_models": [OPENAI_MODEL],
            "error": None
        }

    # 3. Local Ollama Check
    try:
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=3)
        if response.status_code == 200:
            data = response.json()
            models = [m.get("name", "") for m in data.get("models", [])]
            model_configured = OLLAMA_MODEL
            model_found = any(
                m == model_configured
                or m.startswith(f"{model_configured}:")
                or m.startswith(model_configured.split(":")[0])
                for m in models
            )
            return {
                "running": True,
                "provider": "ollama",
                "model_configured": model_configured,
                "model_found": model_found,
                "available_models": models,
                "error": None if model_found else f"Configured model '{model_configured}' was not found. Please run 'ollama pull {model_configured}'."
            }
        else:
            return {
                "running": False,
                "provider": "ollama",
                "model_configured": OLLAMA_MODEL,
                "model_found": False,
                "available_models": [],
                "error": f"Ollama returned HTTP status {response.status_code}."
            }
    except requests.exceptions.RequestException:
        return {
            "running": False,
            "provider": "ollama",
            "model_configured": OLLAMA_MODEL,
            "model_found": False,
            "available_models": [],
            "error": "Ollama is not running. Please start Ollama or set GROQ_API_KEY in backend/.env for zero-storage Cloud AI."
        }


def safe_extract_json(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Safely extract and parse JSON from an LLM response string.
    Handles markdown code blocks, preambles, and postambles.
    """
    if not raw_text or not raw_text.strip():
        return None

    cleaned = raw_text.strip()

    # 1. Strip markdown code fences if present
    fence_pattern = r"```(?:json)?\s*([\s\S]*?)\s*```"
    match = re.search(fence_pattern, cleaned, re.IGNORECASE)
    if match:
        cleaned = match.group(1).strip()

    # 2. Try direct json parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Find outermost curly braces
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = cleaned[start:end + 1]
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # Fix common trailing comma issues
            fixed = re.sub(r",\s*([}\]])", r"\1", candidate)
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

    logger.error("Failed to parse JSON from LLM response. Raw output:\n%s", raw_text)
    return None


def call_groq(prompt: str, system_prompt: str = "", temperature: float = 0.1, timeout_seconds: int = 60) -> str:
    """
    Call Groq Cloud API for lightning-fast Llama-3 inference without local disk usage.
    """
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: Dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": temperature,
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        if response.status_code != 200:
            error_msg = response.text
            try:
                error_data = response.json()
                error_msg = error_data.get("error", {}).get("message", error_msg)
            except Exception:
                pass
            raise RuntimeError(f"Groq API error ({response.status_code}): {error_msg}")
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except requests.exceptions.Timeout:
        raise RuntimeError("Groq Cloud request timed out. Please try again.")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise e
        raise RuntimeError(f"Groq API connection error: {str(e)}")


def call_openai(prompt: str, system_prompt: str = "", temperature: float = 0.1, timeout_seconds: int = 60) -> str:
    """
    Call OpenAI Cloud API.
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "temperature": temperature
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)
        if response.status_code != 200:
            raise RuntimeError(f"OpenAI error ({response.status_code}): {response.text}")
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        raise RuntimeError(f"OpenAI API connection error: {str(e)}")


def call_ollama_local(prompt: str, system_prompt: str = "", temperature: float = 0.1, timeout_seconds: int = 300) -> str:
    """
    Send prompt to local Ollama API via /api/chat.
    """
    health = get_ollama_client_info()
    if not health["running"]:
        raise RuntimeError("Ollama is not running. Please start Ollama or configure GROQ_API_KEY in backend/.env.")

    url = f"{OLLAMA_BASE_URL}/api/chat"
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "keep_alive": "60m",
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_thread": 8,
            "num_ctx": 4096
        }
    }

    try:
        response = requests.post(url, json=payload, timeout=timeout_seconds)
        if response.status_code == 404:
            raise RuntimeError(f"Configured Ollama model '{OLLAMA_MODEL}' was not found. Please run 'ollama pull {OLLAMA_MODEL}'.")
        response.raise_for_status()
        data = response.json()
        return data.get("message", {}).get("content", "")
    except requests.exceptions.Timeout:
        raise RuntimeError("Ollama request timed out. Please try again or ensure your computer has sufficient free RAM.")
    except requests.exceptions.ConnectionError:
        raise RuntimeError("Ollama is not running. Please start Ollama or set GROQ_API_KEY for Cloud AI.")
    except Exception as e:
        if isinstance(e, RuntimeError):
            raise e
        raise RuntimeError(f"Ollama error: {str(e)}")


def call_ollama(prompt: str, system_prompt: str = "", temperature: float = 0.1, timeout_seconds: int = 300) -> str:
    """
    Universal AI caller:
    Prioritizes Cloud AI (Groq/OpenAI) to preserve device disk space.
    Falls back gracefully to local Ollama if no cloud API key is configured.
    """
    if GROQ_API_KEY:
        return call_groq(prompt, system_prompt=system_prompt, temperature=temperature, timeout_seconds=timeout_seconds)
    elif OPENAI_API_KEY:
        return call_openai(prompt, system_prompt=system_prompt, temperature=temperature, timeout_seconds=timeout_seconds)
    else:
        return call_ollama_local(prompt, system_prompt=system_prompt, temperature=temperature, timeout_seconds=timeout_seconds)



def calculate_match_score(required_skills: List[str], matching_skills: List[str], missing_skills: List[str]) -> Dict[str, Any]:
    """
    Calculates transparent match percentage based on matched required skills.
    Formula: matched / total_required * 100
    """
    clean_req = [s.strip() for s in required_skills if s.strip()]
    clean_match = [s.strip() for s in matching_skills if s.strip()]
    clean_miss = [s.strip() for s in missing_skills if s.strip()]

    total_criteria = len(clean_req)
    if total_criteria == 0:
        total_criteria = len(clean_match) + len(clean_miss)

    if total_criteria > 0:
        matched_count = len(clean_match)
        percentage = round((matched_count / total_criteria) * 100)
        percentage = max(0, min(100, percentage))
    else:
        percentage = 50

    return {
        "match_percentage": percentage,
        "matched_count": len(clean_match),
        "total_criteria": total_criteria,
        "criteria_note": f"{len(clean_match)} of {total_criteria} required criteria identified in Master Resume"
    }


def analyze_and_tailor_unified(jd_text: str, resume_text: str) -> Dict[str, Any]:
    """
    Unified single-round LLM execution that performs deep requirement analysis
    AND generates tailored resume sections in one high-efficiency pass (~40s vs 140s).
    Strictly follows anti-fabrication guidelines.
    """
    system_prompt = (
        "You are an elite, truthful ATS and resume tailoring assistant.\n"
        "STRICT ANTI-FABRICATION RULE:\n"
        "- The Master Resume is the ONLY source of truth.\n"
        "- NEVER invent companies, job titles, employment dates, years of experience, degrees, certifications, "
        "skills, projects, clients, achievements, metrics, responsibilities, or salary.\n"
        "- If the Job Description requires something that does NOT appear in the Master Resume, "
        "you MUST place it in 'missing_skills'. DO NOT claim the candidate possesses it.\n"
        "- Place in 'matching_skills' ONLY skills that are explicitly present in the Master Resume.\n"
        "- Rephrase and strengthen bullet points using strong action verbs, strictly preserving real metrics.\n"
        "- Return ONLY valid JSON matching the exact schema."
    )

    user_prompt = f"""
Analyze the following Job Description (JD) against the Master Resume and generate both the analysis and the tailored resume content.

=== JOB DESCRIPTION ===
{jd_text[:3500]}

=== MASTER RESUME (SOURCE OF TRUTH) ===
{resume_text[:3500]}

=== OUTPUT INSTRUCTIONS ===
Return a single JSON object with two main sections: 'analysis' and 'tailored_resume'.
1. 'analysis':
   - job_title, required_skills, preferred_skills, soft_skills, responsibilities, education_requirements, experience_requirements, keywords, matching_skills, missing_skills, relevant_experience, relevant_projects, resume_summary, improvement_suggestions.
2. 'tailored_resume':
   - summary: 3-4 sentence professional summary tailored to JD using ONLY real Master Resume facts.
   - skills: object with technical, tools, soft_skills, matching_with_jd, missing_from_resume.
   - experience: array of roles from Master Resume. Rewrite 2-4 bullets per role with strong action verbs. Preserve exact companies, roles, and dates.
   - projects: array of relevant projects found in Master Resume.
   - education: array of authentic degrees and institutions from Master Resume.
   - certifications: array of certifications from Master Resume (or empty if none).

Return ONLY this JSON structure:
{{
  "analysis": {{
    "job_title": "string",
    "required_skills": ["string"],
    "preferred_skills": ["string"],
    "soft_skills": ["string"],
    "responsibilities": ["string"],
    "education_requirements": ["string"],
    "experience_requirements": ["string"],
    "keywords": ["string"],
    "matching_skills": ["string"],
    "missing_skills": ["string"],
    "relevant_experience": ["string"],
    "relevant_projects": ["string"],
    "resume_summary": "string",
    "improvement_suggestions": ["string"]
  }},
  "tailored_resume": {{
    "summary": "string",
    "skills": {{
      "technical": ["string"],
      "tools": ["string"],
      "soft_skills": ["string"],
      "matching_with_jd": ["string"],
      "missing_from_resume": ["string"]
    }},
    "experience": [
      {{
        "role": "string",
        "company": "string",
        "duration": "string",
        "location": "string",
        "bullets": ["string"]
      }}
    ],
    "projects": [
      {{
        "name": "string",
        "technologies": "string",
        "bullets": ["string"]
      }}
    ],
    "education": [
      {{
        "degree": "string",
        "institution": "string",
        "year": "string"
      }}
    ],
    "certifications": ["string"]
  }}
}}
"""

    raw_response = call_ollama(prompt=user_prompt, system_prompt=system_prompt, temperature=0.1, timeout_seconds=300)
    parsed = safe_extract_json(raw_response)

    if not parsed or "analysis" not in parsed:
        logger.error("Failed to parse unified response: %s", raw_response)
        raise ValueError("Could not parse structured analysis from local AI model. Please try again.")

    analysis = parsed.get("analysis", {})
    tailored = parsed.get("tailored_resume", {})

    # Compute match metrics
    match_metrics = calculate_match_score(
        analysis.get("required_skills", []),
        analysis.get("matching_skills", []),
        analysis.get("missing_skills", [])
    )
    analysis["match_metrics"] = match_metrics

    return {
        "analysis": analysis,
        "tailored_resume": tailored
    }


def analyze_resume_against_jd(jd_text: str, resume_text: str) -> Dict[str, Any]:
    """
    Backwards-compatible analysis function.
    """
    unified = analyze_and_tailor_unified(jd_text, resume_text)
    return unified["analysis"]
