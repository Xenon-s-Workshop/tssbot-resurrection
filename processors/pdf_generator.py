"""
PDF Generator — Two engines, two modes.

Engine 1: ReportLab  (platypus layout engine)
Engine 2: WeasyPrint (HTML → PDF renderer)

Mode A: "answer_key"  — questions only, then answer key at end
Mode B: "inline"      — each question has answer + explanation inline

Bengali font (Noto Sans Bengali) is registered for both engines.
Falls back to a Latin-only embedded font if the .ttf is missing.
"""

import logging
import os
from io import BytesIO
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

FONTS_DIR = Path("fonts")
BENGALI_FONT_PATH = FONTS_DIR / "NotoSansBengali-Regular.ttf"
BENGALI_FONT_NAME = "NotoBengali"

QUESTIONS_PER_PAGE = 6


# ── Font bootstrap ────────────────────────────────────────────────────────────

def _download_noto_bengali():
    """Download Noto Sans Bengali from Google Fonts CDN if not present."""
    if BENGALI_FONT_PATH.exists():
        return True
    try:
        import requests
        FONTS_DIR.mkdir(exist_ok=True)
        url = (
            "https://github.com/googlefonts/noto-fonts/raw/main/hinted/ttf/"
            "NotoSansBengali/NotoSansBengali-Regular.ttf"
        )
        logger.info("Downloading Noto Sans Bengali font…")
        r = requests.get(url, timeout=30)
        r.raise_for_status()
        BENGALI_FONT_PATH.write_bytes(r.content)
        logger.info(f"Font saved to {BENGALI_FONT_PATH}")
        return True
    except Exception as e:
        logger.warning(f"Could not download Bengali font: {e}")
        return False


def _ensure_font():
    if not BENGALI_FONT_PATH.exists():
        _download_noto_bengali()
    return BENGALI_FONT_PATH.exists()


# ── ReportLab engine ─────────────────────────────────────────────────────────

def _build_reportlab_pdf(questions: List[Dict], mode: str, title: str) -> BytesIO:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    # Register Bengali font
    font_available = _ensure_font()
    if font_available:
        try:
            pdfmetrics.registerFont(TTFont(BENGALI_FONT_NAME, str(BENGALI_FONT_PATH)))
            body_font = BENGALI_FONT_NAME
        except Exception as e:
            logger.warning(f"Font registration failed: {e}")
            body_font = "Helvetica"
    else:
        body_font = "Helvetica"

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()

    def style(name, **kw):
        return ParagraphStyle(name, fontName=body_font, **kw)

    s_title = style("DocTitle", fontSize=16, spaceAfter=6, leading=20)
    s_h2 = style("SectionHead", fontSize=13, spaceBefore=12, spaceAfter=4, leading=16)
    s_q = style("Question", fontSize=11, spaceBefore=6, spaceAfter=3, leading=15)
    s_opt = style("Option", fontSize=10, leftIndent=14, spaceBefore=1, leading=13)
    s_ans = style("Answer", fontSize=10, leftIndent=14, spaceBefore=2, textColor=(0.1, 0.5, 0.1), leading=13)
    s_exp = style("Explanation", fontSize=9, leftIndent=14, spaceBefore=1, textColor=(0.3, 0.3, 0.3), leading=12)
    s_key = style("KeyLine", fontSize=10, spaceBefore=2, leading=13)

    option_labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]
    story = []

    story.append(Paragraph(_esc(title), s_title))
    story.append(Spacer(1, 4 * mm))

    if mode == "answer_key":
        # ── Part 1: Questions only ────────────────────────────────────────
        story.append(Paragraph("Questions", s_h2))
        for page_start in range(0, len(questions), QUESTIONS_PER_PAGE):
            page_qs = questions[page_start: page_start + QUESTIONS_PER_PAGE]
            for local_i, q in enumerate(page_qs):
                global_i = page_start + local_i + 1
                q_text = _esc(q.get("question_description") or "")
                story.append(Paragraph(f"<b>Q{global_i}.</b> {q_text}", s_q))
                for j, opt in enumerate(q.get("options") or []):
                    label = option_labels[j] if j < len(option_labels) else str(j + 1)
                    story.append(Paragraph(f"{label}. {_esc(opt)}", s_opt))
                story.append(Spacer(1, 3 * mm))
            if page_start + QUESTIONS_PER_PAGE < len(questions):
                story.append(PageBreak())

        # ── Part 2: Answer Key ────────────────────────────────────────────
        story.append(PageBreak())
        story.append(Paragraph("Answer Key", s_h2))
        story.append(Spacer(1, 2 * mm))
        for i, q in enumerate(questions):
            correct_idx = q.get("correct_answer_index", 0)
            correct_letter = option_labels[correct_idx] if correct_idx < len(option_labels) else "A"
            exp = _esc(q.get("explanation") or "")
            story.append(Paragraph(f"<b>{i+1} → {correct_letter}</b>", s_key))
            if exp:
                story.append(Paragraph(exp, s_exp))
            story.append(Spacer(1, 2 * mm))
            if (i + 1) % 15 == 0 and i + 1 < len(questions):
                story.append(PageBreak())

    else:
        # ── Inline mode ───────────────────────────────────────────────────
        story.append(Paragraph("Quiz Questions", s_h2))
        for page_start in range(0, len(questions), QUESTIONS_PER_PAGE):
            page_qs = questions[page_start: page_start + QUESTIONS_PER_PAGE]
            for local_i, q in enumerate(page_qs):
                global_i = page_start + local_i + 1
                q_text = _esc(q.get("question_description") or "")
                story.append(Paragraph(f"<b>Q{global_i}.</b> {q_text}", s_q))
                correct_idx = q.get("correct_answer_index", 0)
                for j, opt in enumerate(q.get("options") or []):
                    label = option_labels[j] if j < len(option_labels) else str(j + 1)
                    is_correct = j == correct_idx
                    opt_text = f"<b>✓ {label}. {_esc(opt)}</b>" if is_correct else f"{label}. {_esc(opt)}"
                    story.append(Paragraph(opt_text, s_ans if is_correct else s_opt))
                exp = _esc(q.get("explanation") or "")
                if exp:
                    story.append(Paragraph(f"💡 {exp}", s_exp))
                story.append(Spacer(1, 4 * mm))
            if page_start + QUESTIONS_PER_PAGE < len(questions):
                story.append(PageBreak())

    doc.build(story)
    buf.seek(0)
    return buf


# ── WeasyPrint engine ─────────────────────────────────────────────────────────

def _build_weasyprint_pdf(questions: List[Dict], mode: str, title: str) -> BytesIO:
    from weasyprint import HTML, CSS

    font_available = _ensure_font()
    abs_font_path = BENGALI_FONT_PATH.resolve().as_posix()

    font_face = ""
    if font_available:
        font_face = f"""
        @font-face {{
            font-family: 'NotoBengali';
            src: url('file://{abs_font_path}');
        }}
        """
    body_font = "'NotoBengali', 'Noto Sans Bengali', 'Arial Unicode MS', sans-serif" if font_available else "Arial, sans-serif"

    css_string = f"""
        {font_face}

        @page {{
            size: A4;
            margin: 20mm;
        }}

        body {{
            font-family: {body_font};
            font-size: 11pt;
            color: #1a1a1a;
            line-height: 1.5;
        }}

        h1 {{
            font-size: 18pt;
            margin-bottom: 8px;
            border-bottom: 2px solid #333;
            padding-bottom: 4px;
        }}

        h2 {{
            font-size: 14pt;
            margin-top: 20px;
            margin-bottom: 8px;
            color: #2c3e50;
        }}

        .question-block {{
            margin-bottom: 18px;
            page-break-inside: avoid;
        }}

        .question-text {{
            font-size: 11pt;
            font-weight: bold;
            margin-bottom: 6px;
        }}

        .option {{
            font-size: 10pt;
            margin-left: 16px;
            margin-bottom: 2px;
        }}

        .option.correct {{
            color: #1a7a1a;
            font-weight: bold;
        }}

        .explanation {{
            font-size: 9pt;
            color: #555;
            margin-left: 16px;
            margin-top: 4px;
            font-style: italic;
        }}

        .answer-key-line {{
            font-size: 10pt;
            margin-bottom: 4px;
        }}

        .page-break {{
            page-break-after: always;
        }}

        .section {{
            margin-bottom: 12px;
        }}
    """

    option_labels = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J"]

    def esc(text: str) -> str:
        return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    html_parts = [
        f"<!DOCTYPE html><html><head><meta charset='UTF-8'></head><body>",
        f"<h1>{esc(title)}</h1>",
    ]

    if mode == "answer_key":
        html_parts.append("<h2>Questions</h2>")
        for i, q in enumerate(questions):
            q_text = esc(q.get("question_description") or "")
            html_parts.append(f'<div class="question-block">')
            html_parts.append(f'<div class="question-text">Q{i+1}. {q_text}</div>')
            for j, opt in enumerate(q.get("options") or []):
                label = option_labels[j] if j < len(option_labels) else str(j + 1)
                html_parts.append(f'<div class="option">{label}. {esc(opt)}</div>')
            html_parts.append("</div>")
            if (i + 1) % QUESTIONS_PER_PAGE == 0 and i + 1 < len(questions):
                html_parts.append('<div class="page-break"></div>')

        html_parts.append('<div class="page-break"></div>')
        html_parts.append("<h2>Answer Key</h2>")
        for i, q in enumerate(questions):
            correct_idx = q.get("correct_answer_index", 0)
            correct_letter = option_labels[correct_idx] if correct_idx < len(option_labels) else "A"
            exp = esc(q.get("explanation") or "")
            html_parts.append(f'<div class="section">')
            html_parts.append(f'<div class="answer-key-line"><b>{i+1} → {correct_letter}</b></div>')
            if exp:
                html_parts.append(f'<div class="explanation">💡 {exp}</div>')
            html_parts.append("</div>")

    else:
        html_parts.append("<h2>Quiz Questions</h2>")
        for i, q in enumerate(questions):
            q_text = esc(q.get("question_description") or "")
            correct_idx = q.get("correct_answer_index", 0)
            html_parts.append(f'<div class="question-block">')
            html_parts.append(f'<div class="question-text">Q{i+1}. {q_text}</div>')
            for j, opt in enumerate(q.get("options") or []):
                label = option_labels[j] if j < len(option_labels) else str(j + 1)
                is_correct = j == correct_idx
                cls = 'option correct' if is_correct else 'option'
                prefix = "✓ " if is_correct else ""
                html_parts.append(f'<div class="{cls}">{prefix}{label}. {esc(opt)}</div>')
            exp = esc(q.get("explanation") or "")
            if exp:
                html_parts.append(f'<div class="explanation">💡 {exp}</div>')
            html_parts.append("</div>")
            if (i + 1) % QUESTIONS_PER_PAGE == 0 and i + 1 < len(questions):
                html_parts.append('<div class="page-break"></div>')

    html_parts.append("</body></html>")
    html_string = "\n".join(html_parts)

    pdf_bytes = HTML(string=html_string).write_pdf(
        stylesheets=[CSS(string=css_string)]
    )
    buf = BytesIO(pdf_bytes)
    buf.seek(0)
    return buf


# ── Public API ────────────────────────────────────────────────────────────────

def generate_pdf(
    questions: List[Dict],
    mode: str = "inline",
    engine: str = "reportlab",
    title: str = "Quiz",
    output_path: Path = None,
) -> BytesIO:
    """
    Generate a PDF from questions.

    Parameters
    ----------
    questions   : list of question dicts
    mode        : "inline" | "answer_key"
    engine      : "reportlab" | "weasyprint"
    title       : document title
    output_path : if given, also write to this path

    Returns
    -------
    BytesIO with PDF bytes (seeked to 0)
    """
    if not questions:
        raise ValueError("No questions provided for PDF generation")

    logger.info(f"Generating PDF — engine={engine}, mode={mode}, questions={len(questions)}")

    if engine == "weasyprint":
        buf = _build_weasyprint_pdf(questions, mode, title)
    else:
        buf = _build_reportlab_pdf(questions, mode, title)

    if output_path:
        output_path.write_bytes(buf.read())
        buf.seek(0)
        logger.info(f"PDF saved to {output_path}")

    return buf


def _esc(text: str) -> str:
    """Escape XML special chars for ReportLab Paragraph."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
