import base64
import html as html_lib
import io
import os
import re
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor
import pymupdf as fitz

# Root directories
BACKEND_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BACKEND_DIR.parent / "generated_resumes"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)

from services.fresher_resume_service import format_education_entry, sanitize_bullet_text  # noqa: E402


WINDOWS_FONTS_DIR = r"C:\Windows\Fonts"

FONT_FAMILY_MAP: Dict[str, Tuple[str, str, str, str, str]] = {
    # key -> (docx_body_font, reg_ttf, bold_ttf, italic_ttf, bold_italic_ttf)
    "arial": ("Arial", "arial.ttf", "arialbd.ttf", "ariali.ttf", "arialbi.ttf"),
    "calibri": ("Calibri", "calibri.ttf", "calibrib.ttf", "calibrii.ttf", "calibriz.ttf"),
    "segoe ui": ("Segoe UI", "segoeui.ttf", "segoeuib.ttf", "segoeuii.ttf", "segoeuiz.ttf"),
    "georgia": ("Georgia", "georgia.ttf", "georgiab.ttf", "georgiai.ttf", "georgiaz.ttf"),
    "times new roman": ("Times New Roman", "times.ttf", "timesbd.ttf", "timesi.ttf", "timesbi.ttf"),
}


def set_cell_margins(cell, top=50, bottom=50, left=50, right=50):
    """Set inner margins for a table cell in twentieths of a point (dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement("w:tcMar")
    for m, val in [("top", top), ("bottom", bottom), ("left", left), ("right", right)]:
        node = OxmlElement(f"w:{m}")
        node.set(qn("w:w"), str(val))
        node.set(qn("w:type"), "dxa")
        tcMar.append(node)
    tcPr.append(tcMar)


def add_horizontal_rule(paragraph, color_hex="2563EB", size=8, space="2"):
    """Add a clean bottom border rule under a Word paragraph."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = parse_xml(
        f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="{size}" w:space="{space}" w:color="{color_hex}"/></w:pBdr>'
    )
    pPr.append(pBdr)


def _remove_table_borders(table) -> None:
    """Remove all visible borders from a Word layout table."""
    tblPr = table._tbl.tblPr
    borders = parse_xml(
        f'<w:tblBorders {nsdecls("w")}>'
        '<w:top w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:left w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:bottom w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:right w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:insideH w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        '<w:insideV w:val="none" w:sz="0" w:space="0" w:color="auto"/>'
        "</w:tblBorders>"
    )
    tblPr.append(borders)


def _add_hyperlink_run(
    paragraph,
    url: str,
    text: str,
    font_name: str = "Arial",
    font_size: float = 8.5,
    color_hex: str = "1D4ED8",
    bold: bool = True,
) -> None:
    """Append a clickable blue hyperlink run inside a Word paragraph."""
    part = paragraph.part
    r_id = part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), r_id)

    run = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    rFonts = OxmlElement("w:rFonts")
    rFonts.set(qn("w:ascii"), font_name)
    rFonts.set(qn("w:hAnsi"), font_name)
    rPr.append(rFonts)

    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), str(int(round(font_size * 2))))
    rPr.append(sz)
    szCs = OxmlElement("w:szCs")
    szCs.set(qn("w:val"), str(int(round(font_size * 2))))
    rPr.append(szCs)

    if bold:
        rPr.append(OxmlElement("w:b"))

    col = OxmlElement("w:color")
    col.set(qn("w:val"), color_hex)
    rPr.append(col)

    run.append(rPr)
    t_el = OxmlElement("w:t")
    t_el.text = text
    run.append(t_el)
    hyperlink.append(run)
    paragraph._p.append(hyperlink)


def _resolve_font_spec(font_family_pref: str = "") -> Tuple[str, str, str, str, str]:
    """Map UI font preference string to DOCX font name + Windows TTF filenames."""
    low = (font_family_pref or "").lower()
    for key, spec in FONT_FAMILY_MAP.items():
        if key in low:
            return spec
    return FONT_FAMILY_MAP["arial"]


def _decode_b64_image(raw: Any) -> Optional[bytes]:
    """Safely decode a base64 / data-URI image string into raw bytes."""
    if not raw or not isinstance(raw, str) or len(raw.strip()) < 30:
        return None
    try:
        payload = raw.split(",", 1)[1] if "," in raw else raw
        return base64.b64decode(payload)
    except Exception:
        return None


def _normalize_url(raw: str) -> Optional[str]:
    """Return a clean https:// URL if the string looks like a web URL/profile path."""
    s = (raw or "").strip()
    if not s or ("." not in s and "/" not in s and not s.lower().startswith("http")):
        return None
    if re.match(r"^https?://", s, re.I):
        return s
    return f"https://{s.lstrip('/')}"


def _build_contact_entries(contact_raw: Any) -> Tuple[List[Dict[str, Optional[str]]], List[Tuple[str, str]]]:
    """Normalize contact fields into display entries and PDF hyperlink targets."""
    contact = contact_raw if isinstance(contact_raw, dict) else {}
    entries: List[Dict[str, Optional[str]]] = []
    link_targets: List[Tuple[str, str]] = []

    if contact.get("email"):
        entries.append({"text": str(contact["email"]).strip(), "url": None, "kind": "plain"})
    if contact.get("phone"):
        entries.append({"text": str(contact["phone"]).strip(), "url": None, "kind": "plain"})
    if contact.get("location"):
        entries.append({"text": str(contact["location"]).strip(), "url": None, "kind": "plain"})

    linkedin_val = str(contact.get("linkedin") or "").strip()
    if linkedin_val:
        url = _normalize_url(linkedin_val) or "https://www.linkedin.com"
        entries.append({"text": "LinkedIn", "url": url, "kind": "link"})
        link_targets.append(("LinkedIn", url))

    github_val = str(contact.get("github") or "").strip()
    if github_val:
        url = _normalize_url(github_val) or "https://github.com"
        entries.append({"text": "GitHub", "url": url, "kind": "link"})
        link_targets.append(("GitHub", url))

    return entries, link_targets


def _collect_skill_rows(skills: Any) -> List[Tuple[str, str]]:
    """Extract normalized (UPPERCASE CATEGORY, comma-separated values) rows matching preview."""
    rows: List[Tuple[str, str]] = []
    if isinstance(skills, dict):
        for cat, slist in skills.items():
            if cat == "missing_from_resume" or not slist:
                continue
            label = "TARGETED EXPERTISE" if cat == "matching_with_jd" else cat.replace("_", " ").upper()
            val_str = ", ".join(str(s) for s in slist) if isinstance(slist, list) else str(slist)
            if val_str.strip():
                rows.append((label, val_str.strip()))
    elif isinstance(skills, list) and skills:
        rows.append(("TECHNICAL COMPETENCIES", ", ".join(str(s) for s in skills if str(s).strip())))
    return rows


def _build_pdf_archive(
    extra_images: Optional[List[Tuple[bytes, str]]] = None,
) -> Tuple[Optional[fitz.Archive], str]:
    """
    Create an in-memory PyMuPDF Archive containing TrueType fonts (Lucida Sans &
    Lucida Bright on Windows, which map ASCII spaces, hyphens, 'fi'/'fl' ligatures,
    and Unicode bullets/en-dashes/em-dashes without U+00A0 or U+FB01 artifacts)
    plus any embedded candidate/project images.
    """
    font_face_css = ""
    archive: Optional[fitz.Archive] = None

    lsans_files = ("LSANS.TTF", "LSANSD.TTF", "LSANSI.TTF", "LSANSDI.TTF")
    lbrite_files = ("LBRITE.TTF", "LBRITED.TTF", "LBRITEI.TTF", "LBRITEDI.TTF")
    has_lucide = os.path.isdir(WINDOWS_FONTS_DIR) and all(
        os.path.exists(os.path.join(WINDOWS_FONTS_DIR, fn))
        for fn in (*lsans_files, *lbrite_files)
    )
    if has_lucide:
        archive = fitz.Archive()
        archive.add(WINDOWS_FONTS_DIR)
        font_face_css = """
@font-face { font-family: 'ResumeSans'; font-weight: normal; font-style: normal; src: url(LSANS.TTF); }
@font-face { font-family: 'ResumeSans'; font-weight: bold;   font-style: normal; src: url(LSANSD.TTF); }
@font-face { font-family: 'ResumeSans'; font-weight: normal; font-style: italic; src: url(LSANSI.TTF); }
@font-face { font-family: 'ResumeSans'; font-weight: bold;   font-style: italic; src: url(LSANSDI.TTF); }
@font-face { font-family: 'ResumeSerif'; font-weight: normal; font-style: normal; src: url(LBRITE.TTF); }
@font-face { font-family: 'ResumeSerif'; font-weight: bold;   font-style: normal; src: url(LBRITED.TTF); }
@font-face { font-family: 'ResumeSerif'; font-weight: normal; font-style: italic; src: url(LBRITEI.TTF); }
@font-face { font-family: 'ResumeSerif'; font-weight: bold;   font-style: italic; src: url(LBRITEDI.TTF); }
"""

    if extra_images:
        if archive is None:
            archive = fitz.Archive()
        archive.add(extra_images)

    return archive, font_face_css


def build_resume_html_and_css(
    resume_data: Dict[str, Any],
    single_page: bool = False,
) -> Tuple[str, str, List[Tuple[str, str]], Optional[fitz.Archive]]:
    """
    Construct semantic HTML + CSS matching the web preview's exact typography,
    royal blue accent rules, inline Role | Company + right-aligned Duration headers,
    2-line Education formatting, and project Tech styling.
    """
    font_pref = str(resume_data.get("font_family") or "").lower()
    skill_rows = _collect_skill_rows(resume_data.get("skills"))
    exp_list = [e for e in (resume_data.get("experience") or []) if isinstance(e, dict)]
    intern_list = [i for i in (resume_data.get("internships") or []) if isinstance(i, dict)]
    proj_list = [p for p in (resume_data.get("projects") or []) if isinstance(p, dict)]
    edu_list = [e for e in (resume_data.get("education") or []) if isinstance(e, dict)]
    cert_list = [str(c).strip() for c in (resume_data.get("certifications") or []) if str(c).strip()]

    # Adaptive starting font/spacing for single-page mode so both sparse and dense resumes fit harmoniously
    is_short_single = (
        single_page
        and len(exp_list) <= 1
        and len(proj_list) <= 1
        and len(skill_rows) <= 7
    )
    if single_page:
        if is_short_single:
            body_pt, name_pt, sec_pt, hdr_gap, item_gap, b_gap, l_height = 10.0, 19.5, 10.5, 11, 7, 2.5, 1.38
        else:
            body_pt, name_pt, sec_pt, hdr_gap, item_gap, b_gap, l_height = 8.1, 17.5, 9.2, 6.2, 3.6, 1.0, 1.25
    else:
        body_pt, name_pt, sec_pt, hdr_gap, item_gap, b_gap, l_height = 9.0, 19.0, 10.0, 8.5, 5.0, 1.5, 1.32

    extra_images: List[Tuple[bytes, str]] = []
    photo_bytes = _decode_b64_image(resume_data.get("photo") or resume_data.get("photo_base64"))
    if photo_bytes:
        extra_images.append((photo_bytes, "candidate_photo.img"))

    for idx, proj in enumerate(proj_list):
        p_bytes = _decode_b64_image(proj.get("image") or proj.get("photo"))
        if p_bytes:
            extra_images.append((p_bytes, f"proj_{idx}.img"))

    archive, font_face_css = _build_pdf_archive(extra_images)
    has_embed = bool(font_face_css)
    body_css_family = (
        "'ResumeSerif', serif"
        if ("times" in font_pref or "georgia" in font_pref)
        else "'ResumeSans', sans-serif"
    ) if has_embed else ("serif" if ("times" in font_pref or "georgia" in font_pref) else "sans-serif")
    name_css_family = "'ResumeSerif', serif" if has_embed else "serif"

    css = f"""{font_face_css}
* {{
    hyphens: none;
    -webkit-hyphens: none;
}}
body {{
    font-family: {body_css_family};
    font-size: {body_pt}pt;
    color: #334155;
    line-height: {l_height};
    margin: 0;
    padding: 0;
    hyphens: none;
}}
.hdr {{
    text-align: center;
    border-bottom: 0.75pt solid #cbd5e1;
    padding-bottom: 4.5pt;
    margin-bottom: 5pt;
}}
table.hdr-photo-tbl {{
    width: 100%;
    border-collapse: collapse;
    border-bottom: 0.75pt solid #cbd5e1;
    margin-bottom: 5pt;
}}
table.hdr-photo-tbl td {{ padding: 0 0 4.5pt 0; vertical-align: middle; }}
.name {{
    font-family: {name_css_family};
    font-size: {name_pt}pt;
    font-weight: bold;
    color: #000000;
    letter-spacing: 0.9pt;
    margin: 0 0 2pt 0;
}}
.contact {{
    font-size: {max(7.6, body_pt - 0.5)}pt;
    color: #475569;
    margin: 0;
}}
.contact-link {{
    color: #1d4ed8;
    font-weight: bold;
    text-decoration: none;
}}
.sep {{
    color: #94a3b8;
    margin: 0 4pt;
}}
.sec-title {{
    font-size: {sec_pt}pt;
    font-weight: bold;
    color: #1e3a8a;
    border-bottom: 1pt solid #2563eb;
    margin: {hdr_gap}pt 0 3.2pt 0;
    padding-bottom: 1.5pt;
    text-transform: uppercase;
    letter-spacing: 0.55pt;
    break-after: avoid;
    page-break-after: avoid;
}}
.summary {{
    text-align: justify;
    margin: 0 0 {item_gap}pt 0;
}}
.skill-row {{
    margin: 0 0 {max(1.4, b_gap + 0.5)}pt 0;
    font-size: {max(7.8, body_pt - 0.2)}pt;
}}
.skill-lbl {{
    font-weight: bold;
    color: #0f172a;
}}
.exp-item, .proj-item, .edu-item {{
    break-inside: avoid;
    page-break-inside: avoid;
    margin-bottom: {item_gap}pt;
}}
table.row-hdr {{
    width: 100%;
    border-collapse: collapse;
    margin: 2pt 0 1.2pt 0;
    break-inside: avoid;
    page-break-inside: avoid;
    break-after: avoid;
    page-break-after: avoid;
}}
table.row-hdr td {{
    padding: 0;
    vertical-align: baseline;
}}
td.left {{ text-align: left; }}
td.right {{ text-align: right; white-space: nowrap; }}
.exp-role {{
    font-weight: bold;
    color: #0f172a;
    font-size: {body_pt + 0.4}pt;
}}
.exp-pipe {{
    color: #94a3b8;
    font-weight: normal;
}}
.exp-comp {{
    font-weight: bold;
    color: #1e3a8a;
    font-size: {body_pt + 0.4}pt;
}}
.exp-loc {{
    color: #64748b;
    font-size: {max(7.6, body_pt - 0.4)}pt;
}}
.exp-dur {{
    font-style: italic;
    font-weight: bold;
    color: #64748b;
    font-size: {max(7.6, body_pt - 0.4)}pt;
}}
.proj-name {{
    font-weight: bold;
    color: #0f172a;
    font-size: {body_pt + 0.4}pt;
}}
.proj-tech {{
    font-style: italic;
    font-weight: bold;
    color: #1e3a8a;
    font-size: {max(7.8, body_pt - 0.1)}pt;
}}
ul.bullets {{
    margin: 0 0 1pt 0;
    padding-left: 13pt;
}}
ul.bullets li {{
    margin: 0 0 {b_gap}pt 0;
}}
.edu-inst {{
    font-weight: bold;
    color: #0f172a;
    font-size: {body_pt + 0.2}pt;
}}
.edu-yr {{
    font-weight: bold;
    color: #0f172a;
    font-size: {body_pt}pt;
}}
.edu-deg {{
    font-style: italic;
    color: #334155;
    font-size: {max(7.8, body_pt - 0.1)}pt;
    margin: 0.5pt 0 0 0;
}}
.proj-img-wrap {{
    margin: 2pt 0 2pt 13pt;
}}
"""

    esc = html_lib.escape
    parts: List[str] = []

    # 1. Header (Name + Contact + Optional Photo)
    name = esc((resume_data.get("name") or "Candidate Name").strip().upper())
    contact_entries, link_targets = _build_contact_entries(resume_data.get("contact"))
    contact_html_items: List[str] = []
    for entry in contact_entries:
        txt = esc(entry["text"] or "")
        if entry["kind"] == "link" and entry["url"]:
            contact_html_items.append(
                f'<a class="contact-link" href="{esc(entry["url"])}">{txt}</a>'
            )
        else:
            contact_html_items.append(txt)
    contact_bar_html = '<span class="sep"> | </span>'.join(contact_html_items)

    if photo_bytes:
        parts.append(
            f'<table class="hdr-photo-tbl"><tr>'
            f'<td style="width: 62pt;"><img src="candidate_photo.img" width="54" height="54" /></td>'
            f'<td><div class="name" style="text-align:left;">{name}</div>'
            f'<div class="contact" style="text-align:left;">{contact_bar_html}</div></td>'
            f"</tr></table>"
        )
    else:
        parts.append(
            f'<div class="hdr"><div class="name">{name}</div>'
            f'<div class="contact">{contact_bar_html}</div></div>'
        )

    # 2. Summary
    summary = str(resume_data.get("summary") or resume_data.get("resume_summary") or "").strip()
    if summary:
        parts.append('<div class="sec-title">SUMMARY</div>')
        parts.append(f'<div class="summary">{esc(summary)}</div>')

    # 3. Core Skills & Technologies
    if skill_rows:
        parts.append('<div class="sec-title">CORE SKILLS &amp; TECHNOLOGIES</div>')
        for label, val_str in skill_rows:
            parts.append(
                f'<div class="skill-row"><span class="skill-lbl">{esc(label)}:</span> {esc(val_str)}</div>'
            )

    # 4. Experience
    if exp_list:
        parts.append('<div class="sec-title">EXPERIENCE</div>')
        for job in exp_list:
            role = esc(str(job.get("role") or job.get("title") or "Software Engineer").strip())
            comp = esc(str(job.get("company") or "").strip())
            dur = esc(str(job.get("duration") or job.get("dates") or "").strip())
            loc = esc(str(job.get("location") or "").strip())

            title_html = f'<span class="exp-role">{role}</span>'
            if comp:
                title_html += f'<span class="exp-pipe"> | </span><span class="exp-comp">{comp}</span>'
            if loc:
                title_html += f'<span class="exp-loc"> &bull; {loc}</span>'

            bullets = [sanitize_bullet_text(b) for b in (job.get("bullets") or []) if sanitize_bullet_text(b)]
            if single_page:
                bullets = bullets[:3]
            bullets_html = "".join(f"<li>{esc(b)}</li>" for b in bullets)
            ul_block = f'<ul class="bullets">{bullets_html}</ul>' if bullets_html else ""

            parts.append(
                f'<div class="exp-item">'
                f'<table class="row-hdr"><tr><td class="left">{title_html}</td>'
                f'<td class="right"><span class="exp-dur">{dur}</span></td></tr></table>'
                f"{ul_block}</div>"
            )

    # 5. Internships (if passed separately)
    if intern_list:
        parts.append('<div class="sec-title">INTERNSHIP EXPERIENCE</div>')
        for intern in intern_list:
            role = esc(str(intern.get("role") or "Intern").strip())
            comp = esc(str(intern.get("company") or "").strip())
            dur = esc(str(intern.get("duration") or "").strip())
            title_html = f'<span class="exp-role">{role}</span>'
            if comp:
                title_html += f'<span class="exp-pipe"> | </span><span class="exp-comp">{comp}</span>'
            bullets = [sanitize_bullet_text(b) for b in (intern.get("bullets") or []) if sanitize_bullet_text(b)]
            bullets_html = "".join(f"<li>{esc(b)}</li>" for b in bullets)
            ul_block = f'<ul class="bullets">{bullets_html}</ul>' if bullets_html else ""
            parts.append(
                f'<div class="exp-item">'
                f'<table class="row-hdr"><tr><td class="left">{title_html}</td>'
                f'<td class="right"><span class="exp-dur">{dur}</span></td></tr></table>'
                f"{ul_block}</div>"
            )

    # 6. Key Projects
    if proj_list:
        parts.append('<div class="sec-title">KEY PROJECTS</div>')
        for idx, proj in enumerate(proj_list):
            pname = esc(str(proj.get("name") or proj.get("title") or "Project").strip())
            tech = esc(str(proj.get("technologies") or proj.get("tools") or "").strip())
            pmeta = esc(str(proj.get("duration") or proj.get("link") or "").strip())

            left_html = f'<span class="proj-name">{pname}</span>'
            if tech:
                left_html += f' <span class="proj-tech">({tech})</span>'
            if pmeta:
                hdr_html = (
                    f'<table class="row-hdr"><tr><td class="left">{left_html}</td>'
                    f'<td class="right"><span class="exp-dur">{pmeta}</span></td></tr></table>'
                )
            else:
                hdr_html = f'<div style="margin: 2pt 0 1.2pt 0;">{left_html}</div>'

            bullets = [sanitize_bullet_text(b) for b in (proj.get("bullets") or []) if sanitize_bullet_text(b)]
            if single_page:
                bullets = bullets[:3]
            bullets_html = "".join(f"<li>{esc(b)}</li>" for b in bullets)
            ul_block = f'<ul class="bullets">{bullets_html}</ul>' if bullets_html else ""

            img_html = ""
            if _decode_b64_image(proj.get("image") or proj.get("photo")):
                img_html = f'<div class="proj-img-wrap"><img src="proj_{idx}.img" width="160" /></div>'

            parts.append(f'<div class="proj-item">{hdr_html}{ul_block}{img_html}</div>')

    # 7. Education
    if edu_list:
        parts.append('<div class="sec-title">EDUCATION</div>')
        for edu in edu_list:
            edu_fmt = format_education_entry(edu)
            inst_esc = esc(edu_fmt["inst_line"])
            year_esc = esc(edu_fmt["year"])
            deg_esc = esc(edu_fmt["degree_line"])
            parts.append(
                f'<div class="edu-item">'
                f'<table class="row-hdr"><tr><td class="left"><span class="edu-inst">{inst_esc}</span></td>'
                f'<td class="right"><span class="edu-yr">{year_esc}</span></td></tr>'
                f'<tr><td colspan="2"><div class="edu-deg">{deg_esc}</div></td></tr>'
                f'</table></div>'
            )

    # 8. Certifications
    if cert_list:
        parts.append('<div class="sec-title">CERTIFICATIONS</div>')
        c_items = "".join(f"<li>{esc(c)}</li>" for c in cert_list)
        parts.append(f'<ul class="bullets">{c_items}</ul>')

    html_body = "".join(parts)
    return html_body, css, link_targets, archive


def _attach_pdf_contact_links(page: fitz.Page, link_targets: List[Tuple[str, str]]) -> None:
    """Attach clickable URI annotations to LinkedIn / GitHub labels in rendered PDF."""
    for label_txt, uri in link_targets:
        try:
            for rect in page.search_for(label_txt):
                if rect.y0 < 140.0:
                    page.insert_link({"kind": fitz.LINK_URI, "from": rect, "uri": uri})
        except Exception:
            pass


def render_pdf_from_resume_data(resume_data: Dict[str, Any], single_page: bool = False) -> Path:
    """
    Render the resume into an A4 PDF matching the web preview's visual typography,
    colors, Unicode symbols, single-line Experience/Project headers, and 2-line Education.
    """
    html_body, css, link_targets, archive = build_resume_html_and_css(
        resume_data, single_page=single_page
    )

    page_w, page_h = 595.0, 842.0

    if single_page:
        pdf_doc = fitz.open()
        page = pdf_doc.new_page(width=page_w, height=page_h)
        target_rect = fitz.Rect(28.0, 22.0, page_w - 28.0, page_h - 22.0)
        page.insert_htmlbox(target_rect, html_body, css=css, archive=archive, scale_low=0.45)
        if len(pdf_doc) > 1:
            while len(pdf_doc) > 1:
                pdf_doc.delete_page(len(pdf_doc) - 1)
        _attach_pdf_contact_links(pdf_doc[0], link_targets)
    else:
        story = fitz.Story(html=html_body, user_css=css, archive=archive)
        mediabox = fitz.Rect(0, 0, page_w, page_h)
        content_rect = fitz.Rect(38.0, 32.0, page_w - 38.0, page_h - 32.0)
        bio = io.BytesIO()
        writer = fitz.DocumentWriter(bio)
        while True:
            dev = writer.begin_page(mediabox)
            more, _ = story.place(content_rect)
            story.draw(dev, None)
            writer.end_page()
            if not more:
                break
        writer.close()
        pdf_doc = fitz.open(stream=bio.getvalue(), filetype="pdf")
        if len(pdf_doc) > 0:
            _attach_pdf_contact_links(pdf_doc[0], link_targets)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:6]
    default_name = "Fresher_Resume" if single_page else "Tailored_Resume"
    clean_candidate = re.sub(r"[^a-zA-Z0-9_-]", "_", resume_data.get("name", default_name)).strip("_") or "Resume"
    tag = "_SinglePage_Fresher" if single_page else ""
    filename = f"{clean_candidate}{tag}_{timestamp}_{unique_suffix}.pdf"
    output_path = GENERATED_DIR / filename
    pdf_doc.save(str(output_path))
    pdf_doc.close()

    return output_path


def render_docx_from_resume_data(resume_data: Dict[str, Any], single_page: bool = False) -> Path:
    """
    Render the resume into a clean A4 Microsoft Word document (.docx) matching
    the web preview's exact structure, fonts, colors, single-line Experience headers,
    italic Project tech stacks, 2-line Education, and clickable contact links.
    """
    doc = docx.Document()
    body_font, _, _, _, _ = _resolve_font_spec(str(resume_data.get("font_family") or ""))

    # Explicitly configure A4 dimensions (8.27 x 11.69 in) matching preview & PDF proportions
    margin_y = 0.38 if single_page else 0.52
    margin_x = 0.45 if single_page else 0.58
    printable_w = 8.27 - (2.0 * margin_x)
    for section in doc.sections:
        section.page_width = Inches(8.27)
        section.page_height = Inches(11.69)
        section.top_margin = Inches(margin_y)
        section.bottom_margin = Inches(margin_y)
        section.left_margin = Inches(margin_x)
        section.right_margin = Inches(margin_x)

    COLOR_BLACK = RGBColor(0, 0, 0)
    COLOR_PRIMARY = RGBColor(15, 23, 42)     # #0f172a
    COLOR_NAVY = RGBColor(30, 58, 138)       # #1e3a8a
    COLOR_BODY = RGBColor(51, 65, 85)        # #334155
    COLOR_MUTED = RGBColor(100, 116, 139)    # #64748b
    COLOR_PIPE = RGBColor(148, 163, 184)     # #94a3b8

    exp_count = len([e for e in (resume_data.get("experience") or []) if isinstance(e, dict)])
    proj_count = len([p for p in (resume_data.get("projects") or []) if isinstance(p, dict)])
    skill_rows = _collect_skill_rows(resume_data.get("skills"))

    if single_page:
        dense = (exp_count >= 3 or len(skill_rows) >= 9 or proj_count >= 3)
        name_pt = 17.5 if dense else 19.0
        sec_pt = 9.0 if dense else 10.0
        body_pt = 7.8 if dense else 8.6
        hdr_pt = 8.3 if dense else 9.0
        bullet_pt = 7.7 if dense else 8.4
        sec_before = Pt(4 if dense else 6)
        sec_after = Pt(1.5 if dense else 2.5)
        bullet_after = Pt(0.5 if dense else 1.2)
        item_before = Pt(1.5 if dense else 3)
        line_sp = 1.04 if dense else 1.10
    else:
        name_pt, sec_pt, body_pt, hdr_pt, bullet_pt = 20.0, 10.5, 9.5, 10.0, 9.2
        sec_before, sec_after, bullet_after, item_before, line_sp = Pt(7), Pt(3), Pt(1.8), Pt(4), 1.12

    def _style_run(run, size: float, bold: bool = False, italic: bool = False, color=COLOR_BODY, font_name: str = body_font):
        run.font.name = font_name
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = color
        return run

    # 1. Header (Name + Contact + Optional Photo)
    name = (resume_data.get("name") or "Candidate Name").strip().upper()
    contact_entries, _ = _build_contact_entries(resume_data.get("contact"))
    photo_bytes = _decode_b64_image(resume_data.get("photo") or resume_data.get("photo_base64"))

    def _populate_contact_paragraph(cp):
        cp.paragraph_format.space_before = Pt(0)
        cp.paragraph_format.space_after = Pt(3 if single_page else 5)
        for idx, entry in enumerate(contact_entries):
            if idx > 0:
                sep_r = cp.add_run("  |  ")
                _style_run(sep_r, max(7.5, body_pt - 0.3), color=COLOR_PIPE)
            if entry["kind"] == "link" and entry["url"]:
                _add_hyperlink_run(
                    cp,
                    entry["url"],
                    entry["text"] or "",
                    font_name=body_font,
                    font_size=max(7.5, body_pt - 0.3),
                    color_hex="1D4ED8",
                    bold=True,
                )
            else:
                cr = cp.add_run(entry["text"] or "")
                _style_run(cr, max(7.5, body_pt - 0.3), color=COLOR_MUTED)
        add_horizontal_rule(cp, color_hex="CBD5E1", size=4, space="2")

    header_rendered = False
    if photo_bytes:
        try:
            tbl = doc.add_table(rows=1, cols=2)
            tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
            tbl.autofit = False
            _remove_table_borders(tbl)

            c_img = tbl.cell(0, 0)
            c_img.width = Inches(1.05)
            set_cell_margins(c_img, top=0, bottom=20, left=0, right=40)
            ip = c_img.paragraphs[0]
            ip.alignment = WD_ALIGN_PARAGRAPH.CENTER
            ip.add_run().add_picture(BytesIO(photo_bytes), width=Inches(0.85))

            c_txt = tbl.cell(0, 1)
            c_txt.width = Inches(printable_w - 1.05)
            set_cell_margins(c_txt, top=20, bottom=20, left=20, right=0)
            np = c_txt.paragraphs[0]
            np.alignment = WD_ALIGN_PARAGRAPH.LEFT
            np.paragraph_format.space_before = Pt(0)
            np.paragraph_format.space_after = Pt(1)
            _style_run(np.add_run(name), name_pt, bold=True, color=COLOR_BLACK, font_name="Times New Roman")
            if contact_entries:
                cp = c_txt.add_paragraph()
                cp.alignment = WD_ALIGN_PARAGRAPH.LEFT
                _populate_contact_paragraph(cp)
            header_rendered = True
        except Exception:
            header_rendered = False

    if not header_rendered:
        np = doc.add_paragraph()
        np.alignment = WD_ALIGN_PARAGRAPH.CENTER
        np.paragraph_format.space_before = Pt(0)
        np.paragraph_format.space_after = Pt(1)
        _style_run(np.add_run(name), name_pt, bold=True, color=COLOR_BLACK, font_name="Times New Roman")
        if contact_entries:
            cp = doc.add_paragraph()
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _populate_contact_paragraph(cp)

    def add_section_heading(title: str):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = sec_before
        p.paragraph_format.space_after = sec_after
        p.paragraph_format.keep_with_next = True
        _style_run(p.add_run(title.upper()), sec_pt, bold=True, color=COLOR_NAVY)
        add_horizontal_rule(p, color_hex="2563EB", size=6, space="2")
        return p

    def add_compact_bullet(text: str):
        bp = doc.add_paragraph()
        bp.paragraph_format.left_indent = Inches(0.18)
        bp.paragraph_format.first_line_indent = Inches(-0.11)
        bp.paragraph_format.space_before = Pt(0)
        bp.paragraph_format.space_after = bullet_after
        bp.paragraph_format.line_spacing = line_sp
        _style_run(bp.add_run("\u2022  "), bullet_pt, color=COLOR_PRIMARY)
        _style_run(bp.add_run(text), bullet_pt, color=COLOR_BODY)

    # 2. Summary
    summary = str(resume_data.get("summary") or resume_data.get("resume_summary") or "").strip()
    if summary:
        add_section_heading("SUMMARY")
        sp = doc.add_paragraph()
        sp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(2 if single_page else 4)
        sp.paragraph_format.line_spacing = line_sp
        _style_run(sp.add_run(summary), body_pt, color=COLOR_BODY)

    # 3. Core Skills & Technologies
    if skill_rows:
        add_section_heading("CORE SKILLS & TECHNOLOGIES")
        for label, val_str in skill_rows:
            sp = doc.add_paragraph()
            sp.paragraph_format.space_before = Pt(0)
            sp.paragraph_format.space_after = Pt(0.6 if single_page else 2)
            sp.paragraph_format.line_spacing = line_sp
            _style_run(sp.add_run(f"{label}: "), body_pt, bold=True, color=COLOR_PRIMARY)
            _style_run(sp.add_run(val_str), body_pt, color=COLOR_BODY)

    # 4. Experience
    experience = [j for j in (resume_data.get("experience") or []) if isinstance(j, dict)]
    if experience:
        add_section_heading("EXPERIENCE")
        for job in experience:
            role = str(job.get("role") or job.get("title") or "Software Engineer").strip()
            comp = str(job.get("company") or "").strip()
            dur = str(job.get("duration") or job.get("dates") or "").strip()
            loc = str(job.get("location") or "").strip()

            hp = doc.add_paragraph()
            hp.paragraph_format.space_before = item_before
            hp.paragraph_format.space_after = Pt(0.5 if single_page else 1.5)
            hp.paragraph_format.keep_with_next = True
            try:
                hp.paragraph_format.tab_stops.add_tab_stop(Inches(printable_w), WD_TAB_ALIGNMENT.RIGHT)
            except Exception:
                pass

            _style_run(hp.add_run(role), hdr_pt, bold=True, color=COLOR_PRIMARY)
            if comp:
                _style_run(hp.add_run("  |  "), hdr_pt, color=COLOR_PIPE)
                _style_run(hp.add_run(comp), hdr_pt, bold=True, color=COLOR_NAVY)
            if loc:
                _style_run(hp.add_run(f" \u2022 {loc}"), max(7.2, body_pt - 0.3), color=COLOR_MUTED)
            if dur:
                _style_run(hp.add_run(f"\t{dur}"), max(7.4, body_pt - 0.2), bold=True, italic=True, color=COLOR_MUTED)

            bullets = [sanitize_bullet_text(b) for b in (job.get("bullets") or []) if sanitize_bullet_text(b)]
            if single_page:
                bullets = bullets[:3]
            for b in bullets:
                add_compact_bullet(b)

    # 5. Internships (if passed separately)
    internships = [i for i in (resume_data.get("internships") or []) if isinstance(i, dict)]
    if internships:
        add_section_heading("INTERNSHIP EXPERIENCE")
        for intern in internships:
            role = str(intern.get("role") or "Intern").strip()
            comp = str(intern.get("company") or "").strip()
            dur = str(intern.get("duration") or "").strip()

            hp = doc.add_paragraph()
            hp.paragraph_format.space_before = item_before
            hp.paragraph_format.space_after = Pt(0.5)
            hp.paragraph_format.keep_with_next = True
            try:
                hp.paragraph_format.tab_stops.add_tab_stop(Inches(printable_w), WD_TAB_ALIGNMENT.RIGHT)
            except Exception:
                pass
            _style_run(hp.add_run(role), hdr_pt, bold=True, color=COLOR_PRIMARY)
            if comp:
                _style_run(hp.add_run("  |  "), hdr_pt, color=COLOR_PIPE)
                _style_run(hp.add_run(comp), hdr_pt, bold=True, color=COLOR_NAVY)
            if dur:
                _style_run(hp.add_run(f"\t{dur}"), max(7.4, body_pt - 0.2), bold=True, italic=True, color=COLOR_MUTED)
            for b in intern.get("bullets", []):
                clean_b = sanitize_bullet_text(b)
                if clean_b:
                    add_compact_bullet(clean_b)

    # 6. Key Projects
    projects = [p for p in (resume_data.get("projects") or []) if isinstance(p, dict)]
    if projects:
        add_section_heading("KEY PROJECTS")
        for proj in projects:
            pname = str(proj.get("name") or proj.get("title") or "Project").strip()
            tech = str(proj.get("technologies") or proj.get("tools") or "").strip()
            pmeta = str(proj.get("duration") or proj.get("link") or "").strip()

            pp = doc.add_paragraph()
            pp.paragraph_format.space_before = item_before
            pp.paragraph_format.space_after = Pt(0.5 if single_page else 1.5)
            pp.paragraph_format.keep_with_next = True
            if pmeta:
                try:
                    pp.paragraph_format.tab_stops.add_tab_stop(Inches(printable_w), WD_TAB_ALIGNMENT.RIGHT)
                except Exception:
                    pass

            _style_run(pp.add_run(pname), hdr_pt, bold=True, color=COLOR_PRIMARY)
            if tech:
                _style_run(pp.add_run(f" ({tech})"), max(7.6, body_pt), bold=True, italic=True, color=COLOR_NAVY)
            if pmeta:
                _style_run(pp.add_run(f"\t{pmeta}"), max(7.4, body_pt - 0.2), italic=True, color=COLOR_MUTED)

            bullets = [sanitize_bullet_text(b) for b in (proj.get("bullets") or []) if sanitize_bullet_text(b)]
            if single_page:
                bullets = bullets[:3]
            for b in bullets:
                add_compact_bullet(b)

            proj_img_bytes = _decode_b64_image(proj.get("image") or proj.get("photo"))
            if proj_img_bytes:
                try:
                    img_p = doc.add_paragraph()
                    img_p.paragraph_format.left_indent = Inches(0.18)
                    img_p.paragraph_format.space_before = Pt(2)
                    img_p.paragraph_format.space_after = Pt(3)
                    img_p.add_run().add_picture(BytesIO(proj_img_bytes), width=Inches(2.8))
                except Exception:
                    pass

    # 7. Education
    education = [e for e in (resume_data.get("education") or []) if isinstance(e, dict)]
    if education:
        add_section_heading("EDUCATION")
        for edu in education:
            edu_fmt = format_education_entry(edu)
            ep1 = doc.add_paragraph()
            ep1.paragraph_format.space_before = item_before
            ep1.paragraph_format.space_after = Pt(0)
            ep1.paragraph_format.keep_with_next = True
            try:
                ep1.paragraph_format.tab_stops.add_tab_stop(Inches(printable_w), WD_TAB_ALIGNMENT.RIGHT)
            except Exception:
                pass
            _style_run(ep1.add_run(edu_fmt["inst_line"]), hdr_pt, bold=True, color=COLOR_PRIMARY)
            if edu_fmt["year"]:
                _style_run(ep1.add_run(f"\t{edu_fmt['year']}"), body_pt, bold=True, color=COLOR_PRIMARY)

            ep2 = doc.add_paragraph()
            ep2.paragraph_format.space_before = Pt(0)
            ep2.paragraph_format.space_after = Pt(1.5 if single_page else 3)
            _style_run(ep2.add_run(edu_fmt["degree_line"]), body_pt, italic=True, color=COLOR_BODY)

    # 8. Certifications
    certs = [str(c).strip() for c in (resume_data.get("certifications") or []) if str(c).strip()]
    if certs:
        add_section_heading("CERTIFICATIONS")
        for c in certs:
            add_compact_bullet(c)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:6]
    default_name = "Fresher_Resume" if single_page else "Tailored_Resume"
    clean_candidate = re.sub(r"[^a-zA-Z0-9_-]", "_", resume_data.get("name", default_name)).strip("_") or "Resume"
    tag = "_SinglePage_Fresher" if single_page else ""
    filename = f"{clean_candidate}{tag}_{timestamp}_{unique_suffix}.docx"
    output_path = GENERATED_DIR / filename
    doc.save(str(output_path))

    return output_path


def generate_docx(resume_data: Dict[str, Any]) -> Path:
    """
    Generate an executive-level, ATS-friendly DOCX resume matching the web preview.
    Routes to single-page mode when single_page or compact_layout is active.
    """
    if resume_data.get("single_page") or resume_data.get("compact_layout"):
        from services.fresher_resume_service import generate_single_page_docx
        return generate_single_page_docx(resume_data)
    return render_docx_from_resume_data(resume_data, single_page=False)


def generate_pdf(resume_data: Dict[str, Any]) -> Path:
    """
    Generate an executive-level, ATS-friendly PDF resume matching the web preview.
    Routes to single-page mode when single_page or compact_layout is active.
    """
    if resume_data.get("single_page") or resume_data.get("compact_layout"):
        from services.fresher_resume_service import generate_single_page_pdf
        return generate_single_page_pdf(resume_data)
    return render_pdf_from_resume_data(resume_data, single_page=False)
