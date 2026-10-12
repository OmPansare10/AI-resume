import json
import re
import requests
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """
    Clean unnecessary spaces and blank lines.
    """
    lines = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            lines.append(line)
    return "\n".join(lines)


def extract_jd_from_text(jd_text: str) -> str:
    """
    Process pasted Job Description text.
    """
    if not jd_text or not jd_text.strip():
        raise ValueError("Job Description text is empty.")
    return clean_text(jd_text)


def extract_json_ld_job_posting(soup: BeautifulSoup) -> str:
    """
    Attempt to extract schema.org JobPosting data from JSON-LD scripts.
    Many job portals (Google Jobs, LinkedIn public, Indeed, Greenhouse, Lever, etc.)
    embed the full job details in JSON-LD for SEO.
    """
    for script in soup.find_all("script", type=re.compile(r"ld\+json", re.I)):
        try:
            if not script.string:
                continue
            data = json.loads(script.string.strip())
            
            # Handle list or single dict
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") in ["JobPosting", "jobPosting"]:
                    title = item.get("title", "")
                    description = item.get("description", "")
                    skills = item.get("skills", "")
                    org = item.get("hiringOrganization", {}).get("name", "") if isinstance(item.get("hiringOrganization"), dict) else ""
                    
                    # Convert HTML description to clean text
                    desc_soup = BeautifulSoup(description, "html.parser")
                    clean_desc = desc_soup.get_text(separator="\n").strip()
                    
                    parts = []
                    if title:
                        parts.append(f"Job Title: {title}")
                    if org:
                        parts.append(f"Company: {org}")
                    if skills:
                        parts.append(f"Skills: {skills}")
                    if clean_desc:
                        parts.append(f"Job Description:\n{clean_desc}")
                    
                    if len("\n\n".join(parts)) > 80:
                        return clean_text("\n\n".join(parts))
        except Exception:
            continue
    return ""


def extract_jd_from_link(jd_link: str) -> str:
    """
    Extract visible text from a public Job Description webpage.
    Supports standard web pages, career portals, and JSON-LD JobPosting schema.
    """
    if not jd_link or not jd_link.strip():
        raise ValueError("Job Description link is empty.")

    clean_url = jd_link.strip()
    if not (clean_url.startswith("http://") or clean_url.startswith("https://")):
        clean_url = "https://" + clean_url

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        response = requests.get(
            clean_url,
            headers=headers,
            timeout=15,
            allow_redirects=True
        )
    except requests.exceptions.RequestException as e:
        raise ValueError(f"Could not connect to URL: {str(e)}")

    if response.status_code == 403 or response.status_code == 401:
        raise ValueError(
            "This job portal (e.g. Naukri/LinkedIn) protects job postings behind anti-scraping walls (403 Forbidden). "
            "Please copy the Job Description text directly from your browser and paste it into the 'Paste JD' tab."
        )

    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # 1. First check if bot-block / access denied is in the response text
    lower_text = response.text.lower()
    if "access denied" in lower_text and ("edgesuite" in lower_text or "akamai" in lower_text or "reference #" in lower_text):
        raise ValueError(
            "This job portal uses Akamai/Cloudflare bot protection that blocks automated requests. "
            "Please copy the job text directly from your open browser tab and paste it into 'Paste JD'."
        )

    if "javascript is disabled" in lower_text and len(lower_text) < 45000:
        # Check if there is schema data before failing
        json_ld_result = extract_json_ld_job_posting(soup)
        if json_ld_result and len(json_ld_result) > 100:
            return json_ld_result

        raise ValueError(
            "This job portal renders job details only via client-side JavaScript. "
            "Please copy the job description text from the page and paste it into 'Paste JD'."
        )

    # 2. Try JSON-LD schema extraction (Google Jobs / SEO schema)
    json_ld_text = extract_json_ld_job_posting(soup)
    if json_ld_text and len(json_ld_text) > 150:
        return json_ld_text

    # 3. Clean page elements
    for element in soup(["script", "style", "noscript", "header", "footer", "nav", "svg", "iframe", "form"]):
        element.decompose()

    # 4. Check for dedicated job content containers
    candidate_selectors = [
        '[class*="job-description"]',
        '[class*="jobDescription"]',
        '[id*="job-description"]',
        '[id*="jobDescription"]',
        '[class*="description"]',
        '[class*="job_description"]',
        'article',
        'main'
    ]
    for selector in candidate_selectors:
        container = soup.select_one(selector)
        if container:
            text = container.get_text(separator="\n")
            cleaned = clean_text(text)
            if len(cleaned) > 200:
                return cleaned

    # 5. Fallback to full page text
    text = soup.get_text(separator="\n")
    cleaned = clean_text(text)

    # 6. Check meta description if main body is too short
    if len(cleaned) < 150:
        meta_desc = ""
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            meta_desc = og_desc["content"].strip()
        else:
            meta_tag = soup.find("meta", attrs={"name": "description"})
            if meta_tag and meta_tag.get("content"):
                meta_desc = meta_tag["content"].strip()

        if meta_desc and len(meta_desc) > 80:
            return clean_text(meta_desc)

    if not cleaned or len(cleaned) < 50:
        raise ValueError(
            "Could not extract sufficient text from this job page. "
            "Please copy the Job Description text directly from the webpage and use the 'Paste JD' tab."
        )

    return cleaned
