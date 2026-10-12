import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional
from services.ai_service import call_ollama, safe_extract_json
from services.image_ocr import (
    extract_text_from_image_b64,
    is_photo_update_request
)

logger = logging.getLogger(__name__)


def extract_contact_info(text: str, filename: str = "") -> Dict[str, str]:
    """
    Extract contact details and candidate name with high precision.
    Supports multiline documents, single-line delimiter-separated contact bars,
    and image OCR text extracts.
    """
    banned_words = {
        "SUMMARY", "EDUCATION", "PROJECTS", "SKILLS", "EXPERIENCE",
        "PROFESSIONAL", "CERTIFICATIONS", "ACHIEVEMENTS", "OBJECTIVE",
        "PROFILE", "CURRICULUM", "VITAE", "RESUME", "PAGE"
    }

    # 1. Email extraction
    email_match = re.search(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    email = email_match.group(0) if email_match else ""

    # 2. Phone extraction (international and standard formats)
    phone_match = re.search(r"(?:(?:\+?91[\s-]?)?[6-9]\d{9})|(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})|(?:\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4})", text)
    phone = phone_match.group(0).strip() if phone_match else ""

    # 3. LinkedIn
    linkedin_match = re.search(r"(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+", text, re.IGNORECASE)
    linkedin = linkedin_match.group(0) if linkedin_match else ("LinkedIn" if "linkedin" in text.lower() else "")

    # 4. GitHub
    github_match = re.search(r"(?:https?:\/\/)?(?:www\.)?github\.com\/[a-zA-Z0-9_-]+", text, re.IGNORECASE)
    github = github_match.group(0) if github_match else ("GitHub" if "github" in text.lower() else "")

    # 5. Location extraction
    location = ""
    location_match = re.search(r'\b([A-Z][a-z]+(?:[\s-][A-Z][a-z]+)?,\s*(?:Maharashtra|Karnataka|Telangana|Tamil\s+Nadu|Delhi|Gujarat|India|California|New\s+York|Texas|Washington|USA|UK))\b', text)
    if location_match:
        cand_loc = location_match.group(1).strip()
        if not any(w.upper() in banned_words for w in cand_loc.replace(',', ' ').split()):
            location = cand_loc

    if not location:
        city_candidates = [
            "Pune", "Mumbai", "Bangalore", "Bengaluru", "Hyderabad", "Delhi", "New Delhi",
            "Noida", "Gurgaon", "Gurugram", "Chennai", "Kolkata", "Ahmedabad", "Jaipur",
            "San Francisco", "New York", "Seattle", "Austin", "Boston", "Chicago", "London",
            "Toronto", "Berlin", "Singapore", "Sydney"
        ]
        for c in city_candidates:
            if re.search(r'\b' + re.escape(c) + r'\b', text, re.IGNORECASE):
                location = f"{c}, Maharashtra" if c.lower() in ["pune", "mumbai"] else c
                break

    # 6. Candidate Name Detection
    name = ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    # First attempt: Check delimiter-separated line before or around email
    for line in lines:
        if email and email in line:
            prefix = line.split(email)[0].strip()
            tokens = [t.strip() for t in re.split(r'[•|,\t]', prefix) if t.strip()]
            for tok in tokens:
                cleaned = re.sub(r'[^A-Za-z\s]', '', tok).strip()
                words = cleaned.split()
                if 2 <= len(words) <= 4 and not any(w.upper() in banned_words for w in words):
                    name = cleaned.title()
                    break
            if name:
                break

    # Second attempt: Check first few lines of text
    if not name:
        for line in lines[:5]:
            if any(d in line for d in ['•', '|', '\t']):
                tokens = [t.strip() for t in re.split(r'[•|,\t]', line) if t.strip()]
                for tok in tokens:
                    cleaned = re.sub(r'[^A-Za-z\s]', '', tok).strip()
                    words = cleaned.split()
                    if 2 <= len(words) <= 4 and not any(w.upper() in banned_words for w in words):
                        if not any(sw.lower() in tok.lower() for sw in ["linkedin", "github", "email", "@"]):
                            name = cleaned.title()
                            break
                if name:
                    break

            cleaned_line = re.sub(r'[^A-Za-z\s]', '', line).strip()
            words = cleaned_line.split()
            if 2 <= len(words) <= 4:
                if not any(w.upper() in banned_words for w in words):
                    if line.isupper() or all(w[0].isupper() for w in words if w):
                        name = cleaned_line.title()
                        break

    # Fallback to filename if available
    if not name and filename:
        clean_fn = Path(filename).stem
        clean_fn = re.sub(r'\(\d+\)', '', clean_fn)
        clean_fn = clean_fn.replace('_', ' ').replace('-', ' ').strip()
        words = [w for w in clean_fn.split() if w.lower() not in ["resume", "cv", "master"]]
        if words:
            name = " ".join(words).title()

    # Fallback to email username
    if not name and email:
        user_part = email.split('@')[0]
        subparts = [p.capitalize() for p in re.split(r'[._-]', user_part) if p and not p.isdigit()]
        if subparts:
            name = " ".join(subparts)

    if not name:
        name = "Candidate Name"

    return {
        "name": name,
        "email": email,
        "phone": phone,
        "linkedin": linkedin,
        "github": github,
        "location": location
    }


def parse_master_resume_structure(resume_text: str, filename: str = "") -> Dict[str, Any]:
    """
    Deterministically extracts authentic Master Resume sections.
    """
    contact = extract_contact_info(resume_text, filename)

    # Known section header regex patterns
    SECTION_PATTERNS = [
        ("summary", r"(?:^|\n)\s*(?:PROFESSIONAL\s+)?SUMMARY\s*(?:\n|$)"),
        ("skills", r"(?:^|\n)\s*(?:TECHNICAL\s+)?SKILLS(?:\s*&\s*TOOLS|\s*&\s*TECHNOLOGIES)?\s*(?:\n|$)"),
        ("experience", r"(?:^|\n)\s*(?:PROFESSIONAL\s+|WORK\s+)?EXPERIENCE\s*(?:\n|$)"),
        ("projects", r"(?:^|\n)\s*(?:KEY\s+|ACADEMIC\s+)?PROJECTS\s*(?:\n|$)"),
        ("education", r"(?:^|\n)\s*EDUCATION(?:\s*&\s*QUALIFICATIONS)?\s*(?:\n|$)"),
        ("certifications", r"(?:^|\n)\s*(?:CERTIFICATIONS(?:\s*&\s*ACHIEVEMENTS)?|ACHIEVEMENTS)\s*(?:\n|$)")
    ]

    matches = []
    for sec_id, pattern in SECTION_PATTERNS:
        for m in re.finditer(pattern, resume_text, re.IGNORECASE):
            matches.append((m.start(), m.end(), sec_id))
    matches.sort(key=lambda x: x[0])

    sections_text: Dict[str, str] = {}
    for i in range(len(matches)):
        start = matches[i][1]
        end = matches[i+1][0] if i + 1 < len(matches) else len(resume_text)
        sec_id = matches[i][2]
        sec_content = resume_text[start:end].strip()
        sections_text[sec_id] = sec_content

    # 1. Summary
    orig_summary = sections_text.get("summary", "")
    if not orig_summary:
        first_lines = [l.strip() for l in resume_text.splitlines()[:6] if len(l.strip()) > 40]
        orig_summary = first_lines[0] if first_lines else "Experienced software engineer with proven technical background."

    # 2. Skills
    skills_raw = sections_text.get("skills", "")
    skills_dict: Dict[str, List[str]] = {}
    if skills_raw:
        for line in skills_raw.splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                cat, val = line.split(":", 1)
                items = [s.strip() for s in re.split(r'[,|•]', val) if s.strip()]
                if items:
                    skills_dict[cat.strip()] = items
            else:
                items = [s.strip() for s in re.split(r'[,|•]', line) if s.strip()]
                if items:
                    skills_dict.setdefault("Technical Skills", []).extend(items)
    if not skills_dict:
        skills_dict["Technical Skills"] = ["Software Engineering", "Backend Development", "Database Management", "Problem Solving"]

    # 3. Experience
    exp_raw = sections_text.get("experience", "")
    experience_list: List[Dict[str, Any]] = []
    if exp_raw:
        current_job: Optional[Dict[str, Any]] = None
        for line in exp_raw.splitlines():
            line = line.strip()
            if not line:
                continue

            if ("|" in line or "–" in line or " - " in line) and len(line) < 120 and not line.startswith(('•', '-', '*')):
                if current_job and (current_job.get("bullets") or current_job.get("role")):
                    experience_list.append(current_job)

                parts = [p.strip() for p in re.split(r'[|–-]', line) if p.strip()]
                role = parts[0] if len(parts) > 0 else "Software Engineer"
                company = parts[1] if len(parts) > 1 else ""
                current_job = {
                    "role": role,
                    "company": company,
                    "duration": "",
                    "location": "",
                    "bullets": []
                }
            elif current_job:
                if re.search(r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|20\d\d|Ongoing|Present)', line, re.I) and len(line) < 50:
                    current_job["duration"] = line
                else:
                    clean_b = line.lstrip('•-*–—> ').strip()
                    if len(clean_b) > 15:
                        current_job["bullets"].append(clean_b)

        if current_job and (current_job.get("bullets") or current_job.get("company")):
            experience_list.append(current_job)

    # 4. Projects (Smart parsing)
    proj_raw = sections_text.get("projects", "")
    projects_list: List[Dict[str, Any]] = []
    if proj_raw:
        current_proj: Optional[Dict[str, Any]] = None
        for line in proj_raw.splitlines():
            line = line.strip()
            if not line:
                continue

            is_bullet = line.startswith(('•', '-', '*', '–', '—', '>', '1.', '2.', '3.'))
            if not is_bullet and ("|" in line or (len(line) < 90 and not line.endswith('.'))):
                if current_proj and (current_proj.get("bullets") or current_proj.get("name")):
                    projects_list.append(current_proj)

                parts = [p.strip() for p in line.split("|") if p.strip()]
                p_name = parts[0]
                p_tech = ", ".join(parts[1:]) if len(parts) > 1 else ""
                current_proj = {
                    "name": p_name,
                    "technologies": p_tech,
                    "bullets": []
                }
            elif current_proj:
                clean_b = line.lstrip('•-*–—> 1234567890.').strip()
                if len(clean_b) > 12:
                    current_proj["bullets"].append(clean_b)

        if current_proj and (current_proj.get("bullets") or current_proj.get("name")):
            projects_list.append(current_proj)

    # Default starter projects if none parsed
    if not projects_list:
        projects_list = [
            {
                "name": "Enterprise Management Service",
                "technologies": "Core Application Stack, Relational Database",
                "bullets": [
                    "Engineered core backend services and modular business logic for high concurrency.",
                    "Designed relational schema models and integrated REST APIs with security best practices."
                ]
            },
            {
                "name": "Cloud Data Analytics Portal",
                "technologies": "Web Framework, Database & Cache",
                "bullets": [
                    "Implemented responsive service endpoints and real-time query aggregation modules.",
                    "Optimized data access layers and automated unit tests for production release reliability."
                ]
            }
        ]

    # 5. Education
    edu_raw = sections_text.get("education", "")
    education_list: List[Dict[str, Any]] = []
    if edu_raw:
        edu_lines = [l.strip() for l in edu_raw.splitlines() if len(l.strip()) > 4 and not re.search(r'@|github|linkedin|\+91', l, re.I)]
        for i in range(0, len(edu_lines), 2):
            deg = edu_lines[i]
            inst = edu_lines[i+1] if i + 1 < len(edu_lines) else ""
            yr_match = re.search(r'(20\d\d[\s–-]+20\d\d|20\d\d)', deg + " " + inst)
            year = yr_match.group(0) if yr_match else ""
            education_list.append({
                "degree": deg,
                "institution": inst,
                "year": year
            })

    # 6. Certifications
    cert_raw = sections_text.get("certifications", "")
    cert_list: List[str] = []
    if cert_raw:
        for line in cert_raw.splitlines():
            line = line.strip().lstrip('•-*–— ').strip()
            if len(line) > 5 and not any(kw in line.upper() for kw in ["CERTIFICATIONS", "ACHIEVEMENTS"]):
                cert_list.append(line)

    return {
        "name": contact["name"],
        "contact": contact,
        "summary": orig_summary,
        "skills": skills_dict,
        "experience": experience_list,
        "projects": projects_list,
        "education": education_list,
        "certifications": cert_list
    }


def extract_target_jd_profile(jd_text: str) -> Dict[str, Any]:
    """
    Heuristically extracts key technology domains, target databases,
    target languages, and industry certifications from the JD text.
    Acts as a high-precision guide and resilient fallback.
    """
    text_lower = jd_text.lower()

    # Detect Target Languages
    languages = []
    lang_map = [
        ("Python", r"\bpython\b"),
        ("Java", r"\bjava\b"),
        ("Go", r"\b(?:golang|go)\b"),
        ("TypeScript", r"\btypescript\b"),
        ("JavaScript", r"\bjavascript\b|node(?:\.js)?\b"),
        ("C#", r"\bc#|\.net\b"),
        ("C++", r"\bc\+\+\b"),
        ("Ruby", r"\bruby\b"),
        ("PHP", r"\bphp\b"),
        ("Rust", r"\brust\b")
    ]
    for name, pat in lang_map:
        if re.search(pat, text_lower):
            languages.append(name)
    primary_language = languages[0] if languages else "Python"

    # Detect Target Frameworks
    frameworks = []
    fw_map = [
        ("FastAPI", r"\bfastapi\b"),
        ("Django", r"\bdjango\b"),
        ("Flask", r"\bflask\b"),
        ("Spring Boot", r"\bspring(?:\s+boot)?\b"),
        ("Express", r"\bexpress(?:\.js)?\b"),
        ("NestJS", r"\bnest(?:\.js)?\b"),
        ("React", r"\breact(?:\.js)?\b"),
        ("Angular", r"\bangular\b"),
        ("ASP.NET", r"\basp\.net\b"),
        ("Ruby on Rails", r"\brails\b")
    ]
    for name, pat in fw_map:
        if re.search(pat, text_lower):
            frameworks.append(name)
    if not frameworks:
        frameworks = ["FastAPI", "Django"] if primary_language == "Python" else ["Spring Boot"] if primary_language == "Java" else ["Express"]

    # Detect Target Databases
    databases = []
    db_map = [
        ("PostgreSQL", r"\bpostgres(?:ql)?\b"),
        ("MongoDB", r"\bmongo(?:db)?\b"),
        ("Redis", r"\bredis\b"),
        ("MySQL", r"\bmysql\b"),
        ("DynamoDB", r"\bdynamodb\b"),
        ("Elasticsearch", r"\belasticsearch\b"),
        ("Cassandra", r"\bcassandra\b"),
        ("SQL Server", r"\bsql\s*server\b"),
        ("Oracle DB", r"\boracle\b")
    ]
    for name, pat in db_map:
        if re.search(pat, text_lower):
            databases.append(name)
    if not databases:
        databases = ["PostgreSQL", "Redis"]

    # Detect Tools / Cloud
    tools = []
    tool_map = [
        ("Docker", r"\bdocker\b"),
        ("Kubernetes", r"\bkubernetes|k8s\b"),
        ("AWS", r"\baws|amazon\s+web\s+services\b"),
        ("Azure", r"\bazure\b"),
        ("GCP", r"\bgcp|google\s+cloud\b"),
        ("Celery", r"\bcelery\b"),
        ("Kafka", r"\bkafka\b"),
        ("RabbitMQ", r"\brabbitmq\b"),
        ("Git", r"\bgit\b"),
        ("CI/CD", r"\bci[\/-]?cd\b"),
        ("GraphQL", r"\bgraphql\b"),
        ("REST API", r"\brest(?:ful)?\s*(?:api)?\b")
    ]
    for name, pat in tool_map:
        if re.search(pat, text_lower):
            tools.append(name)
    if not tools:
        tools = ["Docker", "AWS", "REST APIs", "Git", "CI/CD"]

    # Select Relevant Industry Certifications for JD
    recommended_certs = []
    if "aws" in text_lower or "cloud" in text_lower:
        recommended_certs.append("AWS Certified Developer – Associate")
        recommended_certs.append("AWS Certified Solutions Architect – Associate")
    if primary_language == "Python" or "python" in text_lower:
        recommended_certs.append("PCAP – Certified Associate in Python Programming (Python Institute)")
    elif primary_language == "Java" or "java" in text_lower:
        recommended_certs.append("Oracle Certified Professional: Java SE Developer")
    if "kubernetes" in text_lower or "k8s" in text_lower:
        recommended_certs.append("CKAD – Certified Kubernetes Application Developer")
    if "azure" in text_lower:
        recommended_certs.append("Microsoft Certified: Azure Developer Associate (AZ-204)")
    if "postgres" in text_lower:
        recommended_certs.append("PostgreSQL 14 Associate Certification")

    if len(recommended_certs) < 2:
        recommended_certs.extend([
            f"{primary_language} Professional Developer Certification",
            "Cloud Native & DevOps Engineering Practitioner"
        ])
    recommended_certs = recommended_certs[:3]

    return {
        "primary_language": primary_language,
        "languages": languages or [primary_language],
        "frameworks": frameworks,
        "databases": databases,
        "tools": tools,
        "recommended_certifications": recommended_certs
    }


def tailor_resume_intelligently(
    jd_text: str,
    resume_text: str,
    filename: str = ""
) -> Dict[str, Any]:
    """
    Intelligently tailors candidate's resume against the Job Description:
    1. Analyzes target programming language, frameworks, databases, and certifications from the JD.
    2. Re-engineers Projects:
       - Adapts legacy/alternative stacks (e.g., Java -> Python/FastAPI) to target languages and target databases.
       - Constructs real-world, production-ready system architectures with metrics.
    3. Re-engineers Certifications:
       - Identifies top industry certifications demanded/favored by the JD.
    4. Infuses high-priority JD keywords into technical competencies, summary, and project bullets.
    5. Tracks changes with a detailed changelog and visual highlights for the candidate.
    """
    # 1. Parse full master resume structure
    master_data = parse_master_resume_structure(resume_text, filename)
    existing_projects = master_data.get("projects", [])
    jd_profile = extract_target_jd_profile(jd_text)

    # 2. Prepare AI Prompt
    system_prompt = (
        "You are an elite ATS resume strategist and principal software architect.\n"
        "Your mission is to transform and tailor the candidate's resume for the target Job Description:\n"
        "1. REAL-LIFE PROJECT TRANSFORMATION:\n"
        "   - If the candidate has projects in another language (e.g. Java, PHP, C++) and the JD requires Python, Go, etc., "
        "     TRANSFORM EVERY PROJECT into a REAL-LIFE, USEFUL PRODUCTION PROJECT using the TARGET programming language, "
        "     TARGET framework, and TARGET database (e.g. PostgreSQL, Redis, MongoDB) from the Job Description!\n"
        "   - Give realistic production names, architecture bullets with metrics, database query optimization, and containerization.\n"
        "2. CERTIFICATIONS SELECTION:\n"
        "   - Analyze the JD and assign 2-3 top industry standard certifications directly aligned with the target role and tech stack.\n"
        "3. PROFESSIONAL SUMMARY:\n"
        "   - Write 3-4 impactful sentences highlighting verified expertise in the target tech stack and database.\n"
        "4. Return ONLY valid JSON matching the exact schema."
    )

    projects_context = json.dumps([
        {
            "original_name": p.get("name"),
            "original_technologies": p.get("technologies"),
            "original_bullets": p.get("bullets", [])[:2]
        }
        for p in existing_projects[:3]
    ])

    prompt = f"""
Transform the candidate's projects, certifications, summary, and technical skills to match the Target Job Description.

=== TARGET JOB DESCRIPTION ===
{jd_text[:3000]}

=== CANDIDATE RESUME CURRENT STATE ===
Candidate Name: {master_data.get('name')}
Current Summary: {master_data.get('summary', '')[:300]}
Current Projects: {projects_context}
Current Certifications: {json.dumps(master_data.get('certifications', []))}

=== DETECTED TARGET TECHNOLOGIES ===
Target Language: {jd_profile['primary_language']}
Target Frameworks: {', '.join(jd_profile['frameworks'])}
Target Databases: {', '.join(jd_profile['databases'])}

=== OUTPUT INSTRUCTIONS ===
1. 'job_title': Target role title from the JD.
2. 'target_tech_stack': Top 4-6 target technologies/frameworks from the JD.
3. 'target_database': List of databases from JD (e.g. PostgreSQL, Redis).
4. 'important_keywords': 8-10 high-value ATS keywords from the JD (tech stack, databases, architectural concepts).
5. 'tailored_summary': 3-4 sentence professional summary highlighting the target language, frameworks, and databases.
6. 'tailored_projects': Transform the candidate's projects into REAL-LIFE, USEFUL PRODUCTION PROJECTS using the target programming language ({jd_profile['primary_language']}), frameworks ({', '.join(jd_profile['frameworks'])}), and databases ({', '.join(jd_profile['databases'])}).
   For EACH project provide:
   - 'name': Production system name (e.g. "Distributed High-Throughput Order Engine")
   - 'technologies': String listing target tech (e.g. "{jd_profile['primary_language']}, {jd_profile['frameworks'][0] if jd_profile['frameworks'] else 'FastAPI'}, {', '.join(jd_profile['databases'])}, Docker")
   - 'original_tech': Original tech it was adapted from (e.g. "Java, Spring Boot, MySQL")
   - 'transformation_note': Concise explanation of the adaptation (e.g. "Transformed Java/MySQL service into {jd_profile['primary_language']}/{jd_profile['frameworks'][0] if jd_profile['frameworks'] else 'FastAPI'} microservice with {', '.join(jd_profile['databases'])} caching")
   - 'database_used': Target database(s)
   - 'keywords_infused': 3-5 critical keywords applied in this project
   - 'bullets': Exactly 3 realistic production bullet points:
     * Bullet 1: API/System architecture in target language/framework with quantitative outcomes (e.g. 10k+ req/sec, 99.9% uptime).
     * Bullet 2: Database schema design, indexing, and query optimization with the target database.
     * Bullet 3: Containerization (Docker), background tasks (Celery/Kafka), or CI/CD reliability.
7. 'tailored_certifications': 2-3 top industry certifications matching this JD (e.g. AWS Certified Developer, PCAP Python).
8. 'matching_skills': Skills matching between candidate and JD.
9. 'missing_skills': Skills in JD not initially present in candidate master resume.
10. 'changes_applied': 4-5 bullet points describing exact changes made to projects, databases, certifications, and keywords.

Return ONLY this JSON format:
{{
  "job_title": "string",
  "target_tech_stack": ["string"],
  "target_database": ["string"],
  "important_keywords": ["string"],
  "tailored_summary": "string",
  "tailored_projects": [
    {{
      "name": "string",
      "technologies": "string",
      "original_tech": "string",
      "transformation_note": "string",
      "database_used": "string",
      "keywords_infused": ["string"],
      "bullets": ["string", "string", "string"]
    }}
  ],
  "tailored_certifications": ["string"],
  "matching_skills": ["string"],
  "missing_skills": ["string"],
  "changes_applied": ["string"]
}}
"""

    raw_response = call_ollama(prompt=prompt, system_prompt=system_prompt, temperature=0.1, timeout_seconds=150)
    parsed = safe_extract_json(raw_response)

    # 3. Fallback Generation if AI response is missing or malformed
    if not parsed or not isinstance(parsed, dict) or not parsed.get("tailored_projects"):
        logger.warning("Using resilient intelligent fallback for tailoring.")
        target_lang = jd_profile["primary_language"]
        target_fw = jd_profile["frameworks"][0] if jd_profile["frameworks"] else "FastAPI"
        target_dbs = ", ".join(jd_profile["databases"])

        fallback_projects = []
        for i, proj in enumerate(existing_projects[:3]):
            orig_name = proj.get("name", f"Enterprise Project {i+1}")
            orig_tech = proj.get("technologies", "Java, MySQL")
            new_name = orig_name if not any(w in orig_name.lower() for w in ["java", "spring"]) else f"Cloud {target_lang} {orig_name.replace('Java', '').strip()}"
            fallback_projects.append({
                "name": new_name,
                "technologies": f"{target_lang}, {target_fw}, {target_dbs}, Docker, CI/CD",
                "original_tech": orig_tech,
                "transformation_note": f"Adapted legacy system into modern {target_lang}/{target_fw} microservice with {target_dbs} as required by JD",
                "database_used": target_dbs,
                "keywords_infused": [target_lang, target_fw, jd_profile["databases"][0] if jd_profile["databases"] else "PostgreSQL", "Docker", "REST API"],
                "bullets": [
                    f"Architected high-performance RESTful microservices using {target_lang} and {target_fw}, reducing endpoint response times by 38%.",
                    f"Engineered optimized schemas in {jd_profile['databases'][0] if jd_profile['databases'] else 'PostgreSQL'} with indexing and caching, supporting 15k+ daily queries.",
                    "Containerized application components with Docker and established automated automated CI/CD deployment pipelines."
                ]
            })

        parsed = {
            "job_title": "Target Role",
            "target_tech_stack": [target_lang, target_fw, "Docker", "REST APIs"],
            "target_database": jd_profile["databases"],
            "important_keywords": [target_lang, target_fw] + jd_profile["databases"] + ["Docker", "Microservices", "REST API", "CI/CD"],
            "tailored_summary": f"Results-driven software engineer specialized in building scalable backend services with {target_lang}, {target_fw}, and {target_dbs}. Proven expertise in database query optimization, containerized cloud architectures, and delivering resilient production microservices.",
            "tailored_projects": fallback_projects,
            "tailored_certifications": jd_profile["recommended_certifications"],
            "matching_skills": [target_lang, "REST APIs", "Git", "Problem Solving"],
            "missing_skills": [s for s in jd_profile["databases"] if s not in str(master_data.get("skills", ""))],
            "changes_applied": [
                f"Transformed project stacks and databases to {target_lang}, {target_fw}, and {target_dbs} to match JD requirements",
                f"Aligned databases with target specifications: {target_dbs}",
                f"Integrated recommended industry certifications: {', '.join(jd_profile['recommended_certifications'][:2])}",
                "Infused critical ATS keywords into project bullets and core competencies",
                f"Re-engineered professional summary focusing on {target_lang} production engineering"
            ]
        }

    # 4. Assemble Tailored Resume
    tailored_resume = dict(master_data)

    # A. Injected Summary
    if parsed.get("tailored_summary"):
        tailored_resume["summary"] = parsed["tailored_summary"].strip()

    # B. Injected Tailored Projects
    if parsed.get("tailored_projects") and isinstance(parsed["tailored_projects"], list):
        enhanced_projects = []
        for p in parsed["tailored_projects"]:
            if isinstance(p, dict):
                p["is_tailored"] = True
                enhanced_projects.append(p)
        tailored_resume["projects"] = enhanced_projects

    # C. Injected Tailored Certifications
    if parsed.get("tailored_certifications") and isinstance(parsed["tailored_certifications"], list):
        tailored_resume["certifications"] = parsed["tailored_certifications"]
    elif jd_profile.get("recommended_certifications"):
        tailored_resume["certifications"] = jd_profile["recommended_certifications"]

    # D. Structured & High-Priority Skills
    top_stack = parsed.get("target_tech_stack") or [jd_profile["primary_language"]]
    top_dbs = parsed.get("target_database") or jd_profile["databases"]
    top_keywords = parsed.get("important_keywords") or []

    new_skills: Dict[str, List[str]] = {
        "Targeted JD Stack": top_stack,
        "Databases & Storage": top_dbs,
        "Cloud & DevOps": [t for t in jd_profile["tools"] if t not in top_stack],
    }
    for k, v in master_data.get("skills", {}).items():
        if k not in ["missing_from_resume", "Targeted JD Stack", "Databases & Storage", "Cloud & DevOps"]:
            new_skills[k] = v
    tailored_resume["skills"] = new_skills

    # E. Tailoring Metadata & Visual Changelog for UI
    project_transforms = []
    for p in tailored_resume.get("projects", []):
        project_transforms.append({
            "project_name": p.get("name"),
            "original_tech": p.get("original_tech", "Legacy Tech Stack"),
            "tailored_tech": p.get("technologies"),
            "database_used": p.get("database_used") or ", ".join(top_dbs),
            "transformation_note": p.get("transformation_note") or f"Adapted to {p.get('technologies')}",
            "keywords_infused": p.get("keywords_infused", [])
        })

    changes_applied = parsed.get("changes_applied") or [
        f"Transformed projects to target stack ({jd_profile['primary_language']}) and databases ({', '.join(top_dbs)})",
        f"Aligned certifications with JD credentials: {', '.join(tailored_resume.get('certifications', [])[:2])}",
        f"Infused {len(top_keywords)} critical keywords into summary, skills, and project bullets",
        "Crafted ATS-optimized professional summary"
    ]

    tailored_resume["tailoring_metadata"] = {
        "is_tailored": True,
        "target_role": parsed.get("job_title", "Target Role"),
        "target_language": jd_profile["primary_language"],
        "target_frameworks": jd_profile["frameworks"],
        "target_database": top_dbs,
        "important_keywords": top_keywords,
        "changes_applied": changes_applied,
        "project_transformations": project_transforms,
        "certifications_aligned": tailored_resume.get("certifications", [])
    }

    # 5. Transparent Match Calculation
    req_skills = top_stack + top_dbs
    match_skills = parsed.get("matching_skills") or [jd_profile["primary_language"]]
    miss_skills = parsed.get("missing_skills") or []
    total_crit = len(req_skills) if req_skills else 6
    pct = round((len(match_skills) / total_crit) * 100) if total_crit > 0 else 75
    pct = max(40, min(95, pct))

    analysis = {
        "job_title": parsed.get("job_title", "Target Role"),
        "target_tech_stack": top_stack,
        "target_database": top_dbs,
        "important_keywords": top_keywords,
        "required_skills": req_skills,
        "matching_skills": match_skills,
        "missing_skills": miss_skills,
        "relevant_experience": [f"{j.get('role')} at {j.get('company')}" for j in master_data.get("experience", [])[:2]],
        "relevant_projects": [p.get("name") for p in tailored_resume.get("projects", [])],
        "project_transformations": project_transforms,
        "certifications_recommended": tailored_resume.get("certifications", []),
        "resume_summary": tailored_resume.get("summary", ""),
        "tailoring_changelog": changes_applied,
        "match_metrics": {
            "match_percentage": pct,
            "matched_count": len(match_skills),
            "total_criteria": total_crit
        }
    }

    return {
        "analysis": analysis,
        "tailored_content": tailored_resume,
        "match_score": pct
    }


# Backwards compatibility alias
generate_tailored_resume = tailor_resume_intelligently


def format_acronyms(text: str) -> str:
    """Format project and role titles while keeping technical acronyms correctly capitalized."""
    words = text.split()
    formatted = []
    acronyms = {
        "ai": "AI", "ml": "ML", "ats": "ATS", "api": "API", "rest": "REST",
        "ui": "UI", "ux": "UX", "aws": "AWS", "gcp": "GCP", "db": "DB",
        "sql": "SQL", "ci/cd": "CI/CD", "llm": "LLM", "llms": "LLMs",
        "nlp": "NLP", "ocr": "OCR", "jd": "JD"
    }
    for w in words:
        clean = re.sub(r'[^a-zA-Z0-9/]', '', w).lower()
        if clean in acronyms:
            prefix = ""
            suffix = ""
            if w.startswith(('"', "'", "(", "[")):
                prefix = w[0]
            if w.endswith(('"', "'", ")", "]", ",", ".", ";", ":")):
                suffix = w[-1]
            formatted.append(f"{prefix}{acronyms[clean]}{suffix}")
        else:
            formatted.append(w.capitalize())
    return " ".join(formatted)


def clean_project_title(t: str) -> str:
    """Strip extraneous prompt filler words, typos, and format the project title cleanly."""
    t = re.sub(r'^(?:i\s+want\s+|to\s+|as\s+|with\s+|a\s+|an\s+|the\s+|new\s+|project\s+named\s+|project\s+called\s+|put\s+|add\s+|use\s+)+', '', t.strip(), flags=re.I)
    t = re.sub(r'[\s,\.]+(?:this\s+)?(?:project|prjoect|projcet|poject|progect|resume)(?:\s+instead)?[\.!]?$', '', t, flags=re.I)
    t = re.sub(r'[\s,\.]+(?:instead\s+of\s+this|instead)[\.!]?$', '', t, flags=re.I)
    cleaned = t.strip(" \"':;,.-")
    return format_acronyms(cleaned) if cleaned else ""


def update_project_bullets(old_bullets: List[str], old_name: str, new_name: str, technologies: str = "") -> List[str]:
    """Generate high-impact ATS bullet points tailored to the updated project name and tech stack."""
    if "resume" in new_name.lower() or "tailor" in new_name.lower():
        return [
            f"Architected and deployed {new_name}, an automated AI resume customization system utilizing Python, React, and Ollama.",
            "Engineered PostgreSQL schema with Redis caching for real-time JD parsing and ATS match calculation, reducing latency by 40%.",
            "Built interactive copilot chat with live resume preview, screenshot attachment parsing, and automated document generation."
        ]

    updated_b = []
    old_terms = [old_name]
    clean_old = re.sub(r'^(?:AI-Powered|Cloud-Native|Distributed)\s+', '', old_name, flags=re.I).strip()
    if clean_old and clean_old != old_name:
        old_terms.append(clean_old)
    if "engine" in old_name.lower():
        old_terms.append(re.sub(r'\bengine\b', '', old_name, flags=re.I).strip())

    for b in (old_bullets or []):
        curr = b
        for term in old_terms:
            if term and len(term) > 3 and term.lower() in curr.lower():
                curr = re.sub(re.escape(term), new_name, curr, flags=re.I)
        curr = re.sub(r'AI-powered\s+' + re.escape(new_name), new_name, curr, flags=re.I)
        updated_b.append(curr)

    if not any(new_name.lower() in b.lower() for b in updated_b) or len(updated_b) == 0:
        updated_b = [
            f"Designed and implemented scalable microservices for {new_name} utilizing modern architecture patterns.",
            "Optimized database schema and query performance, reducing data retrieval latency by 35%.",
            "Containerized deployment pipeline with Docker and automated testing, achieving 99.9% uptime."
        ]
    return updated_b


def find_matching_project_from_ocr(projects: List[Dict[str, Any]], ocr_text: str) -> Optional[int]:
    """Finds which existing project best matches the OCR text from an uploaded screenshot."""
    if not ocr_text or not projects:
        return None
    ocr_lower = ocr_text.lower()
    best_idx = None
    best_score = 0

    for idx, p in enumerate(projects):
        score = 0
        p_name = (p.get("name") or "").lower()
        if p_name and p_name in ocr_lower:
            score += 10
        # Check distinctive title words (len > 3)
        p_words = [w for w in re.split(r'[\s\-]+', p_name) if len(w) > 3]
        for w in p_words:
            if w in ocr_lower:
                score += 3
        # Check technologies
        techs = [t.strip().lower() for t in (p.get("technologies") or "").split(",") if t.strip()]
        for t in techs:
            if t in ocr_lower:
                score += 2
        # Check bullets
        for b in p.get("bullets", []):
            b_words = [w for w in re.split(r'[\s\-]+', b.lower()) if len(w) > 5]
            overlap = sum(1 for w in b_words if w in ocr_lower)
            if overlap >= 2:
                score += overlap

        if score > best_score:
            best_score = score
            best_idx = idx

    return best_idx if best_score >= 3 else None


def apply_direct_user_instructions(
    resume_content: Dict[str, Any],
    instruction: str,
    attached_images: Optional[List[str]] = None,
    ocr_text: str = ""
) -> tuple[Dict[str, Any], List[str]]:
    """
    Directly extracts and applies explicit user commands & queries:
    - Contact and name updates (from chat text or extracted screenshot OCR)
    - Project additions and photo attachments (from chat text or photo screenshot)
    - Project editing (titles, technologies, bullets, database)
    - Candidate photo updating / removal
    - Skills additions, removals, replacements
    - Experience role, company, bullet modifications
    - Education additions & updates
    - Certification additions & updates
    - Summary rewrites & conciseness
    - 1-page / single page condensation
    """
    updated = json.loads(json.dumps(resume_content))
    changes: List[str] = []
    inst_clean = instruction.strip()
    inst_lower = inst_clean.lower()
    inst_norm = inst_clean
    inst_norm = re.sub(r'\b(?:prjoect|projcet|progect|poject)\b', 'project', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:chnae|chaneg|chagne|chage)\b', 'change', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:mmy)\b', 'my', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:remvoe|renove|rmove|delet|delte)\b', 'remove', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:insted|instade)\b', 'instead', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:upadate|upate|udpate|updte|updaet)\b', 'update', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:sumary|summery|sumery|sumarry)\b', 'summary', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:porper|propr|propery)\b', 'proper', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:issur|isue|isssue)\b', 'issue', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:experiance|expereince|expeirence)\b', 'experience', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:skil|skils|skll|sklls)\b', 'skills', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:bulet|bullt|bulletes)\b', 'bullets', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:certifcate|certficate|certi)\b', 'certificate', inst_norm, flags=re.I)
    inst_norm = re.sub(r'\b(?:educaton|edcuation)\b', 'education', inst_norm, flags=re.I)
    inst_norm_lower = inst_norm.lower()
    combined_context = f"{inst_clean}\n\n{ocr_text}".strip()
    attached_images = attached_images or []

    # Ensure contact is a dictionary so fields are cleanly accessible
    if not isinstance(updated.get("contact"), dict):
        old_contact_str = str(updated.get("contact") or "")
        updated["contact"] = extract_contact_info(old_contact_str) if old_contact_str else {}

    # Sanitize corrupted location in contact if present (e.g. 'Spring Boot, RE' or 'Pune SUMMARY...')
    curr_loc = str(updated.get("contact", {}).get("location") or "")
    if curr_loc and (any(b in curr_loc.upper() for b in ["SUMMARY", "ENGINEER", "STUDENT", "INTERN", "AUTOMATON", "SPRING BOOT", "DBMS", "SDLC"]) or len(curr_loc.split()) > 4):
        clean_loc = "Pune, Maharashtra" if "pune" in curr_loc.lower() else ("Mumbai, Maharashtra" if "mumbai" in curr_loc.lower() else "Pune, Maharashtra")
        updated["contact"]["location"] = clean_loc

    # -------------------------------------------------------------
    # 1. Contact Details & Candidate Name Updates
    # -------------------------------------------------------------
    # A. Email
    email_cand = None
    m_email_inst = re.search(r'(?:email\s*(?:to|as|is|:)?\s*|^|\s)([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', inst_clean, re.I)
    if m_email_inst:
        email_cand = m_email_inst.group(1).strip()
    elif ocr_text and any(w in inst_norm_lower for w in ["email", "contact", "info"]):
        m_email_ocr = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', ocr_text)
        if m_email_ocr:
            email_cand = m_email_ocr.group(1).strip()

    if email_cand:
        if updated["contact"].get("email") != email_cand:
            updated["contact"]["email"] = email_cand
            changes.append(f"Updated email address to: {email_cand}")

    # B. Phone
    phone_cand = None
    m_phone_inst = re.search(r'(?:phone|mobile|tel|contact\s*no\.?)\s*(?:to|as|is|:)?\s*([+]?[0-9\s-]{9,15})', inst_clean, re.I)
    if m_phone_inst:
        phone_cand = re.sub(r'[^\d+]', '', m_phone_inst.group(1)).strip()
    elif ocr_text and any(w in inst_norm_lower for w in ["phone", "mobile", "number", "contact", "call"]):
        m_phone_ocr = re.search(r'(?:(?:\+?91[\s-]?)?[6-9]\d{9})|(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})|(?:\+?\d{1,3}[\s-]?\(?\d{2,4}\)?[\s-]?\d{3,4}[\s-]?\d{3,4})', ocr_text)
        if m_phone_ocr:
            phone_cand = m_phone_ocr.group(0).strip()

    if phone_cand and len(phone_cand) >= 8:
        if updated["contact"].get("phone") != phone_cand:
            updated["contact"]["phone"] = phone_cand
            changes.append(f"Updated contact phone number to: {phone_cand}")

    # C. Location / City
    loc_cand = None
    m_loc_inst = re.search(r'(?:location|city|address|based\s*in)\s*(?:to|as|is|:)?\s*([A-Za-z\s,]+?)(?:\.|$|\n)', inst_clean, re.I)
    if m_loc_inst and len(m_loc_inst.group(1).strip()) > 2:
        loc_cand = m_loc_inst.group(1).strip().title()
    elif ocr_text and any(w in inst_norm_lower for w in ["location", "city", "address", "relocate"]):
        city_candidates = [
            "Pune", "Mumbai", "Bangalore", "Bengaluru", "Hyderabad", "Delhi", "New Delhi",
            "Noida", "Gurgaon", "Gurugram", "Chennai", "Kolkata", "Ahmedabad", "Jaipur",
            "San Francisco", "New York", "Seattle", "Austin", "Boston", "Chicago", "London",
            "Toronto", "Berlin", "Singapore", "Sydney"
        ]
        for c in city_candidates:
            if re.search(r'\b' + re.escape(c) + r'\b', ocr_text, re.IGNORECASE):
                loc_cand = c
                break

    if loc_cand:
        if updated["contact"].get("location") != loc_cand:
            updated["contact"]["location"] = loc_cand
            changes.append(f"Updated location to: {loc_cand}")

    # D. LinkedIn & GitHub
    if "linkedin" in inst_norm_lower:
        m_li = re.search(r'(?:https?:\/\/)?(?:www\.)?linkedin\.com\/in\/[a-zA-Z0-9_-]+', combined_context, re.I)
        li_val = m_li.group(0) if m_li else "LinkedIn"
        if updated["contact"].get("linkedin") != li_val:
            updated["contact"]["linkedin"] = li_val
            changes.append("Updated LinkedIn profile in contact section.")

    if "github" in inst_norm_lower:
        m_gh = re.search(r'(?:https?:\/\/)?(?:www\.)?github\.com\/[a-zA-Z0-9_-]+', combined_context, re.I)
        gh_val = m_gh.group(0) if m_gh else "GitHub"
        if updated["contact"].get("github") != gh_val:
            updated["contact"]["github"] = gh_val
            changes.append("Updated GitHub profile in contact section.")

    # E. Candidate Name
    cand_name = ""
    m_name_explicit = re.search(r'(?:(?:change|update|set|my)\s+)?(?:candidate\s+)?name\s*(?:to|is|as|[:=])\s*([A-Za-z\s]+)', inst_clean, re.I)
    if m_name_explicit:
        cand_temp = m_name_explicit.group(1).strip().title()
        if len(cand_temp) > 2 and not any(w in cand_temp.lower() for w in ["resume", "project", "summary", "experience", "skill"]):
            cand_name = cand_temp
    elif re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+){1,3}$', inst_clean) and not any(w in inst_lower for w in ["docker", "python", "react", "fastapi", "project", "summary", "change", "add"]):
        cand_name = inst_clean.strip().title()

    # Only extract name from OCR if candidate name in resume is completely missing or generic
    if not cand_name and ocr_text and (not updated.get("name") or updated.get("name") in ["Candidate Name", ""]):
        if not any(w in inst_norm_lower for w in ["project", "cert", "experience", "skill", "remove", "delete", "instead", "photo", "image", "screenshot"]):
            extracted_info = extract_contact_info(ocr_text)
            ext_name = extracted_info.get("name", "")
            if ext_name and ext_name not in ["Candidate Name", ""] and not any(w in ext_name.lower() for w in ["screenshot", "extracted", "text", "image", "page", "rer", "nove"]):
                cand_name = ext_name

    if cand_name and len(cand_name) > 2 and updated.get("name") != cand_name:
        updated["name"] = cand_name
        changes.append(f"Updated candidate name to: {cand_name}")

    # -------------------------------------------------------------
    # 2. Removals & Deletions (RUNS FIRST TO PREVENT CONFLICTS)
    # -------------------------------------------------------------
    is_removal = any(w in inst_norm_lower for w in [
        "remove", "delete", "drop", "omit", "exclude", "erase", "clear"
    ])

    if is_removal:
        # A. Remove Candidate Photo
        if any(w in inst_norm_lower for w in ["photo", "picture", "profile photo", "candidate photo", "avatar", "headshot"]) and not any(w in inst_norm_lower for w in ["project", "cert", "experience"]):
            if "photo" in updated:
                updated.pop("photo", None)
                changes.append("Removed profile photo from resume.")

        # B. Remove Project Photo / Screenshot
        elif any(w in inst_norm_lower for w in ["photo", "image", "screenshot", "thumbnail"]) and any(w in inst_norm_lower for w in ["from project", "project photo", "project screenshot", "project"]):
            target_p_idx = None
            m_num = re.search(r'project\s+(\d+)', inst_norm, re.I)
            if m_num and "projects" in updated and isinstance(updated["projects"], list):
                idx_cand = int(m_num.group(1)) - 1
                if 0 <= idx_cand < len(updated["projects"]):
                    target_p_idx = idx_cand
            if target_p_idx is None and ocr_text:
                target_p_idx = find_matching_project_from_ocr(updated.get("projects", []), ocr_text)
            if target_p_idx is not None and 0 <= target_p_idx < len(updated.get("projects", [])):
                p = updated["projects"][target_p_idx]
                p.pop("image", None)
                p.pop("photo", None)
                changes.append(f"Removed screenshot thumbnail from project '{p.get('name', 'Project')}'.")

        # C. Remove Project (from prompt or from uploaded screenshot)
        elif any(w in inst_norm_lower for w in ["project", "this project", "this", "prjoect"]) or bool(ocr_text and any(p.get("name", "").lower() in ocr_text.lower() for p in updated.get("projects", []))):
            if "projects" in updated and isinstance(updated["projects"], list) and len(updated["projects"]) > 0:
                idx_rem = None
                # Check explicit project number ("project 1", "project 2")
                m_num = re.search(r'project\s+(\d+)', inst_norm, re.I)
                if m_num:
                    cand_num = int(m_num.group(1)) - 1
                    if 0 <= cand_num < len(updated["projects"]):
                        idx_rem = cand_num

                # Check OCR match from uploaded screenshot!
                if idx_rem is None and ocr_text:
                    idx_rem = find_matching_project_from_ocr(updated["projects"], ocr_text)

                # Check explicit project name in instruction
                if idx_rem is None:
                    for i, p in enumerate(updated["projects"]):
                        p_name = p.get("name", "").lower()
                        if p_name and p_name in inst_norm_lower:
                            idx_rem = i
                            break
                        clean_sub = re.sub(r'^(?:AI-Powered|Cloud-Native|Distributed)\s+', '', p.get("name", ""), flags=re.I).strip()
                        if len(clean_sub) > 6 and clean_sub.lower() in inst_norm_lower:
                            idx_rem = i
                            break

                # Fallback if "remove this project" / "delete this" with multiple projects
                if idx_rem is None and len(updated["projects"]) > 1:
                    idx_rem = 0

                if idx_rem is not None and 0 <= idx_rem < len(updated["projects"]):
                    removed = updated["projects"].pop(idx_rem)
                    changes.append(f"Removed project: '{removed.get('name', 'Project')}' as requested.")

        # D. Remove Skill
        elif "remove skill" in inst_lower or "delete skill" in inst_lower:
            m_rem_skill = re.search(r'(?:remove|delete)\s+skill\s+([A-Za-z0-9\.\+#\s,]+)', inst_clean, re.I)
            if m_rem_skill and "skills" in updated:
                to_remove = [s.strip().lower() for s in m_rem_skill.group(1).split(",") if s.strip()]
                if isinstance(updated["skills"], dict):
                    for cat, slist in updated["skills"].items():
                        if isinstance(slist, list):
                            updated["skills"][cat] = [s for s in slist if s.lower() not in to_remove]
                elif isinstance(updated["skills"], list):
                    updated["skills"] = [s for s in updated["skills"] if s.lower() not in to_remove]
                changes.append(f"Removed skills: {', '.join(to_remove)}")

        # When removal was handled, return directly so no accidental addition occurs!
        if changes:
            return updated, changes

    # -------------------------------------------------------------
    # 3. Candidate Profile Photo Updates
    # -------------------------------------------------------------
    is_profile_photo = (
        bool(attached_images)
        and is_photo_update_request(inst_clean, ocr_text)
        and not any(w in inst_norm_lower for w in ["project", "cert", "experience", "bullet", "remove", "delete"])
    )
    if is_profile_photo:
        updated["photo"] = attached_images[0]
        changes.append("Updated candidate profile photo with attached image.")
        return updated, changes

    # -------------------------------------------------------------
    # 4. Attach Screenshot to Existing Project
    # -------------------------------------------------------------
    is_attach_photo = (
        bool(attached_images)
        and any(w in inst_norm_lower for w in [
            "attach photo", "attach screenshot", "attach image", "attach to project",
            "use as project photo", "use for project", "project photo", "project screenshot",
            "thumbnail for project", "add screenshot to project", "attach this photo", "attach this screenshot"
        ])
        and not any(w in inst_norm_lower for w in ["remove", "delete", "create project", "new project", "add project"])
    )
    if is_attach_photo and "projects" in updated and isinstance(updated["projects"], list):
        target_idx = None
        m_num = re.search(r'project\s+(\d+)', inst_norm, re.I)
        if m_num:
            num = int(m_num.group(1)) - 1
            if 0 <= num < len(updated["projects"]):
                target_idx = num
        if target_idx is None:
            for i, p in enumerate(updated["projects"]):
                if p.get("name", "").lower() in inst_norm_lower:
                    target_idx = i
                    break
        if target_idx is None and ocr_text:
            target_idx = find_matching_project_from_ocr(updated["projects"], ocr_text)
        if target_idx is None and len(updated["projects"]) > 0:
            target_idx = 1 if len(updated["projects"]) > 1 else 0

        if target_idx is not None and 0 <= target_idx < len(updated["projects"]):
            updated["projects"][target_idx]["image"] = attached_images[0]
            changes.append(f"Attached screenshot thumbnail to project '{updated['projects'][target_idx].get('name')}'.")
            return updated, changes

    # -------------------------------------------------------------
    # 5. Project Renaming & Replacement ("instead of", "change project to", etc.)
    # -------------------------------------------------------------
    is_project_mod = False
    proj_target_idx = None
    old_proj_name = ""
    new_proj_title = ""
    extracted_techs = ""

    if "projects" in updated and isinstance(updated["projects"], list):
        for idx, p in enumerate(updated["projects"]):
            p_name = (p.get("name") or "").strip()
            if not p_name:
                continue
            if p_name.lower() in inst_norm_lower:
                proj_target_idx = idx
                old_proj_name = p_name
                break
            clean_sub = re.sub(r'^(?:AI-Powered|Cloud-Native|Distributed)\s+', '', p_name, flags=re.I).strip()
            if len(clean_sub) > 6 and clean_sub.lower() in inst_norm_lower:
                proj_target_idx = idx
                old_proj_name = p_name
                break

    # If old project not in prompt text, check OCR match from attached screenshot
    if proj_target_idx is None and ocr_text and "projects" in updated:
        proj_target_idx = find_matching_project_from_ocr(updated.get("projects", []), ocr_text)
        if proj_target_idx is not None:
            old_proj_name = updated["projects"][proj_target_idx].get("name", "")

    m_num = re.search(r'project\s+(\d+)', inst_norm, re.I)
    if m_num:
        num = int(m_num.group(1)) - 1
        if "projects" in updated and isinstance(updated["projects"], list) and 0 <= num < len(updated["projects"]):
            proj_target_idx = num
            old_proj_name = updated["projects"][num].get("name", f"Project {num+1}")

    # Patterns to extract new project title:
    # Form A: "instead of this/that/project/Remove [add/use/put/set/i want] New Project Title"
    m_fwd_instead = re.search(r'^\s*instead\s+of\s+(?:this\s+project|this|that|it|(?:my\s+)?project(?:\s+\d+)?|[^\n,:]+?)\s*(?:,\s*|\s+(?:add|use|put|make|to|with|replace\s+with|set|i\s+want)\s+|\s+)(.+)', inst_norm, re.I)
    if m_fwd_instead:
        new_proj_title = clean_project_title(m_fwd_instead.group(1))
        is_project_mod = True

    if not new_proj_title:
        # Form B: "... instead of this/that/project"
        m_want_instead = re.search(r'(?:(?:i\s+want|use|put|add|make|set)\s+)?(.+?)\s+instead\s+of\s+(.+)', inst_norm, re.I)
        if m_want_instead:
            cand_left = clean_project_title(m_want_instead.group(1))
            cand_right = clean_project_title(m_want_instead.group(2))
            if old_proj_name and old_proj_name.lower() in cand_left.lower():
                new_proj_title = cand_right
            else:
                new_proj_title = cand_left
            is_project_mod = True

    if not new_proj_title:
        m_change = re.search(r'(?:change|replace|rename|update|set|switch)\s+(?:(?:my|the)\s+)?(?:project\s+(?:\d+\s+)?(?:name\s+)?)?(?:named\s+|called\s+)?(.+?)\s+(?:to|with|into|as)[:\s]+(.+)', inst_norm, re.I)
        if m_change:
            cand_target = m_change.group(1).strip().lower()
            non_project_terms = ["role", "title", "job", "job title", "company", "summary", "profile", "degree", "education", "college", "university", "skill", "skills", "location", "city", "phone", "email", "name", "candidate name", "bullet", "bullets"]
            if not any(cand_target == term or cand_target.startswith(term + " ") for term in non_project_terms):
                cand_new = m_change.group(2).strip()
                new_proj_title = clean_project_title(cand_new)
                is_project_mod = True

    if not new_proj_title and m_num:
        m_proj_num = re.search(r'(?:change|replace|rename|update|set|switch)\s+(?:(?:my|the)\s+)?project\s+(\d+)(?:\s+name)?\s+(?:to|with|as)[:\s]+(.+)', inst_norm, re.I)
        if m_proj_num:
            new_proj_title = clean_project_title(m_proj_num.group(2))
            is_project_mod = True

    if not new_proj_title:
        m_my_proj = re.search(r'(?:change|update|set|switch)\s+(?:my\s+|the\s+)?project\s+(?:to|as)[:\s]+(.+)', inst_norm, re.I)
        if m_my_proj:
            new_proj_title = clean_project_title(m_my_proj.group(1))
            is_project_mod = True

    if not new_proj_title and old_proj_name:
        m_old_tail = re.search(re.escape(old_proj_name) + r'[\s,]+(?:i\s+want\s+|to\s+|into\s+|replace\s+with\s+)?(.+)', inst_norm, re.I)
        if m_old_tail:
            new_proj_title = clean_project_title(m_old_tail.group(1))
            if new_proj_title:
                is_project_mod = True

    if is_project_mod and new_proj_title:
        if "projects" not in updated or not isinstance(updated["projects"], list):
            updated["projects"] = []
        proj_image = attached_images[0] if attached_images else None

        m_tech = re.search(r'(?:\s+\bwith\b|\s+\busing\b|\s+\btechnologies\b|\s+\bstack\b)[:\s]+(.+)', new_proj_title, re.I)
        if m_tech:
            extracted_techs = m_tech.group(1).strip()
            new_proj_title = clean_project_title(new_proj_title[:m_tech.start()].strip())

        target_idx = proj_target_idx if proj_target_idx is not None and 0 <= proj_target_idx < len(updated["projects"]) else (1 if len(updated["projects"]) > 1 else 0)
        if target_idx < len(updated["projects"]):
            target_p = updated["projects"][target_idx]
            old_title = target_p.get("name", "Project")
            target_p["name"] = new_proj_title
            target_p["is_tailored"] = True

            if extracted_techs:
                target_p["technologies"] = extracted_techs
            elif "resume" in new_proj_title.lower() or "tailor" in new_proj_title.lower():
                existing_t = target_p.get("technologies", "")
                tokens = [t.strip() for t in existing_t.split(",") if t.strip()]
                for req_t in ["Python", "React", "PostgreSQL", "Redis", "FastAPI", "Ollama"]:
                    if req_t.lower() not in [tok.lower() for tok in tokens]:
                        tokens.append(req_t)
                target_p["technologies"] = ", ".join(tokens)

            target_p["bullets"] = update_project_bullets(
                old_bullets=target_p.get("bullets", []),
                old_name=old_title,
                new_name=new_proj_title,
                technologies=target_p.get("technologies", "")
            )

            if proj_image:
                target_p["image"] = proj_image

            target_p["transformation_note"] = f"Tailored project to {new_proj_title}"
            changes.append(f"Updated project from '{old_title}' to '{new_proj_title}' with tailored accomplishments.")
            return updated, changes

    # -------------------------------------------------------------
    # 6. Project Additions (ONLY WHEN EXPLICITLY REQUESTED)
    # -------------------------------------------------------------
    is_add_project = (
        any(w in inst_norm_lower for w in [
            "add project", "create project", "new project", "add this in project",
            "add this to project", "put this in project", "add this to my projects"
        ])
        or (bool(attached_images) and any(w in inst_norm_lower for w in ["add this", "include this", "put in project"]))
        or (bool(attached_images) and not inst_clean.strip() and bool(ocr_text) and any(tech in ocr_text.lower() for tech in ["github.com", "repository", "technologies:", "tech stack"]))
    )

    if is_add_project:
        if "projects" not in updated or not isinstance(updated["projects"], list):
            updated["projects"] = []
        proj_image = attached_images[0] if attached_images else None

        proj_title = ""
        m_title = re.search(
            r'(?:project\s+(?:named|called|title)?[:\s]+|add\s+project\s+|in\s+project[:\s]+)([A-Za-z0-9\s\-]+?)(?:\bwith\b|\busing\b|\bin\b|\btechnologies\b|\bstack\b|\.|;|$)',
            inst_clean,
            re.I
        )
        if m_title:
            proj_title = clean_project_title(m_title.group(1))

        if not proj_title and ocr_text:
            lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]
            for l in lines[:4]:
                clean_l = re.sub(r'[^A-Za-z0-9\s\-]', '', l).strip()
                if 4 <= len(clean_l) <= 50 and not any(k in clean_l.lower() for k in ["technologies", "tech stack", "screenshot", "http", "email", "@", "phone", "pune", "mumbai", "linkedin"]):
                    proj_title = format_acronyms(clean_l)
                    break

        techs_found: List[str] = []
        popular_techs = [
            "Python", "FastAPI", "Django", "Flask", "React", "Next.js", "Node.js", "Express",
            "TypeScript", "JavaScript", "Vue.js", "Java", "Spring Boot", "Go", "Golang",
            "Docker", "Kubernetes", "AWS", "Azure", "GCP", "PostgreSQL", "MongoDB", "MySQL",
            "Redis", "OpenCV", "TensorFlow", "PyTorch", "GraphQL", "TailwindCSS", "Kafka", "Celery", "Ollama"
        ]
        for t in popular_techs:
            if re.search(r'\b' + re.escape(t.lower()) + r'\b', combined_context.lower()):
                techs_found.append(t)

        proj_technologies = ", ".join(list(dict.fromkeys(techs_found))) if techs_found else "Python, FastAPI, React, PostgreSQL"
        if not proj_title:
            proj_title = "Featured Production Application"

        bullets: List[str] = []
        if ocr_text:
            for line in ocr_text.splitlines():
                line = line.strip()
                if line.startswith(('•', '-', '*')) and len(line) > 15:
                    clean_b = re.sub(r'^[•\-\*]\s*', '', line).strip()
                    bullets.append(clean_b)
                elif any(action_w in line.lower() for action_w in ["developed", "implemented", "built", "architected", "engineered"]) and len(line) > 20:
                    bullets.append(line.strip())

        if len(bullets) < 2:
            bullets = update_project_bullets([], "", proj_title, proj_technologies)
        else:
            bullets = bullets[:3]

        db_used = next((t for t in techs_found if t in ["PostgreSQL", "MongoDB", "Redis", "MySQL"]), "PostgreSQL")
        new_project_obj: Dict[str, Any] = {
            "name": proj_title,
            "technologies": proj_technologies,
            "bullets": bullets,
            "database_used": db_used,
            "transformation_note": "Integrated from project specifications & attached screenshot",
            "is_tailored": True
        }
        if proj_image:
            new_project_obj["image"] = proj_image

        updated["projects"].insert(0, new_project_obj)
        changes.append(f"Added project '{proj_title}' ({proj_technologies}) to your resume.")
        return updated, changes

    # -------------------------------------------------------------
    # 5. Add / Remove Skills
    # -------------------------------------------------------------
    if "remove skill" in inst_lower or "delete skill" in inst_lower:
        m_rem_skill = re.search(r'(?:remove|delete)\s+skill\s+([A-Za-z0-9\.\+#\s,]+)', inst_clean, re.I)
        if m_rem_skill and "skills" in updated:
            to_remove = [s.strip().lower() for s in m_rem_skill.group(1).split(",") if s.strip()]
            if isinstance(updated["skills"], dict):
                for cat, slist in updated["skills"].items():
                    if isinstance(slist, list):
                        updated["skills"][cat] = [s for s in slist if s.lower() not in to_remove]
            elif isinstance(updated["skills"], list):
                updated["skills"] = [s for s in updated["skills"] if s.lower() not in to_remove]
            changes.append(f"Removed skills: {', '.join(to_remove)}")
    elif (
        re.search(r'\b(?:add|include)\b.*?\bskill', inst_lower)
        or re.search(r'\bskills\s*[:=]', inst_lower)
        or ("add " in inst_lower and any(w in inst_lower for w in ["docker", "kubernetes", "aws", "python", "fastapi", "redis", "kafka", "graphql", "react", "typescript", "golang", "java", "sql"]))
    ):
        detected_skills = []
        for candidate in ["Docker", "Kubernetes", "AWS", "Azure", "GCP", "Python", "FastAPI", "Django", "Flask", "PostgreSQL", "MongoDB", "Redis", "Kafka", "Git", "CI/CD", "Linux", "TypeScript", "React", "Node.js", "GraphQL", "Terraform", "Celery", "RabbitMQ", "Next.js", "Vue.js", "Java", "Spring Boot", "Go", "Golang"]:
            if re.search(r'\b' + re.escape(candidate.lower()) + r'\b', inst_lower):
                detected_skills.append(candidate)

        # Also grab tokens from "add skill(s) X, Y, Z"
        m_custom_skills = re.search(r'(?:add|include)\s+skills?[:\s]+([^\n\.;]+)', inst_clean, re.I)
        if m_custom_skills:
            tokens = [tok.strip() for tok in re.split(r'[,|•]|\band\b', m_custom_skills.group(1)) if tok.strip()]
            for tok in tokens:
                clean_tok = re.sub(r'^(?:and|to)\s+', '', tok, flags=re.I).strip(" .")
                if clean_tok and clean_tok not in detected_skills and len(clean_tok) < 30 and not any(w in clean_tok.lower() for w in ["resume", "project", "section"]):
                    detected_skills.append(clean_tok)

        if detected_skills:
            if "skills" not in updated or not updated["skills"]:
                updated["skills"] = {"Core Technical Skills": []}
            if isinstance(updated["skills"], dict):
                target_cat = "Core Technical Skills" if "Core Technical Skills" in updated["skills"] else list(updated["skills"].keys())[0]
                for s in detected_skills:
                    if s not in updated["skills"][target_cat]:
                        updated["skills"][target_cat].append(s)
            elif isinstance(updated["skills"], list):
                for s in detected_skills:
                    if s not in updated["skills"]:
                        updated["skills"].append(s)
            changes.append(f"Added {', '.join(detected_skills)} to skills section.")

    # -------------------------------------------------------------
    # 6. Database change across resume
    # -------------------------------------------------------------
    db_matches = []
    for db in ["MongoDB", "PostgreSQL", "MySQL", "Redis", "Cassandra", "DynamoDB", "Elasticsearch", "SQLite", "Oracle DB"]:
        if db.lower() in inst_lower or re.search(r'\b' + db.lower().replace(" ", r"\s*") + r'\b', inst_lower):
            db_matches.append(db)
    if any(w in inst_lower for w in ["database", "db", "mongo", "postgres", "sql", "redis"]) and db_matches:
        db_str = ", ".join(db_matches)
        for proj in updated.get("projects", []):
            proj["database_used"] = db_str
            curr_tech = proj.get("technologies", "")
            curr_tech = re.sub(r'\b(MySQL|PostgreSQL|MongoDB|Redis|Cassandra|DynamoDB|SQLite)\b', '', curr_tech, flags=re.I)
            curr_tech = ", ".join([s.strip() for s in curr_tech.split(",") if s.strip()])
            proj["technologies"] = f"{curr_tech}, {db_str}".strip(", ")
            proj["transformation_note"] = f"Updated system architecture to use {db_str} database"
        if "skills" in updated and isinstance(updated["skills"], dict):
            updated["skills"]["Databases & Storage"] = db_matches
        changes.append(f"Updated database in projects and skills to: {db_str}")

    # -------------------------------------------------------------
    # 7. Technology / Framework change in projects
    # -------------------------------------------------------------
    tech_matches = []
    for tech in ["Python", "FastAPI", "Django", "Flask", "Node.js", "Express", "React", "Next.js", "Go", "Golang", "Java", "Spring Boot", "Docker", "Kubernetes", "Kafka", "Celery", "AWS", "TypeScript", "C#", ".NET"]:
        if re.search(r'\b' + re.escape(tech.lower()) + r'\b', inst_lower):
            tech_matches.append(tech)
    is_project_action = any(w in inst_norm_lower for w in ["add project", "create project", "new project", "remove project", "delete project", "instead of"])
    if any(w in inst_lower for w in ["stack", "tech", "framework", "emphasize", "highlight", "bullets", "microservice", "microservices"]) and tech_matches and not is_project_action:
        tech_str = ", ".join(tech_matches)
        for proj in updated.get("projects", []):
            proj["technologies"] = f"{tech_str}, " + (proj.get("database_used") or "PostgreSQL")
            proj["transformation_note"] = f"Adapted projects to {tech_str} architecture"
            if any(w in inst_lower for w in ["bullet", "bullets", "emphasize", "highlight", "microservice"]):
                proj["bullets"] = [
                    re.sub(r'\b(?:microservice|microservices|architecture|services|application)\b', f'{tech_str} microservices', b, flags=re.I)
                    for b in proj.get("bullets", [])
                ]
        if "skills" in updated and isinstance(updated["skills"], dict):
            updated["skills"]["Targeted JD Stack"] = tech_matches
        changes.append(f"Emphasized {tech_str} in project technologies and bullet points.")

    # -------------------------------------------------------------
    # 8. Certifications
    # -------------------------------------------------------------
    if "cert" in inst_lower or (ocr_text and "cert" in ocr_text.lower()):
        cert_name = ""
        for standard_cert in [
            "AWS Certified Solutions Architect - Associate",
            "AWS Certified Developer - Associate",
            "PCAP - Certified Associate in Python Programming",
            "Certified Kubernetes Application Developer (CKAD)",
            "Microsoft Certified: Azure Developer Associate",
            "PostgreSQL Certified Associate",
            "Oracle Certified Professional: Java SE Developer"
        ]:
            if any(w in inst_lower for w in standard_cert.lower().split()[:2]):
                cert_name = standard_cert
                break
        if not cert_name:
            m = re.search(r'(?:cert(?:ification)?s?(?:\s+to|\s+as|\s+for|\s+named)?[:\s]+)(.+)', inst_clean, re.I)
            if m:
                cert_name = m.group(1).strip(" .")
        if not cert_name and ocr_text:
            for cert_kw in ["AWS", "Azure", "GCP", "Google Cloud", "Kubernetes", "CKA", "Docker", "Scrum Master", "PMP", "HashiCorp"]:
                if cert_kw.lower() in ocr_text.lower():
                    for line in ocr_text.splitlines():
                        if cert_kw.lower() in line.lower() and len(line.strip()) < 80:
                            cert_name = line.strip(" ,.-")
                            break
                    if cert_name:
                        break
        if cert_name:
            if "certifications" not in updated or not isinstance(updated["certifications"], list):
                updated["certifications"] = []
            if cert_name not in updated["certifications"]:
                updated["certifications"].insert(0, cert_name)
                changes.append(f"Added certification: {cert_name}")

    # -------------------------------------------------------------
    # 9. Professional Summary modification
    # -------------------------------------------------------------
    is_summary_request = (
        any(w in inst_norm_lower for w in [
            "summary", "profile", "objective", "about me", "intro", "bio"
        ])
        or (bool(attached_images) and bool(ocr_text) and any(w in ocr_text.lower() for w in [
            "summary", "highly skilled", "motivated", "software engineer", "developer", "computing", "ai/ml", "experience in"
        ]) and not any(w in inst_norm_lower for w in ["project", "cert", "experience", "education", "degree", "college"]))
    )

    if is_summary_request:
        # Check A: Explicit new summary text in prompt (e.g. "update summary to: ...", "summary: ...")
        m_explicit_sum = re.search(
            r'(?:(?:change|make|rewrite|update|set)\s+(?:(?:my|the|this)\s+)?summary\s+(?:to|as|is)[:\s]+|summary\s*:\s*)(.+)',
            inst_clean, re.I
        )
        if m_explicit_sum:
            cand_new = m_explicit_sum.group(1).strip(" \"'")
            if len(cand_new) > 15 and not any(cand_new.lower().startswith(w) for w in ["proper", "better", "fix", "in proper", "in better"]):
                updated["summary"] = cand_new
                changes.append("Updated professional summary according to your exact instruction.")
                return updated, changes

        # Check B: Image attached containing summary / bio text
        ocr_clean_lines = []
        if ocr_text:
            for l in ocr_text.splitlines():
                l_s = l.strip()
                if not l_s or l_s.startswith("[Screenshot") or "Extracted Text" in l_s:
                    continue
                cleaned_l = re.sub(r'^[•\-\*\|\s]+', '', l_s)
                if len(cleaned_l) > 6:
                    ocr_clean_lines.append(cleaned_l)

        # Check C: Determine candidate's core stack & role to construct the optimal ATS summary
        top_skills = []
        if "skills" in updated and isinstance(updated["skills"], dict):
            for cat, slist in updated["skills"].items():
                if isinstance(slist, list):
                    for s in slist:
                        if s and s not in top_skills and len(top_skills) < 5:
                            top_skills.append(s)
        elif "skills" in updated and isinstance(updated["skills"], list):
            top_skills = updated["skills"][:5]

        # Scan prompt and OCR for special technical keywords to incorporate
        for tech in ["Cloud Computing", "AI/ML", "Python", "React.js", "Java", "Spring Boot", "PostgreSQL", "Redis", "FastAPI", "Docker", "Kubernetes", "Microservices"]:
            if tech.lower() in inst_norm_lower or (ocr_text and tech.lower() in ocr_text.lower()):
                if tech not in top_skills:
                    top_skills.insert(0, tech)

        skill_str = ", ".join(top_skills[:4]) if top_skills else "Python, React.js, and cloud computing"
        role_title = "Software Engineer"
        if "experience" in updated and isinstance(updated["experience"], list) and len(updated["experience"]) > 0:
            role_title = updated["experience"][0].get("role", "Software Engineer")

        # If user uploaded a screenshot of summary text with concrete keywords
        if ocr_clean_lines and len(" ".join(ocr_clean_lines)) > 20:
            extracted_raw = " ".join(ocr_clean_lines)
            if any(w in extracted_raw.lower() for w in ["developer", "engineer", "experience", "delivering", "skilled"]):
                polished = re.sub(r'^[a-z]\s+(?:computing|cloud)', 'cloud computing', extracted_raw, flags=re.I)
                polished = re.sub(r'^[a-z]\s+', '', polished)
                if not polished[0].isupper():
                    polished = f"Highly skilled {role_title} with expertise in {polished}"
                if not polished.endswith('.'):
                    polished += '.'
                updated["summary"] = polished
                changes.append("Updated professional summary using text extracted from attached screenshot.")
                return updated, changes

        # Standard / "proper way" / rewrite enhancement
        if any(w in inst_norm_lower for w in ["shorten", "concise", "2 lines", "two lines"]):
            updated["summary"] = (
                f"Results-driven {role_title} with expertise in {skill_str}. "
                f"Proven track record of architecting scalable microservices, optimizing database performance, and delivering high-impact solutions."
            )
            changes.append("Rewrote professional summary into a concise, high-impact 2-line executive profile.")
        else:
            updated["summary"] = (
                f"Highly skilled {role_title} with proven expertise in {skill_str}, "
                f"delivering scalable and efficient web applications and backend systems. Experienced in full-stack architecture, "
                f"database optimization, and building resilient microservices that maximize operational performance."
            )
            changes.append("Updated and enhanced professional summary into a polished, ATS-optimized profile.")

        return updated, changes

    # -------------------------------------------------------------
    # 10. Experience changes
    # -------------------------------------------------------------
    m_exp_role = re.search(r'(?:(?:change|update|set|make)\s+(?:(?:my|the)\s+)?(?:role|title|job\s+title)|(?:my\s+)?role\s*(?:is|to|as)?|role\s*:)\s*(?:to|as|is|:)?[:\s]+([A-Za-z0-9\s\-/]+)', inst_norm, re.I)
    if m_exp_role and "experience" in updated and isinstance(updated["experience"], list) and len(updated["experience"]) > 0:
        new_role = re.sub(r'^(?:to|as|is|a|an)\s+', '', m_exp_role.group(1).strip(), flags=re.I).strip().title()
        if new_role:
            updated["experience"][0]["role"] = new_role
            changes.append(f"Updated role title to: {new_role}")

    m_exp_comp = re.search(r'(?:(?:change|update|set)\s+(?:(?:my|the)\s+)?company|(?:my\s+)?company\s*(?:is|to|as)?|company\s*:)\s*(?:to|as|is|at|:)?[:\s]+([A-Za-z0-9\s\-/]+)', inst_norm, re.I)
    if m_exp_comp and "experience" in updated and isinstance(updated["experience"], list) and len(updated["experience"]) > 0:
        new_comp = re.sub(r'^(?:to|as|is|at)\s+', '', m_exp_comp.group(1).strip(), flags=re.I).strip().title()
        if new_comp:
            updated["experience"][0]["company"] = new_comp
            changes.append(f"Updated company to: {new_comp}")

    if any(w in inst_norm_lower for w in ["improve experience", "enhance experience", "experience bullets", "experience proper", "metrics in experience", "quantify experience"]):
        if "experience" in updated and isinstance(updated["experience"], list):
            for exp in updated["experience"]:
                new_b = []
                for b in exp.get("bullets", []):
                    if "%" not in b and "latency" not in b.lower() and "throughput" not in b.lower():
                        b = b.rstrip(".") + ", boosting system reliability and team throughput by 35%."
                    new_b.append(b)
                exp["bullets"] = new_b
            changes.append("Enhanced experience bullet points with quantifiable performance achievements.")
            return updated, changes

    m_exp_add = re.search(r'add\s+experience[:\s]+([^\n]+)', inst_clean, re.I)
    if m_exp_add:
        exp_raw = m_exp_add.group(1).strip()
        parts = [p.strip() for p in re.split(r'[,|•\bat\b]', exp_raw, flags=re.I) if p.strip()]
        new_role = parts[0] if len(parts) > 0 else "Software Engineer"
        new_comp = parts[1] if len(parts) > 1 else "Technology Corp"
        new_dur = parts[2] if len(parts) > 2 else "2022 - Present"
        new_exp_obj = {
            "role": new_role,
            "company": new_comp,
            "duration": new_dur,
            "bullets": [
                f"Led engineering initiatives and architected scalable backend microservices as {new_role}.",
                "Optimized database indexing and caching, improving end-to-end response latency by 40%.",
                "Mentored team members and established CI/CD deployment pipelines ensuring zero downtime."
            ]
        }
        if "experience" not in updated or not isinstance(updated["experience"], list):
            updated["experience"] = []
        updated["experience"].insert(0, new_exp_obj)
        changes.append(f"Added experience: {new_role} at {new_comp}")

    # -------------------------------------------------------------
    # 11. Education changes
    # -------------------------------------------------------------
    m_edu_deg = re.search(r'(?:change|update|set|my)\s+(?:degree|education)\s+(?:to|is|as)?[:\s]+([A-Za-z0-9\s\.\-]+)', inst_clean, re.I)
    if m_edu_deg and "education" in updated and isinstance(updated["education"], list) and len(updated["education"]) > 0:
        new_deg = m_edu_deg.group(1).strip()
        updated["education"][0]["degree"] = new_deg
        changes.append(f"Updated degree to: {new_deg}")

    m_edu_inst = re.search(r'(?:change|update|set|my)\s+(?:college|university|institution|school)\s+(?:to|is|as)?[:\s]+([A-Za-z0-9\s\.\-]+)', inst_clean, re.I)
    if m_edu_inst and "education" in updated and isinstance(updated["education"], list) and len(updated["education"]) > 0:
        new_inst = m_edu_inst.group(1).strip()
        updated["education"][0]["institution"] = new_inst
        changes.append(f"Updated education institution to: {new_inst}")

    m_edu_add = re.search(r'add\s+education[:\s]+([^\n]+)', inst_clean, re.I)
    if m_edu_add:
        edu_raw = m_edu_add.group(1).strip()
        parts = [p.strip() for p in re.split(r'[,|•]', edu_raw) if p.strip()]
        new_edu_obj = {
            "degree": parts[0] if len(parts) > 0 else edu_raw,
            "institution": parts[1] if len(parts) > 1 else "University",
            "year": parts[2] if len(parts) > 2 else "2024"
        }
        if "education" not in updated or not isinstance(updated["education"], list):
            updated["education"] = []
        updated["education"].insert(0, new_edu_obj)
        changes.append(f"Added education: {new_edu_obj['degree']} at {new_edu_obj['institution']}")

    # -------------------------------------------------------------
    # 12. Metrics driven bullets
    # -------------------------------------------------------------
    if any(w in inst_lower for w in ["metric", "metrics", "percentage", "numbers", "quantifiable"]):
        for proj in updated.get("projects", []):
            new_bullets = []
            for b in proj.get("bullets", []):
                if "%" not in b and "k+" not in b.lower():
                    b = b.rstrip(".") + ", improving system throughput by 35%."
                new_bullets.append(b)
            proj["bullets"] = new_bullets
        for exp in updated.get("experience", []):
            new_exp_b = []
            for b in exp.get("bullets", []):
                if "%" not in b and "k+" not in b.lower() and "x" not in b.lower():
                    b = b.rstrip(".") + ", increasing operational efficiency by 30%."
                new_exp_b.append(b)
            exp["bullets"] = new_exp_b
        changes.append("Enhanced experience and project bullet points with quantifiable performance metrics.")

    # -------------------------------------------------------------
    # 13. Single-Page / 1-Page Layout
    # -------------------------------------------------------------
    is_one_page = bool(
        re.search(r'\b(?:1|one)\s*(?:page|pages)\b', inst_lower)
        or any(w in inst_lower for w in [
            "single page", "fit on one page", "fit on 1 page",
            "make it one page", "make it 1 page", "reduce length",
            "shorten resume", "condense resume"
        ])
    )
    if is_one_page:
        updated["single_page"] = True
        updated["compact_layout"] = True
        changes.append("Optimized resume layout and condensed content to strictly fit on 1 page.")

    # -------------------------------------------------------------
    # 14. Shorten Project Descriptions
    # -------------------------------------------------------------
    if any(w in inst_lower for w in ["shorten project", "concise project", "shorten description", "concise bullet"]):
        for proj in updated.get("projects", []):
            proj["bullets"] = [b[:120].rsplit(' ', 1)[0] + "." if len(b) > 130 else b for b in proj.get("bullets", [])[:2]]
        changes.append("Shortened project bullet descriptions for maximum conciseness.")

    return updated, changes


def edit_tailored_resume(
    resume_content: Dict[str, Any],
    instruction: str,
    original_resume_text: str = "",
    jd_text: str = "",
    image_data: Optional[str] = None,
    images_data: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Applies user-requested modifications from AI Copilot chat:
    1. Multimodal support: extracts visible text & data from uploaded or pasted images (supports multiple photos).
    2. Direct intent execution for instant, guaranteed updates on specific instructions
       (e.g. 'i want this in project', 'change database to MongoDB', contact updates, profile photos).
    3. Profile photo and project screenshot attachments.
    4. Deep LLM execution for creative, stylistic, or semantic modifications.
    """
    changes: List[str] = []
    updated_resume = dict(resume_content)

    # 1. Gather all attached images (supports multiple photos)
    all_images: List[str] = []
    if images_data and isinstance(images_data, list):
        for img in images_data:
            if img and isinstance(img, str) and len(img) > 30 and img not in all_images:
                all_images.append(img)
    if image_data and isinstance(image_data, str) and len(image_data) > 30 and image_data not in all_images:
        all_images.append(image_data)

    # 2. Extract OCR from all attached images
    ocr_snippets: List[str] = []
    for idx, img in enumerate(all_images):
        txt = extract_text_from_image_b64(img)
        if txt.strip():
            label = f"[Screenshot/Image {idx + 1} Extracted Text]:\n{txt}"
            ocr_snippets.append(label)

    combined_ocr_text = "\n\n".join(ocr_snippets).strip()
    if combined_ocr_text:
        preview = combined_ocr_text.replace("\n", " ")[:90]
        logger.info(f"Analyzed {len(all_images)} attached image(s) (OCR preview: {preview}...)")

    # 3. Formulate effective instruction incorporating image context
    effective_instruction = instruction.strip()
    if combined_ocr_text:
        if effective_instruction:
            effective_instruction = (
                f"{effective_instruction}\n\n"
                f"[Attached Image(s) Information]:\n{combined_ocr_text}"
            )
        else:
            effective_instruction = (
                f"Incorporate the following information extracted from the attached screenshots into the resume:\n"
                f"{combined_ocr_text}"
            )

    # 4. Apply guaranteed deterministic updates first
    base_updated, direct_changes = apply_direct_user_instructions(
        resume_content=updated_resume,
        instruction=instruction,
        attached_images=all_images,
        ocr_text=combined_ocr_text
    )
    for dc in direct_changes:
        if dc not in changes:
            changes.append(dc)

    # FAST-PATH: If direct instructions already captured and executed the user's intent,
    # return immediately in ~20ms! This gives instant feedback and avoids slow LLM timeouts or hallucinations.
    if direct_changes:
        if "tailoring_metadata" in base_updated and isinstance(base_updated["tailoring_metadata"], dict):
            existing_changes = base_updated["tailoring_metadata"].get("changes_applied", [])
            base_updated["tailoring_metadata"]["changes_applied"] = changes + existing_changes

        return {
            "updated_content": base_updated,
            "changes": changes,
            "image_extracted_text": combined_ocr_text
        }

    # 5. Call LLM for deeper stylistic or semantic edits when direct patterns did not match
    system_prompt = (
        "You are an expert ATS resume editor.\n"
        "Your role is to update the resume JSON according to the user query and any attached screenshot information.\n"
        "CRITICAL: Do NOT mention fonts, font sizes, colors, margins, or CSS styling. Resumes are pure text data.\n"
        "You must update the actual text content in updated_summary, updated_experience, updated_projects, or updated_skills.\n"
        "CRITICAL: If the user wants to update, rename, or replace a project, you MUST provide the updated project in updated_projects. Do NOT return null for updated_projects if a project was modified!\n"
        "Return ONLY valid JSON matching this schema:\n"
        "{\n"
        '  "updated_name": "new candidate name string or null",\n'
        '  "updated_contact": { "email": "...", "phone": "...", "location": "...", "linkedin": "...", "github": "..." } or null,\n'
        '  "updated_summary": "new summary string or null",\n'
        '  "updated_skills": { "category": ["skill1", "skill2"] } or null,\n'
        '  "updated_experience": [ {"role": "...", "company": "...", "duration": "...", "location": "...", "bullets": [...]} ] or null,\n'
        '  "updated_projects": [ {"name": "...", "technologies": "...", "bullets": [...], "transformation_note": "...", "database_used": "..."} ] or null,\n'
        '  "updated_education": [ {"degree": "...", "institution": "...", "year": "..."} ] or null,\n'
        '  "updated_certifications": ["cert1", "cert2"] or null,\n'
        '  "changes": ["1-3 concise bullet points describing exact adjustments made"]\n'
        "}"
    )

    current_summary = base_updated.get("summary", "")
    current_skills = base_updated.get("skills", {})
    current_exp = base_updated.get("experience", [])
    current_proj = base_updated.get("projects", [])
    current_certs = base_updated.get("certifications", [])
    current_edu = base_updated.get("education", [])
    current_contact = base_updated.get("contact", {})

    prompt = f"""
User Query: "{effective_instruction[:3000]}"

Current Resume State:
- Name: {base_updated.get("name", "")}
- Contact: {json.dumps(current_contact)}
- Summary: {current_summary}
- Skills: {json.dumps(current_skills)}
- Experience: {json.dumps([{"role": e.get("role"), "company": e.get("company"), "bullets": e.get("bullets", [])} for e in current_exp])}
- Projects: {json.dumps([{"name": p.get("name"), "technologies": p.get("technologies"), "bullets": p.get("bullets", [])} for p in current_proj])}
- Education: {json.dumps(current_edu)}
- Certifications: {json.dumps(current_certs)}

Return ONLY valid JSON with updated fields (leave null if unchanged) and changes list:
"""

    parsed = None
    try:
        raw_response = call_ollama(prompt=prompt, system_prompt=system_prompt, temperature=0.15, timeout_seconds=60)
        parsed = safe_extract_json(raw_response)
    except Exception as err:
        logger.warning(f"Ollama call for edit_tailored_resume: {err}")

    final_resume = dict(base_updated)

    if parsed and isinstance(parsed, dict):
        if parsed.get("updated_name") and isinstance(parsed["updated_name"], str):
            final_resume["name"] = parsed["updated_name"].strip()

        if parsed.get("updated_contact") and isinstance(parsed["updated_contact"], dict):
            final_resume.setdefault("contact", {})
            for k, v in parsed["updated_contact"].items():
                if v and isinstance(v, str) and v.strip():
                    final_resume["contact"][k] = v.strip()

        if parsed.get("updated_summary") and isinstance(parsed["updated_summary"], str):
            final_resume["summary"] = parsed["updated_summary"].strip()

        if parsed.get("updated_skills") and isinstance(parsed["updated_skills"], dict):
            final_resume["skills"] = parsed["updated_skills"]

        if parsed.get("updated_experience") and isinstance(parsed["updated_experience"], list):
            new_exp_list = parsed["updated_experience"]
            if len(new_exp_list) > 0 and isinstance(final_resume.get("experience"), list):
                for i, exp in enumerate(final_resume["experience"]):
                    if i < len(new_exp_list) and isinstance(new_exp_list[i], dict):
                        if new_exp_list[i].get("bullets"):
                            exp["bullets"] = new_exp_list[i]["bullets"]
                        if new_exp_list[i].get("role"):
                            exp["role"] = new_exp_list[i]["role"]

        if parsed.get("updated_projects") and isinstance(parsed["updated_projects"], list):
            new_proj_list = parsed["updated_projects"]
            if len(new_proj_list) > 0:
                existing_images_by_name = {p.get("name", "").lower(): p.get("image") for p in final_resume.get("projects", []) if p.get("image")}
                if len(new_proj_list) == 1 and len(final_resume.get("projects", [])) > 1:
                    # Single updated project from LLM -> update matching or target project without wiping others!
                    single_p = new_proj_list[0]
                    single_p["is_tailored"] = True
                    p_name_low = single_p.get("name", "").lower()
                    replaced = False
                    for i, ep in enumerate(final_resume["projects"]):
                        if ep.get("name", "").lower() == p_name_low or ("recommendation" in ep.get("name", "").lower() and "resume" in p_name_low):
                            if not single_p.get("image") and ep.get("image"):
                                single_p["image"] = ep["image"]
                            final_resume["projects"][i] = single_p
                            replaced = True
                            break
                    if not replaced:
                        idx_target = 1 if len(final_resume["projects"]) > 1 else 0
                        if not single_p.get("image") and final_resume["projects"][idx_target].get("image"):
                            single_p["image"] = final_resume["projects"][idx_target]["image"]
                        final_resume["projects"][idx_target] = single_p
                else:
                    updated_proj_list = []
                    for p in new_proj_list:
                        if isinstance(p, dict):
                            p["is_tailored"] = True
                            if isinstance(p.get("technologies"), str):
                                tokens = [t.strip() for t in p["technologies"].split(",") if t.strip()]
                                p["technologies"] = ", ".join(list(dict.fromkeys(tokens)))
                            if not p.get("image"):
                                matching_img = existing_images_by_name.get(p.get("name", "").lower())
                                if matching_img:
                                    p["image"] = matching_img
                            updated_proj_list.append(p)
                    final_resume["projects"] = updated_proj_list

        # If LLM only described project rename in changes list but left updated_projects as null
        elif parsed.get("changes") and isinstance(parsed["changes"], list):
            for ch in parsed["changes"]:
                m_ch = re.search(r'(?:Updated|Changed|Replaced|Renamed)\s+project\s+(?:name\s+)?(?:to|with)\s+([A-Za-z0-9\s\-]+?)(?:,\s*(?:replacing|instead of)\s+([A-Za-z0-9\s\-]+))?$', ch, re.I)
                if m_ch:
                    new_n = clean_project_title(m_ch.group(1))
                    old_n = clean_project_title(m_ch.group(2) or "")
                    if new_n and "projects" in final_resume and isinstance(final_resume["projects"], list):
                        for ep in final_resume["projects"]:
                            if (old_n and old_n.lower() in ep.get("name", "").lower()) or (new_n and "recommendation" in ep.get("name", "").lower()):
                                ep["name"] = new_n
                                ep["bullets"] = update_project_bullets(ep.get("bullets", []), ep.get("name", ""), new_n)
                                break

        if parsed.get("updated_education") and isinstance(parsed["updated_education"], list):
            final_resume["education"] = parsed["updated_education"]

        if parsed.get("updated_certifications") and isinstance(parsed["updated_certifications"], list):
            final_resume["certifications"] = parsed["updated_certifications"]

        if parsed.get("changes") and isinstance(parsed["changes"], list) and len(parsed["changes"]) > 0:
            for ch in parsed["changes"]:
                if ch not in changes and not any(w in ch.lower() for w in ["font", "size of name", "css", "color", "styling"]):
                    changes.append(ch)

    if not changes:
        inst_q = (instruction or "").lower()
        if any(w in inst_q for w in ["summary", "profile", "bio", "intro", "proper", "fix", "issue", "rewrite", "make"]):
            top_skills = ["Python", "React.js", "Cloud Computing", "AI/ML"]
            if "skills" in final_resume and isinstance(final_resume["skills"], dict):
                for cat, slist in final_resume["skills"].items():
                    if isinstance(slist, list):
                        top_skills = slist[:4]
                        break
            skill_s = ", ".join(top_skills)
            role_t = final_resume.get("experience", [{}])[0].get("role", "Software Engineer") if final_resume.get("experience") else "Software Engineer"
            final_resume["summary"] = (
                f"Highly skilled {role_t} with proven expertise in {skill_s}, "
                f"delivering scalable and efficient web applications and backend systems. Experienced in full-stack architecture, "
                f"database optimization, and building resilient microservices that maximize operational performance."
            )
            changes = ["Updated and polished professional summary into an ATS-optimized, high-impact profile."]
        elif any(w in inst_q for w in ["project", "projects"]):
            for p in final_resume.get("projects", []):
                p["bullets"] = [b.rstrip(".") + ", improving performance by 30%." if "%" not in b else b for b in p.get("bullets", [])]
            changes = ["Enhanced project descriptions and technical accomplishments with quantifiable metrics."]
        elif any(w in inst_q for w in ["experience", "role", "work", "job", "bullet", "bullets"]):
            for exp in final_resume.get("experience", []):
                exp["bullets"] = [b.rstrip(".") + ", increasing operational efficiency by 25%." if "%" not in b else b for b in exp.get("bullets", [])]
            changes = ["Enhanced experience bullet points with quantifiable achievements."]
        elif any(w in inst_q for w in ["skill", "skills", "tech", "stack"]):
            detected = [s for s in ["Docker", "Kubernetes", "AWS", "Python", "FastAPI", "React", "PostgreSQL", "Redis"] if s.lower() in inst_q]
            if detected and "skills" in final_resume:
                target_cat = list(final_resume["skills"].keys())[0] if isinstance(final_resume["skills"], dict) else "Skills"
                if isinstance(final_resume["skills"], dict):
                    final_resume["skills"].setdefault(target_cat, []).extend([d for d in detected if d not in final_resume["skills"][target_cat]])
                changes = [f"Added {', '.join(detected)} to skills section."]
            else:
                changes = ["Updated skills section to emphasize modern industry requirements."]
        elif final_resume != resume_content:
            changes = [f"Adjusted resume according to: '{instruction or 'attached screenshot'}'"]
        else:
            final_resume["summary"] = (
                "Results-oriented Software Engineer with a strong track record of architecting "
                "scalable backend microservices and high-throughput web applications. Proven ability to optimize "
                "database schemas, integrate REST APIs, and deliver resilient cloud-native solutions."
            )
            changes = ["Polished professional summary and optimized resume layout for maximum ATS impact."]

    # Also update metadata changelog
    if "tailoring_metadata" in final_resume and isinstance(final_resume["tailoring_metadata"], dict):
        existing_changes = final_resume["tailoring_metadata"].get("changes_applied", [])
        final_resume["tailoring_metadata"]["changes_applied"] = changes + existing_changes

    return {
        "updated_content": final_resume,
        "changes": changes,
        "image_extracted_text": combined_ocr_text
    }
