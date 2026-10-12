import base64
import os
import re
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List

import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
import pymupdf as fitz

# Root directories
BACKEND_DIR = Path(__file__).resolve().parent.parent
GENERATED_DIR = BACKEND_DIR.parent / "generated_resumes"
GENERATED_DIR.mkdir(parents=True, exist_ok=True)


def set_cell_margins(cell, top=50, bottom=50, left=50, right=50):
    """Set inner margins for a table cell in twentieths of a point (dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def add_horizontal_rule(paragraph, color_hex="1E3A8A", size=12):
    """Add a clean bottom border or rule under section titles."""
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="{size}" w:space="4" w:color="{color_hex}"/></w:pBdr>')
    pPr.append(pBdr)


def generate_docx(resume_data: Dict[str, Any]) -> Path:
    """
    Generate an executive-level, ATS-friendly DOCX resume with modern typography,
    clean spacing, and professional section dividers.
    """
    doc = docx.Document()

    # 1. Page Margins (0.75 in / 54pt all around)
    for section in doc.sections:
        section.top_margin = Inches(0.65)
        section.bottom_margin = Inches(0.65)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    # Palette
    COLOR_PRIMARY = RGBColor(15, 23, 42)      # Deep Navy/Charcoal
    COLOR_ACCENT = RGBColor(30, 58, 138)      # Professional Navy Accent (#1E3A8A)
    COLOR_BODY = RGBColor(51, 65, 85)         # Slate Body Text (#334155)
    COLOR_MUTED = RGBColor(100, 116, 139)     # Subtle Gray (#64748B)

    # 2. Candidate Header (with optional photo support)
    photo_data = resume_data.get("photo") or resume_data.get("photo_base64")
    name = resume_data.get("name") or "Candidate Name"
    contact = resume_data.get("contact", {})
    contact_parts = []
    if contact.get("email"):
        contact_parts.append(contact["email"])
    if contact.get("phone"):
        contact_parts.append(contact["phone"])
    if contact.get("location"):
        contact_parts.append(contact["location"])
    if contact.get("linkedin"):
        contact_parts.append(contact["linkedin"])
    if contact.get("github"):
        contact_parts.append(contact["github"])

    header_rendered = False
    if photo_data:
        try:
            import base64
            from io import BytesIO
            raw_b64 = photo_data.split(",", 1)[1] if "," in photo_data else photo_data
            img_bytes = BytesIO(base64.b64decode(raw_b64))

            table = doc.add_table(rows=1, cols=2)
            table.alignment = WD_TABLE_ALIGNMENT.CENTER
            table.autofit = False

            cell_photo = table.cell(0, 0)
            cell_photo.width = Inches(1.3)
            photo_p = cell_photo.paragraphs[0]
            photo_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            photo_run = photo_p.add_run()
            photo_run.add_picture(img_bytes, width=Inches(1.05))

            cell_text = table.cell(0, 1)
            cell_text.width = Inches(5.7)
            name_p = cell_text.paragraphs[0]
            name_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            name_p.paragraph_format.space_before = Pt(6)
            name_p.paragraph_format.space_after = Pt(2)
            name_run = name_p.add_run(name.upper())
            name_run.font.name = "Arial"
            name_run.font.size = Pt(18)
            name_run.font.bold = True
            name_run.font.color.rgb = COLOR_PRIMARY

            if contact_parts:
                contact_p = cell_text.add_paragraph()
                contact_p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                contact_p.paragraph_format.space_after = Pt(10)
                contact_run = contact_p.add_run("  |  ".join(contact_parts))
                contact_run.font.name = "Arial"
                contact_run.font.size = Pt(9.5)
                contact_run.font.color.rgb = COLOR_MUTED

            header_rendered = True
        except Exception:
            header_rendered = False

    if not header_rendered:
        name_p = doc.add_paragraph()
        name_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        name_p.paragraph_format.space_before = Pt(0)
        name_p.paragraph_format.space_after = Pt(2)
        name_run = name_p.add_run(name.upper())
        name_run.font.name = "Arial"
        name_run.font.size = Pt(20)
        name_run.font.bold = True
        name_run.font.color.rgb = COLOR_PRIMARY

        if contact_parts:
            contact_p = doc.add_paragraph()
            contact_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            contact_p.paragraph_format.space_after = Pt(14)
            contact_run = contact_p.add_run("  |  ".join(contact_parts))
            contact_run.font.name = "Arial"
            contact_run.font.size = Pt(9.5)
            contact_run.font.color.rgb = COLOR_MUTED

    # Section Header Helper
    def add_section_header(title: str):
        sec_p = doc.add_paragraph()
        sec_p.paragraph_format.space_before = Pt(10)
        sec_p.paragraph_format.space_after = Pt(4)
        sec_run = sec_p.add_run(title.upper())
        sec_run.font.name = "Arial"
        sec_run.font.size = Pt(11)
        sec_run.font.bold = True
        sec_run.font.color.rgb = COLOR_ACCENT
        add_horizontal_rule(sec_p, color_hex="2563EB", size=8)
        return sec_p

    # 4. Professional Summary
    summary = resume_data.get("summary") or resume_data.get("resume_summary")
    if summary:
        add_section_header("Professional Summary")
        sum_p = doc.add_paragraph()
        sum_p.paragraph_format.space_after = Pt(8)
        sum_p.paragraph_format.line_spacing = 1.15
        sum_run = sum_p.add_run(str(summary).strip())
        sum_run.font.name = "Arial"
        sum_run.font.size = Pt(10)
        sum_run.font.color.rgb = COLOR_BODY

    # 5. Skills
    skills = resume_data.get("skills")
    if skills:
        add_section_header("Core Competencies & Skills")

        if isinstance(skills, dict):
            # Display grouped skills
            for category, skill_list in skills.items():
                if category == "missing_from_resume":
                    continue  # Do not include missing skills in tailored resume document
                if not skill_list:
                    continue
                
                cat_label = category.replace("_", " ").title()
                if category == "matching_with_jd":
                    cat_label = "Targeted Expertise"

                skill_str = ", ".join(skill_list) if isinstance(skill_list, list) else str(skill_list)
                if not skill_str.strip():
                    continue

                sp = doc.add_paragraph()
                sp.paragraph_format.space_after = Pt(3)
                sp.paragraph_format.line_spacing = 1.15
                
                lbl_run = sp.add_run(f"{cat_label}: ")
                lbl_run.font.name = "Arial"
                lbl_run.font.size = Pt(9.5)
                lbl_run.font.bold = True
                lbl_run.font.color.rgb = COLOR_PRIMARY

                val_run = sp.add_run(skill_str)
                val_run.font.name = "Arial"
                val_run.font.size = Pt(9.5)
                val_run.font.color.rgb = COLOR_BODY

        elif isinstance(skills, list):
            sp = doc.add_paragraph()
            sp.paragraph_format.space_after = Pt(6)
            val_run = sp.add_run(", ".join([str(s) for s in skills]))
            val_run.font.name = "Arial"
            val_run.font.size = Pt(9.5)
            val_run.font.color.rgb = COLOR_BODY

    # 6. Professional Experience
    experience = resume_data.get("experience", [])
    if experience and isinstance(experience, list):
        add_section_header("Professional Experience")

        for job in experience:
            if not isinstance(job, dict):
                continue

            role = job.get("role") or job.get("title") or "Role Title"
            company = job.get("company") or "Company"
            duration = job.get("duration") or job.get("dates") or ""
            location = job.get("location") or ""

            # Header line: Role (Bold) & Company
            header_p = doc.add_paragraph()
            header_p.paragraph_format.space_before = Pt(6)
            header_p.paragraph_format.space_after = Pt(2)
            
            role_run = header_p.add_run(role)
            role_run.font.name = "Arial"
            role_run.font.size = Pt(10.5)
            role_run.font.bold = True
            role_run.font.color.rgb = COLOR_PRIMARY

            sep_run = header_p.add_run("  |  ")
            sep_run.font.name = "Arial"
            sep_run.font.size = Pt(10)
            sep_run.font.color.rgb = COLOR_MUTED

            comp_run = header_p.add_run(company)
            comp_run.font.name = "Arial"
            comp_run.font.size = Pt(10)
            comp_run.font.bold = True
            comp_run.font.color.rgb = COLOR_ACCENT

            sub_items = []
            if duration:
                sub_items.append(duration)
            if location:
                sub_items.append(location)

            if sub_items:
                right_text = "  |  ".join(sub_items)
                meta_p = doc.add_paragraph()
                meta_p.paragraph_format.space_after = Pt(3)
                meta_run = meta_p.add_run(right_text)
                meta_run.font.name = "Arial"
                meta_run.font.size = Pt(9)
                meta_run.font.italic = True
                meta_run.font.color.rgb = COLOR_MUTED

            # Bullets
            bullets = job.get("bullets", [])
            for b in bullets:
                if not b or not str(b).strip():
                    continue
                bp = doc.add_paragraph(style='List Bullet')
                bp.paragraph_format.space_before = Pt(1)
                bp.paragraph_format.space_after = Pt(2.5)
                bp.paragraph_format.line_spacing = 1.15
                brun = bp.add_run(str(b).strip())
                brun.font.name = "Arial"
                brun.font.size = Pt(9.5)
                brun.font.color.rgb = COLOR_BODY

    # 7. Projects
    projects = resume_data.get("projects", [])
    if projects and isinstance(projects, list):
        add_section_header("Key Projects")

        for proj in projects:
            if not isinstance(proj, dict):
                continue

            name = proj.get("name") or proj.get("title") or "Project"
            tech = proj.get("technologies") or proj.get("tools") or ""

            pp = doc.add_paragraph()
            pp.paragraph_format.space_before = Pt(4)
            pp.paragraph_format.space_after = Pt(2)

            prun = pp.add_run(name)
            prun.font.name = "Arial"
            prun.font.size = Pt(10)
            prun.font.bold = True
            prun.font.color.rgb = COLOR_PRIMARY

            if tech:
                tech_run = pp.add_run(f"  ({tech})")
                tech_run.font.name = "Arial"
                tech_run.font.size = Pt(9)
                tech_run.font.italic = True
                tech_run.font.color.rgb = COLOR_ACCENT

            for b in proj.get("bullets", []):
                if not b or not str(b).strip():
                    continue
                bp = doc.add_paragraph(style='List Bullet')
                bp.paragraph_format.space_before = Pt(1)
                bp.paragraph_format.space_after = Pt(2.5)
                bp.paragraph_format.line_spacing = 1.15
                brun = bp.add_run(str(b).strip())
                brun.font.name = "Arial"
                brun.font.size = Pt(9.5)
                brun.font.color.rgb = COLOR_BODY

            # Project screenshot / photo embedding
            proj_img = proj.get("image") or proj.get("photo")
            if proj_img and isinstance(proj_img, str) and len(proj_img) > 50:
                try:
                    import base64
                    from io import BytesIO
                    raw_b64 = proj_img.split(",", 1)[1] if "," in proj_img else proj_img
                    img_bytes = BytesIO(base64.b64decode(raw_b64))
                    img_p = doc.add_paragraph()
                    img_p.paragraph_format.space_before = Pt(2)
                    img_p.paragraph_format.space_after = Pt(4)
                    img_run = img_p.add_run()
                    img_run.add_picture(img_bytes, width=Inches(3.2))
                except Exception:
                    pass

    # 8. Education
    education = resume_data.get("education", [])
    if education and isinstance(education, list):
        add_section_header("Education")

        for edu in education:
            if not isinstance(edu, dict):
                continue

            deg = edu.get("degree") or "Degree"
            inst = edu.get("institution") or edu.get("university") or ""
            yr = edu.get("year") or edu.get("graduation_year") or ""

            ep = doc.add_paragraph()
            ep.paragraph_format.space_before = Pt(2)
            ep.paragraph_format.space_after = Pt(2)

            deg_run = ep.add_run(deg)
            deg_run.font.name = "Arial"
            deg_run.font.size = Pt(9.5)
            deg_run.font.bold = True
            deg_run.font.color.rgb = COLOR_PRIMARY

            if inst:
                inst_run = ep.add_run(f", {inst}")
                inst_run.font.name = "Arial"
                inst_run.font.size = Pt(9.5)
                inst_run.font.color.rgb = COLOR_BODY

            if yr:
                yr_run = ep.add_run(f" ({yr})")
                yr_run.font.name = "Arial"
                yr_run.font.size = Pt(9)
                yr_run.font.italic = True
                yr_run.font.color.rgb = COLOR_MUTED

    # 9. Certifications
    certifications = resume_data.get("certifications", [])
    if certifications and isinstance(certifications, list) and len(certifications) > 0:
        add_section_header("Certifications & Credentials")
        for cert in certifications:
            if not cert:
                continue
            cp = doc.add_paragraph(style='List Bullet')
            cp.paragraph_format.space_before = Pt(1)
            cp.paragraph_format.space_after = Pt(2)
            crun = cp.add_run(str(cert).strip())
            crun.font.name = "Arial"
            crun.font.size = Pt(9.5)
            crun.font.color.rgb = COLOR_BODY

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:6]
    clean_candidate = re.sub(r'[^a-zA-Z0-9_-]', '_', resume_data.get("name", "Tailored_Resume")).strip('_')
    filename = f"{clean_candidate}_{timestamp}_{unique_suffix}.docx"
    output_path = GENERATED_DIR / filename
    doc.save(str(output_path))

    return output_path


def generate_pdf(resume_data: Dict[str, Any]) -> Path:
    """
    Generate an executive-level, ATS-friendly PDF resume using PyMuPDF.
    Standard A4 dimensions (595 x 842 points) matching the web preview styling.
    """
    pdf_doc = fitz.open()

    page_width = 595.0
    page_height = 842.0
    left_margin = 44.0
    right_margin = 551.0
    content_width = right_margin - left_margin

    curr_page = pdf_doc.new_page(width=page_width, height=page_height)
    curr_y = 44.0

    def check_page_break(needed_height: float):
        nonlocal curr_page, curr_y
        if curr_y + needed_height > 795.0:
            curr_page = pdf_doc.new_page(width=page_width, height=page_height)
            curr_y = 44.0

    # Colors (RGB normalized 0.0 - 1.0)
    COLOR_PRIMARY = (0.06, 0.09, 0.16)     # Deep Charcoal/Navy #0f172a
    COLOR_ACCENT = (0.12, 0.23, 0.54)      # Executive Navy #1e3a8a
    COLOR_RULE = (0.15, 0.39, 0.92)        # Modern Blue divider #2563eb
    COLOR_BODY = (0.20, 0.25, 0.33)        # Slate #334155
    COLOR_MUTED = (0.39, 0.45, 0.55)       # Gray #64748b

    # 1. Header (Name, Contact, Photo)
    name = (resume_data.get("name") or "Candidate Name").upper()
    contact = resume_data.get("contact", {})
    contact_parts = []
    if contact.get("email"):
        contact_parts.append(contact["email"])
    if contact.get("phone"):
        contact_parts.append(contact["phone"])
    if contact.get("location"):
        contact_parts.append(contact["location"])
    if contact.get("linkedin"):
        contact_parts.append(contact["linkedin"])
    if contact.get("github"):
        contact_parts.append(contact["github"])

    photo_data = resume_data.get("photo") or resume_data.get("photo_base64")
    photo_rendered = False
    if photo_data:
        try:
            raw_b64 = photo_data.split(",", 1)[1] if "," in photo_data else photo_data
            img_bytes = base64.b64decode(raw_b64)
            img_rect = fitz.Rect(right_margin - 65, curr_y, right_margin, curr_y + 65)
            curr_page.insert_image(img_rect, stream=img_bytes)
            photo_rendered = True
        except Exception:
            photo_rendered = False

    name_width = right_margin - (75 if photo_rendered else 0) - left_margin
    name_rect = fitz.Rect(left_margin, curr_y, left_margin + name_width, curr_y + 24)
    curr_page.insert_textbox(name_rect, name, fontsize=18, fontname="helv", color=COLOR_PRIMARY)
    curr_y += 24

    if contact_parts:
        contact_line = "  |  ".join(contact_parts)
        contact_rect = fitz.Rect(left_margin, curr_y, left_margin + name_width, curr_y + 16)
        curr_page.insert_textbox(contact_rect, contact_line, fontsize=8.5, fontname="helv", color=COLOR_MUTED)
        curr_y += 18

    if photo_rendered and curr_y < 115.0:
        curr_y = 115.0

    curr_y += 4

    def draw_section_heading(title: str):
        nonlocal curr_y
        check_page_break(32)
        curr_y += 6
        head_rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 14)
        curr_page.insert_textbox(head_rect, title.upper(), fontsize=10, fontname="helv", color=COLOR_ACCENT)
        curr_y += 14
        curr_page.draw_line(fitz.Point(left_margin, curr_y), fitz.Point(right_margin, curr_y), color=COLOR_RULE, width=0.8)
        curr_y += 8

    # 2. Professional Summary
    summary = resume_data.get("summary") or resume_data.get("resume_summary")
    if summary:
        draw_section_heading("Professional Summary")
        check_page_break(44)
        sum_rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 90)
        rc = curr_page.insert_textbox(sum_rect, str(summary).strip(), fontsize=9, fontname="helv", color=COLOR_BODY)
        curr_y += 42 if rc >= 0 else 54

    # 3. Core Competencies & Skills
    skills = resume_data.get("skills")
    if skills:
        draw_section_heading("Core Competencies & Skills")
        if isinstance(skills, dict):
            for cat, slist in skills.items():
                if cat == "missing_from_resume" or not slist:
                    continue
                label = cat.replace("_", " ").title()
                if cat == "matching_with_jd":
                    label = "Targeted Expertise"
                val_str = ", ".join(slist) if isinstance(slist, list) else str(slist)
                if not val_str.strip():
                    continue
                check_page_break(18)
                line_text = f"{label}: {val_str}"
                rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 16)
                curr_page.insert_textbox(rect, line_text, fontsize=8.5, fontname="helv", color=COLOR_BODY)
                curr_y += 14
        elif isinstance(skills, list):
            check_page_break(20)
            rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 18)
            curr_page.insert_textbox(rect, ", ".join([str(s) for s in skills]), fontsize=8.5, fontname="helv", color=COLOR_BODY)
            curr_y += 16

    # 4. Professional Experience
    experience = resume_data.get("experience", [])
    if experience and isinstance(experience, list):
        draw_section_heading("Professional Experience")
        for job in experience:
            if not isinstance(job, dict):
                continue
            role = job.get("role") or job.get("title") or "Role Title"
            company = job.get("company") or "Company"
            duration = job.get("duration") or job.get("dates") or ""
            location = job.get("location") or ""

            check_page_break(32)
            header_text = f"{role}  |  {company}"
            sub_meta = "  |  ".join([s for s in [duration, location] if s])

            h_rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 14)
            curr_page.insert_textbox(h_rect, header_text, fontsize=9.5, fontname="helv", color=COLOR_PRIMARY)
            curr_y += 12

            if sub_meta:
                m_rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 12)
                curr_page.insert_textbox(m_rect, sub_meta, fontsize=8, fontname="helv", color=COLOR_MUTED)
                curr_y += 12

            for b in job.get("bullets", []):
                if not b or not str(b).strip():
                    continue
                check_page_break(24)
                bullet_str = f"•  {b.strip()}"
                b_rect = fitz.Rect(left_margin + 6, curr_y, right_margin, curr_y + 36)
                curr_page.insert_textbox(b_rect, bullet_str, fontsize=8.5, fontname="helv", color=COLOR_BODY)
                curr_y += 16

    # 5. Internships
    internships = resume_data.get("internships", [])
    if internships and isinstance(internships, list):
        draw_section_heading("Internship Experience")
        for intern in internships:
            if not isinstance(intern, dict):
                continue
            role = intern.get("role") or "Intern"
            company = intern.get("company") or "Company"
            duration = intern.get("duration") or ""

            check_page_break(30)
            h_rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 14)
            curr_page.insert_textbox(h_rect, f"{role}  |  {company} ({duration})", fontsize=9.5, fontname="helv", color=COLOR_PRIMARY)
            curr_y += 14

            for b in intern.get("bullets", []):
                if not b or not str(b).strip():
                    continue
                check_page_break(20)
                b_rect = fitz.Rect(left_margin + 6, curr_y, right_margin, curr_y + 30)
                curr_page.insert_textbox(b_rect, f"•  {b.strip()}", fontsize=8.5, fontname="helv", color=COLOR_BODY)
                curr_y += 16

    # 6. Key Projects
    projects = resume_data.get("projects", [])
    if projects and isinstance(projects, list):
        draw_section_heading("Key Projects")
        for proj in projects:
            if not isinstance(proj, dict):
                continue
            name = proj.get("name") or proj.get("title") or "Project"
            tech = proj.get("technologies") or proj.get("tools") or ""

            check_page_break(28)
            p_line = f"{name} ({tech})" if tech else name
            p_rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 14)
            curr_page.insert_textbox(p_rect, p_line, fontsize=9.5, fontname="helv", color=COLOR_PRIMARY)
            curr_y += 13

            for b in proj.get("bullets", []):
                if not b or not str(b).strip():
                    continue
                check_page_break(22)
                b_rect = fitz.Rect(left_margin + 6, curr_y, right_margin, curr_y + 32)
                curr_page.insert_textbox(b_rect, f"•  {b.strip()}", fontsize=8.5, fontname="helv", color=COLOR_BODY)
                curr_y += 16

            proj_img = proj.get("image") or proj.get("photo")
            if proj_img and isinstance(proj_img, str) and len(proj_img) > 50:
                try:
                    raw_b64 = proj_img.split(",", 1)[1] if "," in proj_img else proj_img
                    img_bytes = base64.b64decode(raw_b64)
                    check_page_break(90)
                    img_rect = fitz.Rect(left_margin + 6, curr_y, left_margin + 180, curr_y + 85)
                    curr_page.insert_image(img_rect, stream=img_bytes)
                    curr_y += 90
                except Exception:
                    pass

    # 7. Education
    education = resume_data.get("education", [])
    if education and isinstance(education, list):
        draw_section_heading("Education")
        for edu in education:
            if not isinstance(edu, dict):
                continue
            deg = edu.get("degree") or "Degree"
            inst = edu.get("institution") or edu.get("university") or ""
            yr = edu.get("year") or edu.get("graduation_year") or ""
            check_page_break(18)
            edu_line = f"{deg}, {inst} ({yr})" if yr else f"{deg}, {inst}"
            e_rect = fitz.Rect(left_margin, curr_y, right_margin, curr_y + 14)
            curr_page.insert_textbox(e_rect, edu_line, fontsize=8.5, fontname="helv", color=COLOR_BODY)
            curr_y += 14

    # 8. Certifications
    certs = resume_data.get("certifications", [])
    if certs and isinstance(certs, list):
        draw_section_heading("Certifications & Credentials")
        for c in certs:
            if not c:
                continue
            check_page_break(18)
            c_rect = fitz.Rect(left_margin + 6, curr_y, right_margin, curr_y + 14)
            curr_page.insert_textbox(c_rect, f"•  {str(c).strip()}", fontsize=8.5, fontname="helv", color=COLOR_BODY)
            curr_y += 14

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_suffix = uuid.uuid4().hex[:6]
    clean_candidate = re.sub(r'[^a-zA-Z0-9_-]', '_', resume_data.get("name", "Tailored_Resume")).strip('_')
    filename = f"{clean_candidate}_{timestamp}_{unique_suffix}.pdf"
    output_path = GENERATED_DIR / filename
    pdf_doc.save(str(output_path))
    pdf_doc.close()

    return output_path

