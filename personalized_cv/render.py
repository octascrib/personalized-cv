"""Render escaped plain text through a controlled, single-column PDF layout."""

from pathlib import Path
import re
import unicodedata
from xml.sax.saxutils import escape

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph

from .models import GeneratedCV


def find_fonts(font_directory: Path | None) -> tuple[Path, Path]:
    directories = [font_directory] if font_directory else [
        Path("/usr/share/fonts/truetype/dejavu"),
        Path("/usr/share/fonts/dejavu-sans-fonts"),
        Path("/usr/local/share/fonts"),
    ]
    for directory in directories:
        regular = directory / "DejaVuSans.ttf"
        bold = directory / "DejaVuSans-Bold.ttf"
        if regular.is_file() and bold.is_file():
            return regular, bold
    raise ValueError("DejaVu Sans fonts not found; install them or use --font-dir with both TTF files.")


def markdown(cv: GeneratedCV) -> str:
    lines = [f"# {cv.candidate_name.text}", ""]
    lines.extend(claim.text for claim in cv.contacts)
    lines.append("")
    for section in cv.sections:
        lines.extend((f"## {section.heading}", ""))
        for entry in section.entries:
            if entry.heading:
                lines.extend((f"### {entry.heading.text}", ""))
            lines.extend(claim.text for claim in entry.details)
            lines.extend(f"- {claim.text}" for claim in entry.bullets)
            lines.append("")
    return "\n".join(lines)


def render_pdf(cv: GeneratedCV, destination: Path, fonts: tuple[Path, Path]) -> None:
    pdfmetrics.registerFont(TTFont("CVRegular", str(fonts[0])))
    pdfmetrics.registerFont(TTFont("CVBold", str(fonts[1])))
    base = dict(fontName="CVRegular", fontSize=11, leading=13.2,
                textColor=colors.black, alignment=TA_LEFT, splitLongWords=True)
    body = ParagraphStyle("body", **base, spaceAfter=4)
    name = ParagraphStyle("name", parent=body, fontName="CVBold", fontSize=20, leading=24, keepWithNext=True)
    section_style = ParagraphStyle("section", parent=body, fontName="CVBold", fontSize=13,
                                   leading=15.6, spaceBefore=10, keepWithNext=True)
    entry_style = ParagraphStyle("entry", parent=body, fontName="CVBold", keepWithNext=True)
    bullet = ParagraphStyle("bullet", parent=body, leftIndent=10, firstLineIndent=-8)
    story = []

    def add(text, style, prefix="", keep=False):
        # Plain model text is always escaped; only exact standalone contact URLs
        # are linked. No model-supplied markup or external resources are interpreted.
        if "\n" in text or "\r" in text:
            text = " ".join(text.split())
        font = pdfmetrics.getFont(style.fontName)
        missing = [c for c in text if not c.isspace() and ord(c) not in font.face.charToGlyph]
        if missing:
            raise ValueError("The CV contains glyphs unsupported by the configured font.")
        safe = escape(text)
        if prefix == "":
            destination = None
            if re.fullmatch(r"https?://[^\s<>\"']+", text):
                destination = text
            elif re.fullmatch(r"[^\s<>\"'@]+@[^\s<>\"'@]+\.[^\s<>\"'@]+", text):
                destination = "mailto:" + text
            if destination:
                safe_url = escape(destination, {'"': "&quot;"})
                safe = f'<link href="{safe_url}">{safe}</link>'
        paragraph = Paragraph(prefix + safe, style)
        if keep:
            paragraph.keepWithNext = True
        story.append(paragraph)

    add(cv.candidate_name.text, name)
    for contact in cv.contacts:
        add(contact.text, body)
    for section in cv.sections:
        add(section.heading, section_style)
        for entry in section.entries:
            if entry.heading:
                add(entry.heading.text, entry_style)
            for index, detail in enumerate(entry.details):
                add(detail.text, body, keep=bool(entry.bullets) or index < len(entry.details) - 1)
            for claim in entry.bullets:
                add(claim.text, bullet, prefix="&#8226; ")
    document = SimpleDocTemplate(str(destination), pagesize=A4, rightMargin=20*mm,
                                leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm,
                                title="Curriculum Vitae", author=cv.candidate_name.text)
    document.build(story)


def expected_text(cv: GeneratedCV):
    yield cv.candidate_name.text
    yield from (claim.text for claim in cv.contacts)
    for section in cv.sections:
        yield section.heading
        for entry in section.entries:
            if entry.heading:
                yield entry.heading.text
            yield from (claim.text for claim in entry.details)
            yield from (claim.text for claim in entry.bullets)


def verify_pdf(cv: GeneratedCV, path: Path) -> int:
    reader = PdfReader(path)
    count = len(reader.pages)
    if not count or (cv.max_pages is not None and count > cv.max_pages):
        raise ValueError("The PDF exceeds the template page limit; shorten content before retrying.")
    if any(not page.extract_text().strip() for page in reader.pages):
        raise ValueError("The PDF contains a blank or non-extractable page.")
    def normalized(text):
        return "".join(unicodedata.normalize("NFC", text).split())
    extracted = "\n".join(page.extract_text() for page in reader.pages)
    # Ignore renderer-added bullet markers, but compare all remaining text exactly
    # after Unicode/whitespace normalization to detect duplication as well as loss.
    extracted = re.sub(r"(?m)^\s*• ?", "", extracted)
    if normalized(extracted) != normalized("\n".join(expected_text(cv))):
        raise ValueError("PDF text verification failed: content is missing, duplicated, or out of order.")
    return count
